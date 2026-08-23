import os
from pathlib import Path
import threading
from types import SimpleNamespace

import requests

from agent import AgentError
from app_logging import configure_logging, get_logger
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
LOG_PATH = PROJECT_ROOT / "data" / "logs" / "sales_agent.log"
CONVERSATION_LOG_PATH = PROJECT_ROOT / "data" / "logs" / "conversations.log"
PRIVATE_ENV_PATH = PROJECT_ROOT / ".private" / "meta-whatsapp" / "credentials.env"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
logger = get_logger("whatsapp")


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
        logger.info("➖ Ignored event for another WhatsApp phone number")
        return False
    if not claim_fn(message.message_id, message.sender_id):
        logger.info("➖ Ignored duplicate WhatsApp message")
        return False

    session_id = f"whatsapp:{message.sender_id}"
    try:
        if not allow_fn(session_id):
            logger.warning(
                "🚫 WhatsApp session blocked by message guard | session=%s",
                session_id,
            )
            return False
        logger.info(
            "WhatsApp message accepted | session=%s chars=%d",
            session_id,
            len(message.text),
        )
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


def build_whatsapp_channel(
    database_path,
    model,
    api_key,
    system_instruction,
    selection_instruction,
    response_instruction,
    access_token,
    phone_number_id,
    graph_api_version,
    verify_token,
    app_secret,
    coordinator=None,
    max_workers=4,
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
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
        save_exchange(database_path, session_id, user_text, reply.customer_reply)

    if coordinator is None:
        coordinator = SessionCoordinator(
            create_reply,
            save_reply,
            max_workers=max_workers,
        )

    def send_reply(recipient, text):
        send_text_message(
            access_token,
            phone_number_id,
            recipient,
            text,
            graph_api_version,
        )

    def note_operator_request(session_id, message):
        logger.info(
            "❗ Operator handoff recorded | session=%s summary_chars=%d",
            session_id,
            len(message),
        )

    def report_error(recipient, error):
        logger.error(
            "❌ Could not process WhatsApp message | error_type=%s error=%s",
            type(error).__name__,
            error,
        )
        try:
            send_reply(
                recipient,
                "Hazırda cavab verə bilmirəm. Zəhmət olmasa bir az sonra "
                "yenidən cəhd edin.",
            )
        except WhatsAppError as send_error:
            logger.error("❌ Could not send WhatsApp error message: %s", send_error)

    def submit_message(session_id, user_text, recipient):
        coordinator.submit(
            session_id,
            user_text,
            lambda reply: deliver_agent_reply(
                recipient,
                session_id,
                reply,
                send_reply,
                note_operator_request,
            ),
            lambda error: report_error(recipient, error),
        )

    def process_message(message):
        handle_incoming_message(
            message,
            phone_number_id,
            lambda message_id, sender_id: claim_incoming_message(
                database_path,
                message_id,
                sender_id,
            ),
            lambda message_id: release_incoming_message(database_path, message_id),
            lambda session_id: is_message_allowed(database_path, session_id),
            submit_message,
        )

    app = create_webhook_app(verify_token, app_secret, process_message)

    def run():
        logger.info(
            "🚀 WhatsApp webhook started | url=http://%s:%d%s",
            host,
            port,
            WEBHOOK_PATH,
        )
        app.run(
            host=host,
            port=port,
            threaded=True,
            use_reloader=False,
        )

    def start():
        thread = threading.Thread(target=run, name="whatsapp-webhook", daemon=True)
        thread.start()
        return thread

    def stop():
        logger.info("🛑 WhatsApp webhook stops with the process")

    def shutdown():
        coordinator.shutdown()

    return SimpleNamespace(
        name="whatsapp",
        run=run,
        start=start,
        stop=stop,
        shutdown=shutdown,
    )


def load_instructions():
    return (
        load_system_instruction(),
        load_prompt_file("prompts/product_selection.md"),
        load_prompt_file("prompts/product_response.md"),
    )


def main():
    load_env_file()
    load_env_file(PRIVATE_ENV_PATH)

    try:
        configure_logging(LOG_PATH, CONVERSATION_LOG_PATH)
        settings = get_settings()
        initialize_database(DATABASE_PATH)
        initialize_whatsapp_store(DATABASE_PATH)
        system_instruction, selection_instruction, response_instruction = (
            load_instructions()
        )
    except (DatabaseError, RuntimeError) as error:
        logger.exception("❌ WhatsApp startup failed | error=%s", error)
        return

    channel = build_whatsapp_channel(
        DATABASE_PATH,
        settings["GEMINI_MODEL"],
        settings["GEMINI_API_KEY"],
        system_instruction,
        selection_instruction,
        response_instruction,
        access_token=settings["WHATSAPP_ACCESS_TOKEN"],
        phone_number_id=settings["WHATSAPP_PHONE_NUMBER_ID"],
        graph_api_version=settings["WHATSAPP_GRAPH_API_VERSION"],
        verify_token=settings["WHATSAPP_VERIFY_TOKEN"],
        app_secret=settings["WHATSAPP_APP_SECRET"],
    )

    try:
        channel.run()
    except KeyboardInterrupt:
        logger.info("🛑 WhatsApp bot stopped")
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
        logger.exception("❌ WhatsApp server failed | error=%s", error)
    finally:
        channel.shutdown()


if __name__ == "__main__":
    main()
