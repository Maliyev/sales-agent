import os
from pathlib import Path

import requests

from chat import send_message
from config import load_env_file
from database import (
    DatabaseError,
    create_session,
    initialize_database,
    list_session_ids,
    load_history,
    reset_history,
    save_exchange,
)
from gemini import get_model_reply


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "sales_agent.db"


def get_settings():
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to the .env file.")

    if not model:
        raise RuntimeError("GEMINI_MODEL is missing. Add it to the .env file.")

    return api_key, model


def main():
    load_env_file()
    api_key, model = get_settings()
    session_id = "terminal:default"

    try:
        initialize_database(DATABASE_PATH)
    except DatabaseError as error:
        print(f"Database error: {error}")
        return

    print("Sales agent started. Type 'exit' to stop.")
    print("Commands: /use <client>, /sessions, /reset")

    while True:
        user_text = input("You: ").strip()

        if user_text.lower() == "exit":
            break

        if user_text.startswith("/use "):
            client_id = user_text.removeprefix("/use ").strip()
            if not client_id:
                print("Write a client name after /use.")
                continue

            session_id = f"terminal:{client_id}"
            try:
                create_session(DATABASE_PATH, session_id)
            except DatabaseError as error:
                print(f"Database error: {error}")
                continue

            print(f"Current session: {session_id}")
            continue

        if user_text == "/sessions":
            try:
                session_ids = list_session_ids(DATABASE_PATH)
            except DatabaseError as error:
                print(f"Database error: {error}")
                continue

            if not session_ids:
                print("No sessions yet.")
                continue

            print("Sessions:")
            for item in session_ids:
                print(f"- {item}")
            continue

        if user_text == "/reset":
            try:
                reset_history(DATABASE_PATH, session_id)
            except DatabaseError as error:
                print(f"Database error: {error}")
                continue

            print(f"History cleared for {session_id}.")
            continue

        if not user_text:
            continue

        try:
            history = load_history(DATABASE_PATH, session_id)
            reply = send_message(
                history,
                user_text,
                lambda messages: get_model_reply(messages, model, api_key),
            )
            save_exchange(DATABASE_PATH, session_id, user_text, reply)
        except requests.RequestException as error:
            print(f"Request failed: {error}")
            continue
        except DatabaseError as error:
            print(f"Database error: {error}")
            continue
        except RuntimeError as error:
            print(f"Model error: {error}")
            continue

        print(f"Agent: {reply}")


if __name__ == "__main__":
    main()
