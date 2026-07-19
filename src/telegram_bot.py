import json
import os
from pathlib import Path
import time

import requests

from agent import AgentError
from config import load_env_file
from database import DatabaseError, initialize_database, reset_history
from message_service import reply_to_customer
from product_search import ProductSearchError
from prompts import load_prompt_file, load_system_instruction


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "sales_agent.db"
POLL_TIMEOUT_SECONDS = 25
MAX_MESSAGE_LENGTH = 4000


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


def handle_update(update, reply_fn, reset_fn, send_fn):
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
        send_fn(chat_id, "Söhbət tarixçəsi silindi.")
        return

    if command.startswith("/"):
        send_fn(chat_id, "Naməlum əmr. Mövcud əmr: /reset")
        return

    reply = reply_fn(session_id, text)
    send_fn(chat_id, reply)


def run_polling(token, update_handler):
    offset = None
    print("Telegram bot started. Press Ctrl+C to stop.")

    while True:
        try:
            updates = get_updates(token, offset)
        except TelegramError as error:
            print(f"Telegram polling error: {error}")
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
                print(f"Could not process Telegram update: {error}")


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


def main():
    load_env_file()

    try:
        api_key, model, telegram_token = get_settings()
        initialize_database(DATABASE_PATH)
        system_instruction = load_system_instruction()
        selection_instruction = load_prompt_file("prompts/product_selection.md")
        response_instruction = load_prompt_file("prompts/product_response.md")
    except (DatabaseError, RuntimeError) as error:
        print(f"Startup error: {error}")
        return

    def create_reply(session_id, user_text):
        return reply_to_customer(
            DATABASE_PATH,
            session_id,
            user_text,
            model,
            api_key,
            system_instruction,
            selection_instruction,
            response_instruction,
        )

    def clear_history(session_id):
        reset_history(DATABASE_PATH, session_id)

    def send_reply(chat_id, text):
        send_message(telegram_token, chat_id, text)

    def process_update(update):
        handle_update(update, create_reply, clear_history, send_reply)

    try:
        run_polling(telegram_token, process_update)
    except KeyboardInterrupt:
        print("Telegram bot stopped.")


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
