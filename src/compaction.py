import time

from app_logging import get_logger, log_conversation
from database import (
    DatabaseError,
    add_history_summary,
    load_history_with_timestamps,
    record_api_call,
)
from gemini import (
    generate_content,
    get_text_response,
    get_usage_metadata,
)
from prompts import load_compaction_instruction


logger = get_logger("compaction")

MAX_SUMMARY_CHARACTERS = 8000
SUMMARY_PREFIX = "Summary of the earlier conversation:"

ROLE_LABELS = {
    "user": "Customer",
    "model": "Seller",
    "tool": "Earlier summary",
    "operator": "Operator",
}


class CompactionError(RuntimeError):
    pass


def compact_history(
    database_path,
    session_id,
    model,
    api_key,
    in_reply_to_message_id=None,
    compaction_instruction=None,
    generate_fn=generate_content,
    usage_fn=None,
    load_fn=load_history_with_timestamps,
):
    if compaction_instruction is None:
        compaction_instruction = load_compaction_instruction()

    rows = load_fn(database_path, session_id)
    if not rows:
        raise CompactionError("There is nothing to compact: the history is empty.")

    transcript = _format_transcript(rows)
    contents = [{"role": "user", "parts": [{"text": transcript}]}]

    started_at = time.monotonic()
    try:
        data = generate_fn(contents, model, api_key, compaction_instruction)
        summary = get_text_response(data).strip()
        if not summary:
            raise RuntimeError("The compaction model returned an empty summary.")
    except Exception as error:
        _record_call(
            database_path,
            session_id,
            in_reply_to_message_id,
            model,
            started_at,
            "failed",
            _describe_error(error),
        )
        raise CompactionError(f"Compaction request failed: {_describe_error(error)}") from error

    usage = _read_usage(usage_fn, data)
    _record_call(
        database_path,
        session_id,
        in_reply_to_message_id,
        model,
        started_at,
        "ok",
        None,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
    )

    if len(summary) > MAX_SUMMARY_CHARACTERS:
        summary = summary[:MAX_SUMMARY_CHARACTERS]
        logger.warning(
            "✂️ Compaction summary was truncated | session=%s",
            session_id,
        )

    try:
        add_history_summary(database_path, session_id, f"{SUMMARY_PREFIX}\n{summary}")
    except DatabaseError as error:
        raise CompactionError(f"Could not store the summary: {error}") from error

    logger.info(
        "🧹 Context compacted | session=%s messages=%d summary_chars=%d model=%s",
        session_id,
        len(rows),
        len(summary),
        model,
    )
    log_conversation(
        session_id,
        "SYSTEM",
        f"Context compacted: {len(rows)} messages replaced with a summary.",
    )


def _format_transcript(rows):
    lines = []
    for row in rows:
        label = ROLE_LABELS.get(row["role"], row["role"])
        lines.append(f"[{row['created_at']}] {label}: {row['text']}")
    return "\n\n".join(lines)


def _record_call(
    database_path,
    session_id,
    in_reply_to_message_id,
    model,
    started_at,
    status,
    error,
    prompt_tokens=0,
    completion_tokens=0,
):
    try:
        record_api_call(
            database_path,
            session_id,
            in_reply_to_message_id,
            "compaction",
            model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            status=status,
            error=error,
        )
    except DatabaseError as record_error:
        logger.warning(
            "⚠️ Could not record the compaction call | session=%s error=%s",
            session_id,
            record_error,
        )


def _read_usage(usage_fn, data):
    if usage_fn is None:
        usage_fn = get_usage_metadata
    try:
        usage = usage_fn(data)
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0}
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0}

    return {
        "prompt_tokens": _safe_int(usage.get("prompt_tokens")),
        "completion_tokens": _safe_int(usage.get("completion_tokens")),
    }


def _safe_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _describe_error(error):
    return f"{type(error).__name__}: {error}"[:300]
