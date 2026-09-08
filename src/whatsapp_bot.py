import os
from pathlib import Path
import threading
from types import SimpleNamespace

import requests

from agent import AgentError
from app_config import get_gemini_model, get_vision_model
from app_logging import configure_logging, get_logger
from config import load_env_file
from database import (
    DatabaseError,
    initialize_database,
    insert_incoming_message,
    save_model_message,
    update_messages_status,
)
from document_reader import (
    MAX_DOCUMENT_FILE_SIZE,
    DocumentReadError,
    build_document_user_text,
    extract_document_text,
    is_supported_document,
)
from image_reader import (
    MAX_IMAGE_FILE_SIZE,
    ImageReadError,
    build_image_user_text,
    is_image,
    resolve_mime_type,
)
from image_reader import describe_image as describe_image_bytes
from message_guard import is_message_allowed
from message_service import generate_customer_reply
from product_search import ProductSearchError
from prompts import load_prompt_file, load_system_instruction
from reply_delivery import ReplyDeliveryError, deliver_agent_reply
from session_coordinator import SessionCoordinator
from whatsapp_client import WhatsAppError, download_media, send_text_message
from whatsapp_server import WEBHOOK_PATH, create_webhook_app
from whatsapp_store import (
    claim_incoming_message,
    release_incoming_message,
)
from whatsapp_webhook import (
    WhatsAppDocumentMessage,
    WhatsAppImageMessage,
    WhatsAppTextMessage,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "sales_agent.db"
LOG_PATH = PROJECT_ROOT / "data" / "logs" / "sales_agent.log"
CONVERSATION_LOG_PATH = PROJECT_ROOT / "data" / "logs" / "conversations.log"
PRIVATE_ENV_PATH = PROJECT_ROOT / ".private" / "meta-whatsapp" / "credentials.env"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
UNSUPPORTED_DOCUMENT_REPLY = (
    "Bu fayl formatını oxuya bilmirəm. Zəhmət olmasa .xlsx və ya "
    ".docx formatında göndərin."
)
UNREADABLE_DOCUMENT_REPLY = (
    "Sənədi oxuya bilmirəm. Zəhmət olmasa faylı yenidən göndərin."
)
UNREADABLE_IMAGE_REPLY = (
    "Şəkli emal edə bilmirəm. Zəhmət olmasa sorğunuzu mətn şəklində yazın."
)
OVERSIZED_DOCUMENT_REPLY = (
    "Fayl çox böyükdür. Zəhmət olmasa 5 MB-dan kiçik fayl göndərin."
)
DELIVERY_FAILURE_REPLY = (
    "Hazırda cavab verə bilmirəm. Zəhmət olmasa bir az sonra "
    "yenidən cəhd edin."
)
logger = get_logger("whatsapp")


def handle_incoming_message(
    message,
    expected_phone_number_id,
    claim_fn,
    release_fn,
    allow_fn,
    submit_fn,
    read_document_fn=None,
    download_media_fn=None,
    describe_image_fn=None,
    send_fn=None,
):
    if not isinstance(
        message,
        (WhatsAppTextMessage, WhatsAppDocumentMessage, WhatsAppImageMessage),
    ):
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
        if isinstance(message, WhatsAppImageMessage):
            user_text = _prepare_image_text(
                message,
                resolve_mime_type(None, message.mime_type),
                describe_image_fn,
                download_media_fn,
                send_fn,
            )
            if user_text is None:
                return True
            logger.info(
                "🖼 WhatsApp image accepted | session=%s desc_chars=%d",
                session_id,
                len(user_text),
            )
        elif isinstance(message, WhatsAppDocumentMessage):
            user_text = _prepare_document_text(
                message,
                read_document_fn,
                download_media_fn,
                describe_image_fn,
                send_fn,
            )
            if user_text is None:
                return True
            logger.info(
                "📄 WhatsApp document accepted | session=%s filename=%s chars=%d",
                session_id,
                message.filename,
                len(user_text),
            )
        else:
            user_text = message.text
            logger.info(
                "WhatsApp message accepted | session=%s chars=%d",
                session_id,
                len(user_text),
            )
        submit_fn(session_id, user_text, message.sender_id)
    except Exception:
        release_fn(message.message_id)
        raise

    return True


def _prepare_document_text(
    message,
    read_document_fn,
    download_media_fn,
    describe_image_fn,
    send_fn,
):
    if read_document_fn is None or download_media_fn is None or send_fn is None:
        raise WhatsAppError("WhatsApp document handlers are not configured.")

    mime_type = resolve_mime_type(message.filename, message.mime_type)
    if is_image(mime_type, message.filename):
        return _prepare_image_text(
            message,
            mime_type,
            describe_image_fn,
            download_media_fn,
            send_fn,
        )

    if not is_supported_document(message.filename):
        logger.info(
            "➖ Ignored unsupported WhatsApp document | filename=%s",
            message.filename,
        )
        send_fn(message.sender_id, UNSUPPORTED_DOCUMENT_REPLY)
        return None

    try:
        data = download_media_fn(message.media_id)
    except (WhatsAppError, requests.RequestException) as error:
        logger.error(
            "❌ Could not download WhatsApp document | filename=%s error=%s",
            message.filename,
            error,
        )
        send_fn(message.sender_id, DELIVERY_FAILURE_REPLY)
        return None

    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_DOCUMENT_FILE_SIZE:
        send_fn(message.sender_id, OVERSIZED_DOCUMENT_REPLY)
        return None

    try:
        extracted_text = read_document_fn(message.filename, data)
    except DocumentReadError as error:
        logger.warning(
            "📄 Could not read WhatsApp document | filename=%s error=%s",
            message.filename,
            error,
        )
        send_fn(message.sender_id, UNREADABLE_DOCUMENT_REPLY)
        return None

    return build_document_user_text(message.filename, extracted_text, message.caption)


def _prepare_image_text(
    message,
    mime_type,
    describe_image_fn,
    download_media_fn,
    send_fn,
):
    if describe_image_fn is None or download_media_fn is None or send_fn is None:
        raise WhatsAppError("WhatsApp image handlers are not configured.")

    try:
        data = download_media_fn(message.media_id)
    except (WhatsAppError, requests.RequestException) as error:
        logger.error(
            "❌ Could not download WhatsApp image | media_id=%s error=%s",
            message.media_id,
            error,
        )
        send_fn(message.sender_id, DELIVERY_FAILURE_REPLY)
        return None

    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_IMAGE_FILE_SIZE:
        send_fn(message.sender_id, OVERSIZED_DOCUMENT_REPLY)
        return None

    session_id = f"whatsapp:{message.sender_id}"
    try:
        description = describe_image_fn(data, mime_type, session_id)
    except ImageReadError as error:
        logger.warning(
            "🖼 Could not describe WhatsApp image | media_id=%s error=%s",
            message.media_id,
            error,
        )
        send_fn(message.sender_id, UNREADABLE_IMAGE_REPLY)
        return None

    return build_image_user_text(description, message.caption)


def get_settings():
    names = (
        "GEMINI_API_KEY",
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

    settings["GEMINI_MODEL"] = get_gemini_model()
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
    def create_reply(session_id, user_text, in_reply_to_message_id):
        return generate_customer_reply(
            database_path,
            session_id,
            user_text,
            model,
            api_key,
            system_instruction,
            selection_instruction,
            response_instruction,
            in_reply_to_message_id=in_reply_to_message_id,
        )

    def save_reply(session_id, reply):
        return save_model_message(
            database_path,
            session_id,
            reply.customer_reply,
            status="RESPONSE_READY",
        )

    if coordinator is None:
        def mark_messages_status(session_id, message_ids, status):
            update_messages_status(database_path, message_ids, status)

        coordinator = SessionCoordinator(
            create_reply,
            save_reply,
            mark_messages_status=mark_messages_status,
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
            send_reply(recipient, DELIVERY_FAILURE_REPLY)
        except WhatsAppError as send_error:
            logger.error("❌ Could not send WhatsApp error message: %s", send_error)

    def submit_message(session_id, user_text, recipient):
        try:
            message_id = insert_incoming_message(database_path, session_id, user_text)
        except DatabaseError as error:
            logger.error(
                "❌ Could not store the message | session=%s error=%s",
                session_id,
                error,
            )
            report_error(recipient, error)
            return

        coordinator.submit(
            session_id,
            message_id,
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

    def download_document_media(media_id):
        return download_media(
            access_token,
            phone_number_id,
            media_id,
            graph_api_version,
        )

    def read_document(filename, data):
        return extract_document_text(filename, data)

    def describe_image(data, mime_type, session_id):
        return describe_image_bytes(
            data,
            mime_type,
            get_vision_model(),
            api_key,
            database_path,
            session_id,
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
            read_document_fn=read_document,
            download_media_fn=download_document_media,
            describe_image_fn=describe_image,
            send_fn=send_reply,
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
