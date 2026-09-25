import os
from pathlib import Path
import threading

from admin_dashboard import register_admin_routes
from app_config import get_gemini_model
from app_logging import configure_logging, get_logger
from config import load_env_file
from database import (
    DatabaseError,
    initialize_database,
    record_agent_turn,
    reset_history,
    save_model_message,
    update_messages_status,
)
from message_service import generate_customer_reply
from prompts import load_prompt_file, load_system_instruction
from session_coordinator import SessionCoordinator
from telegram_bot import build_telegram_channel
from whatsapp_bot import build_whatsapp_channel
from whatsapp_bot import get_settings as get_whatsapp_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "sales_agent.db"
LOG_PATH = PROJECT_ROOT / "data" / "logs" / "sales_agent.log"
CONVERSATION_LOG_PATH = PROJECT_ROOT / "data" / "logs" / "conversations.log"
PRIVATE_ENV_PATH = PROJECT_ROOT / ".private" / "meta-whatsapp" / "credentials.env"
MAX_WORKERS = 6

logger = get_logger("runner")


def get_common_settings():
    api_key = os.getenv("GEMINI_API_KEY")
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

    missing = [
        name
        for name, value in (
            ("GEMINI_API_KEY", api_key),
            ("TELEGRAM_BOT_TOKEN", telegram_token),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing settings: {', '.join(missing)}.")

    return api_key, get_gemini_model(), telegram_token


def main():
    load_env_file()
    load_env_file(PRIVATE_ENV_PATH)

    try:
        configure_logging(LOG_PATH, CONVERSATION_LOG_PATH)
        api_key, model, telegram_token = get_common_settings()
        whatsapp_settings = get_whatsapp_settings()
        initialize_database(DATABASE_PATH)
        system_instruction = load_system_instruction()
        selection_instruction = load_prompt_file("prompts/product_selection.md")
        response_instruction = load_prompt_file("prompts/product_response.md")
    except (DatabaseError, RuntimeError) as error:
        logger.exception("❌ Runner startup failed | error=%s", error)
        return

    def create_reply(session_id, user_text, in_reply_to_message_id):
        return generate_customer_reply(
            DATABASE_PATH,
            session_id,
            user_text,
            get_gemini_model(),
            api_key,
            system_instruction,
            selection_instruction,
            response_instruction,
            in_reply_to_message_id=in_reply_to_message_id,
        )

    def save_reply(session_id, reply):
        return save_model_message(
            DATABASE_PATH,
            session_id,
            reply.customer_reply,
            status="RESPONSE_READY",
        )

    def mark_messages_status(session_id, message_ids, status):
        update_messages_status(DATABASE_PATH, message_ids, status)

    coordinator = SessionCoordinator(
        create_reply,
        save_reply,
        mark_messages_status=mark_messages_status,
        record_turn=lambda session_id: record_agent_turn(DATABASE_PATH, session_id),
        max_workers=MAX_WORKERS,
    )

    telegram_channel = build_telegram_channel(
        DATABASE_PATH,
        model,
        api_key,
        telegram_token,
        system_instruction,
        selection_instruction,
        response_instruction,
        coordinator=coordinator,
    )

    railway_port = os.getenv("PORT")
    whatsapp_host = "0.0.0.0" if railway_port else "127.0.0.1"
    whatsapp_port = int(railway_port) if railway_port else 8000

    whatsapp_channel = build_whatsapp_channel(
        DATABASE_PATH,
        model,
        api_key,
        system_instruction,
        selection_instruction,
        response_instruction,
        access_token=whatsapp_settings["WHATSAPP_ACCESS_TOKEN"],
        phone_number_id=whatsapp_settings["WHATSAPP_PHONE_NUMBER_ID"],
        graph_api_version=whatsapp_settings["WHATSAPP_GRAPH_API_VERSION"],
        verify_token=whatsapp_settings["WHATSAPP_VERIFY_TOKEN"],
        app_secret=whatsapp_settings["WHATSAPP_APP_SECRET"],
        coordinator=coordinator,
        host=whatsapp_host,
        port=whatsapp_port,
    )

    register_admin_routes(
        whatsapp_channel.app,
        DATABASE_PATH,
        coordinator=coordinator,
        reset_fn=lambda session_id: reset_history(DATABASE_PATH, session_id),
        system_instruction=system_instruction,
    )

    telegram_channel.start()
    whatsapp_channel.start()

    logger.info(
        "🚀 Runner started | workers=%d telegram=on "
        "port=%d whatsapp_path=/webhooks/whatsapp admin_path=/admin",
        MAX_WORKERS,
        whatsapp_port,
    )
    print("Sales agent runner is running. Press Ctrl+C to stop.")

    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        logger.info("🛑 Runner stopping | signal=KeyboardInterrupt")
    finally:
        telegram_channel.stop()
        coordinator.shutdown()
        logger.info("🛑 Runner stopped")


if __name__ == "__main__":
    main()
