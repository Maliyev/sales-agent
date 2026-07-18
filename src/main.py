import os

import requests

from chat import send_message
from config import load_env_file
from gemini import get_model_reply


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
    history = []

    print("Sales agent started. Type 'exit' to stop.")

    while True:
        user_text = input("You: ").strip()

        if user_text.lower() == "exit":
            break

        if not user_text:
            continue

        try:
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
