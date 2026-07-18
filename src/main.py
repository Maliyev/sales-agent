import os

import requests

from chat import send_message
from config import load_env_file
from gemini import get_model_reply
from sessions import get_history, list_session_ids, reset_history


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
    sessions = {}
    session_id = "terminal:default"

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
            get_history(sessions, session_id)
            print(f"Current session: {session_id}")
            continue

        if user_text == "/sessions":
            session_ids = list_session_ids(sessions)
            if not session_ids:
                print("No sessions yet.")
                continue

            print("Sessions:")
            for item in session_ids:
                print(f"- {item}")
            continue

        if user_text == "/reset":
            reset_history(sessions, session_id)
            print(f"History cleared for {session_id}.")
            continue

        if not user_text:
            continue

        try:
            history = get_history(sessions, session_id)
            reply = send_message(
                history,
                user_text,
                lambda messages: get_model_reply(messages, model, api_key),
            )
        except requests.RequestException as error:
            print(f"Request failed: {error}")
            continue
        except RuntimeError as error:
            print(f"Model error: {error}")
            continue

        print(f"Agent: {reply}")


if __name__ == "__main__":
    main()
