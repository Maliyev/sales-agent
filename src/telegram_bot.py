import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import requests

from agent import AgentError
from app_logging import configure_logging, get_logger
from config import load_env_file
from database import (
    DatabaseError,
    initialize_database,
    reset_history,
    save_exchange,
    update_messages_status,
)
from message_guard import is_message_allowed
from message_service import generate_customer_reply
from product_search import ProductSearchError
from prompts import load_prompt_file, load_system_instruction
from reply_delivery import deliver_agent_reply
from session_coordinator import SessionCoordinator


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "sales_agent.db"
LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "logs" / "sales_agent.log"
CONVERSATION_LOG_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "logs" / "conversations.log"
)
POLL_TIMEOUT_SECONDS = 25
MAX_MESSAGE_LENGTH = 4000
logger = get_logger("telegram")


class TelegramError(RuntimeError):
    pass


def get_updates(token, offset=None, session=requests):
    params = {
        "timeout": POLL_TIMEOUT_SECONDS,
        "allowed_updates": json.dumps(["message"]),
    }
    if offset is not None:
        params["offset"] = offset

    result = _telegram_request(
        token,
        "getUpdates",
        session.get,
        params=params,
        timeout=POLL_TIMEOUT_SECONDS + 5,
    )
    if not isinstance(result, list):
        raise TelegramError("Telegram returned an invalid update list.")
    return result


def send_message(token, chat_id, text, session=requests):
    for chunk in split_message(text):
        _telegram_request(
            token,
            "sendMessage",
            session.post,
            json={"chat_id": chat_id, "text": chunk},
            timeout=15,
        )


def split_message(text):
    if not isinstance(text, str) or not text:
        raise TelegramError("Telegram message must not be empty.")
    return [
        text[start : start + MAX_MESSAGE_LENGTH]
        for start in range(0, len(text), MAX_MESSAGE_LENGTH)
    ]


def handle_update(update, submit_fn, reset_fn, send_fn, allow_fn=None):
    if not isinstance(update, dict):
        return

    message = update.get("message")
    if not isinstance(message, dict):
        return

    chat = message.get("chat")
    if not isinstance(chat, dict):
        return
    chat_id = chat.get("id")
    if isinstance(chat_id, bool) or not isinstance(chat_id, int):
        return

    text = message.get("text")
    if not isinstance(text, str) or not text.strip():
        send_fn(chat_id, "Hazırda yalnız mətn mesajlarını oxuya bilirəm.")
        return

    text = text.strip()
    session_id = f"telegram:{chat_id}"
    if allow_fn is not None and not allow_fn(session_id):
        logger.warning(
            "🚫 Telegram session blocked by message guard | session=%s",
            session_id,
        )
        return

    command = text.split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()

    if command == "/start":
        send_fn(
            chat_id,
            "Salam! Mən elen.az köməkçisiyəm. Məhsullar haqqında sual verə "
            "bilərsiniz. Söhbəti silmək üçün /reset yazın.",
        )
        return

    if command == "/reset":
        reset_fn(session_id)
        logger.info(
            "🧹 Telegram session reset | session=%s",
            session_id,
        )
        send_fn(chat_id, "Söhbət tarixçəsi silindi.")
        return

    if command.startswith("/"):
        send_fn(chat_id, "Naməlum əmr. Mövcud əmr: /reset")
        return

    submit_fn(session_id, text, chat_id)


def run_polling(token, update_handler, stop_event=None):
    offset = None
    logger.info("🚀 Telegram polling started")

    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("🛑 Telegram polling stopped")
            return

        try:
            updates = get_updates(token, offset)
        except TelegramError as error:
            if stop_event is not None and stop_event.is_set():
                logger.info("🛑 Telegram polling stopped")
                return
            logger.error("❌ Telegram polling failed: %s", error)
            time.sleep(3)
            continue

        for update in updates:
            update_id = update.get("update_id") if isinstance(update, dict) else None
            if isinstance(update_id, int) and not isinstance(update_id, bool):
                offset = update_id + 1

            try:
                update_handler(update)
            except (
                AgentError,
                DatabaseError,
                ProductSearchError,
                TelegramError,
                requests.RequestException,
                RuntimeError,
            ) as error:
                logger.exception("❌ Could not process Telegram update: %s", error)


def build_telegram_channel(
    database_path,
    model,
    api_key,
    telegram_token,
    system_instruction,
    selection_instruction,
    response_instruction,
    coordinator=None,
    max_workers=4,
):
    def create_reply(session_id, user_text):
        return generate_customer_reply(
            database_path,
            session_id,
            user_text,
            model,
            api_key,
            system_instruction,
            selection_instruction,
            response_instruction,
        )

    def save_reply(session_id, user_text, reply):
        return save_exchange(
            database_path,
            session_id,
            user_text,
            reply.customer_reply,
            status="RESPONSE_READY",
        )

    if coordinator is None:
        def mark_delivery_result(session_id, message_ids, delivered):
            update_messages_status(
                database_path,
                message_ids,
                "DELIVERED" if delivered else "FAILED_DELIVERY",
            )

        coordinator = SessionCoordinator(
            create_reply,
            save_reply,
            mark_delivery_result=mark_delivery_result,
            max_workers=max_workers,
        )

    def send_reply(chat_id, text):
        send_message(telegram_token, chat_id, text)

    def note_operator_request(session_id, message):
        logger.info(
            "❗ Operator handoff recorded | session=%s summary_chars=%d",
            session_id,
            len(message),
        )

    def report_error(chat_id, error):
        logger.error(
            "❌ Could not process Telegram message | error_type=%s error=%s",
            type(error).__name__,
            error,
        )
        try:
            send_reply(
                chat_id,
                "Hazırda cavab verə bilmirəm. Zəhmət olmasa bir az sonra "
                "yenidən cəhd edin.",
            )
        except TelegramError as send_error:
            logger.error("❌ Could not send Telegram error message: %s", send_error)

    def submit_message(session_id, user_text, chat_id):
        coordinator.submit(
            session_id,
            user_text,
            lambda reply: deliver_agent_reply(
                chat_id,
                session_id,
                reply,
                send_reply,
                note_operator_request,
            ),
            lambda error: report_error(chat_id, error),
        )

    def clear_history(session_id):
        coordinator.reset_session(
            session_id,
            lambda: reset_history(database_path, session_id),
        )

    def process_update(update):
        handle_update(
            update,
            submit_message,
            clear_history,
            send_reply,
            lambda session_id: is_message_allowed(database_path, session_id),
        )

    stop_event = threading.Event()

    def run():
        run_polling(telegram_token, process_update, stop_event)

    def start():
        thread = threading.Thread(target=run, name="telegram-bot", daemon=True)
        thread.start()
        return thread

    def stop():
        stop_event.set()

    def shutdown():
        coordinator.shutdown()

    return SimpleNamespace(
        name="telegram",
        run=run,
        start=start,
        stop=stop,
        shutdown=shutdown,
    )


def get_settings():
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to the .env file.")
    if not model:
        raise RuntimeError("GEMINI_MODEL is missing. Add it to the .env file.")
    if not telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing. Add it to the .env file.")

    return api_key, model, telegram_token


def load_instructions():
    return (
        load_system_instruction(),
        load_prompt_file("prompts/product_selection.md"),
        load_prompt_file("prompts/product_response.md"),
    )


def main():
    load_env_file()

    try:
        configure_logging(LOG_PATH, CONVERSATION_LOG_PATH)
        api_key, model, telegram_token = get_settings()
        initialize_database(DATABASE_PATH)
        system_instruction, selection_instruction, response_instruction = (
            load_instructions()
        )
    except (DatabaseError, RuntimeError) as error:
        logger.exception("❌ Telegram startup failed | error=%s", error)
        return

    channel = build_telegram_channel(
        DATABASE_PATH,
        model,
        api_key,
        telegram_token,
        system_instruction,
        selection_instruction,
        response_instruction,
    )

    try:
        channel.run()
    except KeyboardInterrupt:
        logger.info("🛑 Telegram bot stopped")
    finally:
        channel.shutdown()


def _telegram_request(token, method, request_fn, **kwargs):
    url = f"https://api.telegram.org/bot{token}/{method}"

    try:
        response = request_fn(url, **kwargs)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise TelegramError(f"Telegram {method} request failed.") from error

    if not isinstance(data, dict) or data.get("ok") is not True:
        description = data.get("description") if isinstance(data, dict) else None
        if not isinstance(description, str):
            description = "Unknown Telegram API error."
        raise TelegramError(description)

    return data.get("result")


if __name__ == "__main__":
    main()
