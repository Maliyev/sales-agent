import os
from pathlib import Path

import requests

from agent import AgentError
from app_logging import configure_logging
from config import load_env_file
from database import (
    DatabaseError,
    create_session,
    initialize_database,
    list_session_ids,
    reset_history,
)
from message_service import reply_to_customer
from product_search import ProductSearchError
from prompts import load_prompt_file, load_system_instruction
from reply_delivery import deliver_agent_reply


DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "sales_agent.db"
LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "logs" / "sales_agent.log"
CONVERSATION_LOG_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "logs" / "conversations.log"
)


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
    configure_logging(LOG_PATH, CONVERSATION_LOG_PATH)
    api_key, model = get_settings()
    session_id = "terminal:default"

    try:
        initialize_database(DATABASE_PATH)
        system_instruction = load_system_instruction()
        selection_instruction = load_prompt_file("prompts/product_selection.md")
        response_instruction = load_prompt_file("prompts/product_response.md")
    except DatabaseError as error:
        print(f"Database error: {error}")
        return
    except RuntimeError as error:
        print(f"Prompt error: {error}")
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
            reply = reply_to_customer(
                DATABASE_PATH,
                session_id,
                user_text,
                model,
                api_key,
                system_instruction,
                selection_instruction,
                response_instruction,
            )
        except ProductSearchError as error:
            print(f"Product search error: {error}")
            continue
        except requests.RequestException as error:
            print(f"Request failed: {error}")
            continue
        except DatabaseError as error:
            print(f"Database error: {error}")
            continue
        except (AgentError, RuntimeError) as error:
            print(f"Agent error: {error}")
            continue

        deliver_agent_reply(
            session_id,
            session_id,
            reply,
            lambda _destination, text: print(f"Agent: {text}"),
            lambda _session_id, message: print(f"Operator request: {message}"),
        )


if __name__ == "__main__":
    main()
