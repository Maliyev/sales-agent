"""On-demand operational report from retained conversation log files."""

import os
import time
from datetime import datetime, time as day_time, timedelta, timezone
from pathlib import Path

from app_logging import get_logger
from database import DatabaseError, create_session, record_api_call
from openrouter import OpenRouterError, generate_content


BAKU_TIMEZONE = timezone(timedelta(hours=4), name="Asia/Baku")
MODEL = "z-ai/glm-5.3-flash"
REPORT_SESSION_ID = "admin:report"
MAX_DAYS = 30
MAX_LOG_CHARACTERS = 1_000_000
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "admin_report.md"
logger = get_logger("admin.report")


class ReportError(RuntimeError):
    pass


def calendar_window(days, now=None):
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
        raise ReportError(f"Укажите от 1 до {MAX_DAYS} календарных дней.")
    now = (now or datetime.now(BAKU_TIMEZONE)).astimezone(BAKU_TIMEZONE)
    last_day = now.date() - timedelta(days=1 if now.hour < 5 else 0)
    first_day = last_day - timedelta(days=days - 1)
    return datetime.combine(first_day, day_time.min, BAKU_TIMEZONE), now


def _timestamp(line):
    stamp = line.split(" | ", 1)[0].lstrip("\ufeff")
    for format_string in ("%y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(stamp, format_string)
        except ValueError:
            continue
    return None


def read_conversation_window(log_path, start, end, log_timezone=None):
    """Read every matching line from the current log and retained rotations."""
    path = Path(log_path)
    paths = [Path(f"{path}.{index}") for index in (3, 2, 1)] + [path]
    if not any(item.is_file() for item in paths):
        raise ReportError("conversations.log пока недоступен.")
    log_timezone = log_timezone or datetime.now().astimezone().tzinfo
    start_utc, end_utc = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    lines = []
    characters = 0
    sessions = set()
    first_seen = None
    last_seen = None
    try:
        for item in paths:
            if not item.is_file():
                continue
            with item.open("r", encoding="utf-8", errors="replace") as file:
                for line in file:
                    stamp = _timestamp(line)
                    if stamp is None:
                        continue
                    moment = stamp.replace(tzinfo=log_timezone).astimezone(timezone.utc)
                    first_seen = moment if first_seen is None else min(first_seen, moment)
                    last_seen = moment if last_seen is None else max(last_seen, moment)
                    if not start_utc <= moment <= end_utc:
                        continue
                    lines.append(line.rstrip("\r\n"))
                    characters += len(lines[-1])
                    if characters > MAX_LOG_CHARACTERS:
                        raise ReportError(
                            "За выбранный период больше 1 млн символов логов. "
                            "Уменьшите число дней; запрос к модели не отправлен."
                        )
                    parts = line.split(" | ", 3)
                    if len(parts) >= 3 and parts[2].strip().endswith("USER"):
                        sessions.add(parts[1].strip())
    except OSError as error:
        logger.error("Could not read conversation logs: %s", error)
        raise ReportError("Не удалось прочитать журнал разговоров.") from error
    return {
        "lines": lines,
        "customer_sessions": len(sessions),
        "available_from": first_seen.astimezone(BAKU_TIMEZONE).isoformat() if first_seen else None,
        "available_until": last_seen.astimezone(BAKU_TIMEZONE).isoformat() if last_seen else None,
        "coverage_warning": bool(first_seen and first_seen > start_utc),
    }


def generate_report(days, log_path, database_path=None, generate_fn=generate_content,
                    now=None, log_timezone=None):
    start, end = calendar_window(days, now)
    data = read_conversation_window(log_path, start, end, log_timezone)
    result = {
        "start": start.isoformat(), "end": end.isoformat(),
        "log_lines": len(data["lines"]),
        "customer_sessions": data["customer_sessions"],
        "available_from": data["available_from"],
        "available_until": data["available_until"],
        "coverage_warning": data["coverage_warning"],
        "model": MODEL,
    }
    if not data["lines"]:
        result["report"] = "За выбранный период в доступном журнале нет записей."
        result["model_called"] = False
        return result

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ReportError("OPENROUTER_API_KEY не настроен.")
    try:
        prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ReportError("Не удалось прочитать промпт отчёта.") from error
    if not prompt:
        raise ReportError("Промпт отчёта пуст.")

    metadata = (
        f"Период по Баку: {start.isoformat()} — {end.isoformat()}\n"
        f"Строк журнала: {len(data['lines'])}\n"
        f"Уникальных сессий с событием USER: {data['customer_sessions']}\n"
        f"Журнал начинается: {data['available_from'] or 'неизвестно'}\n"
        f"Возможна неполная история: {'да' if data['coverage_warning'] else 'нет'}\n\n"
        "Ниже исходные строки conversations.log:\n"
    )
    started = time.monotonic()
    try:
        response = generate_fn(
            [{"role": "user", "parts": [{"text": metadata + "\n".join(data["lines"])}]}],
            MODEL, api_key, prompt, timeout=180, reasoning_effort="low",
            max_completion_tokens=3000,
        )
    except OpenRouterError as error:
        _record_usage(database_path, 0, 0, int((time.monotonic() - started) * 1000),
                      "failed")
        raise ReportError(str(error)) from error
    usage = response.get("usageMetadata") or {}
    _record_usage(database_path, usage.get("promptTokenCount", 0),
                  usage.get("candidatesTokenCount", 0),
                  int((time.monotonic() - started) * 1000), "ok",
                  cost_usd=usage.get("costUsd"))
    parts = response["candidates"][0]["content"]["parts"]
    report = "\n".join(part["text"] for part in parts if isinstance(part.get("text"), str)).strip()
    if not report:
        raise ReportError("Модель вернула пустой отчёт.")
    result["report"] = report
    result["model_called"] = True
    return result


def _record_usage(database_path, prompt_tokens, completion_tokens, duration_ms, status,
                  cost_usd=None):
    if database_path is None:
        return
    try:
        create_session(database_path, REPORT_SESSION_ID)
        record_api_call(database_path, REPORT_SESSION_ID, None, "final",
                        f"openrouter:{MODEL}", prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens, duration_ms=duration_ms,
                        status=status, cost_usd=cost_usd)
    except DatabaseError:
        logger.exception("Could not record admin report API usage")
