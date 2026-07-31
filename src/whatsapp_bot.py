import os
from pathlib import Path

import requests

from agent import AgentError
from config import load_env_file
from database import DatabaseError, initialize_database, save_exchange
from message_guard import is_message_allowed
from message_service import generate_customer_reply
from product_search import ProductSearchError
from prompts import load_prompt_file, load_system_instruction
from reply_delivery import ReplyDeliveryError, deliver_agent_reply
from session_coordinator import SessionCoordinator
from whatsapp_client import WhatsAppError, send_text_message
from whatsapp_server import WEBHOOK_PATH, create_webhook_app
from whatsapp_store import (
    claim_incoming_message,
    initialize_whatsapp_store,
    release_incoming_message,
)
from whatsapp_webhook import WhatsAppTextMessage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "sales_agent.db"
PRIVATE_ENV_PATH = PROJECT_ROOT / ".private" / "meta-whatsapp" / "credentials.env"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def handle_incoming_message(
    message,
    expected_phone_number_id,
    claim_fn,
    release_fn,
    allow_fn,
    submit_fn,
):
    if not isinstance(message, WhatsAppTextMessage):
        raise WhatsAppError("WhatsApp returned an invalid incoming message.")
    if message.phone_number_id != expected_phone_number_id:
        return False
    if not claim_fn(message.message_id, message.sender_id):
        return False

    session_id = f"whatsapp:{message.sender_id}"
    try:
        if not allow_fn(session_id):
            return False
        submit_fn(session_id, message.text, message.sender_id)
    except Exception:
        release_fn(message.message_id)
        raise

    return True


def get_settings():
    names = (
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_GRAPH_API_VERSION",
        "WHATSAPP_VERIFY_TOKEN",
        "WHATSAPP_APP_SECRET",
    )
    settings = {}

    for name in names:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"{name} is missing.")
        settings[name] = value

    return settings


def main():
    load_env_file()
    load_env_file(PRIVATE_ENV_PATH)

    try:
        settings = get_settings()
        initialize_database(DATABASE_PATH)
        initialize_whatsapp_store(DATABASE_PATH)
        system_instruction = load_system_instruction()
        selection_instruction = load_prompt_file("prompts/product_selection.md")
        response_instruction = load_prompt_file("prompts/product_response.md")
    except (DatabaseError, RuntimeError) as error:
        print(f"WhatsApp startup error: {error}")
        return

    def create_reply(session_id, user_text):
        return generate_customer_reply(
            DATABASE_PATH,
            session_id,
            user_text,
            settings["GEMINI_MODEL"],
            settings["GEMINI_API_KEY"],
            system_instruction,
            selection_instruction,
            response_instruction,
        )

    def save_reply(session_id, user_text, reply):
        save_exchange(DATABASE_PATH, session_id, user_text, reply.customer_reply)

    def send_reply(recipient, text):
        send_text_message(
            settings["WHATSAPP_ACCESS_TOKEN"],
            settings["WHATSAPP_PHONE_NUMBER_ID"],
            recipient,
            text,
            settings["WHATSAPP_GRAPH_API_VERSION"],
        )

    def report_operator_request(session_id, message):
        print(f"Operator request for {session_id}: {message}")

    def report_error(recipient, error):
        print(f"Could not process WhatsApp message: {error}")
        try:
            send_reply(
                recipient,
                "Hazırda cavab verə bilmirəm. Zəhmət olmasa bir az sonra "
                "yenidən cəhd edin.",
            )
        except WhatsAppError as send_error:
            print(f"Could not send WhatsApp error message: {send_error}")

    coordinator = SessionCoordinator(create_reply, save_reply, max_workers=4)

    def submit_message(session_id, user_text, recipient):
        coordinator.submit(
            session_id,
            user_text,
            lambda reply: deliver_agent_reply(
                recipient,
                session_id,
                reply,
                send_reply,
                report_operator_request,
            ),
            lambda error: report_error(recipient, error),
        )

    def process_message(message):
        handle_incoming_message(
            message,
            settings["WHATSAPP_PHONE_NUMBER_ID"],
            lambda message_id, sender_id: claim_incoming_message(
                DATABASE_PATH,
                message_id,
                sender_id,
            ),
            lambda message_id: release_incoming_message(DATABASE_PATH, message_id),
            lambda session_id: is_message_allowed(DATABASE_PATH, session_id),
            submit_message,
        )

    try:
        app = create_webhook_app(
            settings["WHATSAPP_VERIFY_TOKEN"],
            settings["WHATSAPP_APP_SECRET"],
            process_message,
        )
        print(
            f"WhatsApp webhook listening on http://{DEFAULT_HOST}:{DEFAULT_PORT}"
            f"{WEBHOOK_PATH}"
        )
        app.run(
            host=DEFAULT_HOST,
            port=DEFAULT_PORT,
            threaded=True,
            use_reloader=False,
        )
    except (
        AgentError,
        DatabaseError,
        ProductSearchError,
        ReplyDeliveryError,
        WhatsAppError,
        requests.RequestException,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"WhatsApp server error: {error}")
    finally:
        coordinator.shutdown()


if __name__ == "__main__":
    main()
