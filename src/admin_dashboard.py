import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from config import load_env_file
from database import (
    DatabaseError,
    initialize_database,
    list_sessions,
    load_session_messages,
    save_model_message,
)
from telegram_bot import TelegramError, send_message as send_telegram_message
from whatsapp_client import WhatsAppError, send_text_message


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "sales_agent.db"
PRIVATE_ENV_PATH = PROJECT_ROOT / ".private" / "meta-whatsapp" / "credentials.env"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
MAX_MANUAL_MESSAGE_LENGTH = 4000


class AdminDashboardError(RuntimeError):
    pass


def create_admin_app(database_path, send_fn):
    if not callable(send_fn):
        raise ValueError("send_fn must be callable.")

    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
    )

    @app.get("/")
    def dashboard():
        return render_template("admin.html")

    @app.get("/api/sessions")
    def sessions_api():
        return jsonify({"sessions": list_sessions(database_path)})

    @app.get("/api/sessions/<path:session_id>/messages")
    def messages_api(session_id):
        return jsonify(
            {
                "session_id": session_id,
                "messages": load_session_messages(database_path, session_id),
            }
        )

    @app.post("/api/sessions/<path:session_id>/messages")
    def send_message_api(session_id):
        payload = request.get_json(silent=True)
        text = payload.get("text") if isinstance(payload, dict) else None

        if not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Message must not be empty."}), 400

        text = text.strip()
        if len(text) > MAX_MANUAL_MESSAGE_LENGTH:
            return jsonify(
                {
                    "error": (
                        "Message is longer than "
                        f"{MAX_MANUAL_MESSAGE_LENGTH} characters."
                    )
                }
            ), 400

        try:
            send_fn(session_id, text)
            message_id = save_model_message(database_path, session_id, text)
        except AdminDashboardError as error:
            return jsonify({"error": str(error)}), 400
        except (DatabaseError, TelegramError, WhatsAppError):
            return jsonify({"error": "Message could not be sent."}), 502

        return jsonify({"id": message_id, "status": "sent"}), 201

    @app.errorhandler(DatabaseError)
    def database_error(_error):
        return jsonify({"error": "Database is temporarily unavailable."}), 500

    return app


def build_channel_sender():
    def send_to_channel(session_id, text):
        channel, separator, recipient = session_id.partition(":")
        if not separator or not recipient:
            raise AdminDashboardError("This session has an invalid ID.")

        if channel == "whatsapp":
            send_text_message(
                require_setting("WHATSAPP_ACCESS_TOKEN"),
                require_setting("WHATSAPP_PHONE_NUMBER_ID"),
                recipient,
                text,
                os.getenv("WHATSAPP_GRAPH_API_VERSION", "v25.0"),
            )
            return

        if channel == "telegram":
            try:
                chat_id = int(recipient)
            except ValueError as error:
                raise AdminDashboardError("Telegram session has an invalid chat ID.") from error
            send_telegram_message(
                require_setting("TELEGRAM_BOT_TOKEN"),
                chat_id,
                text,
            )
            return

        raise AdminDashboardError(
            f"Manual sending is not available for {channel} sessions."
        )

    return send_to_channel


def require_setting(name):
    value = os.getenv(name)
    if not value:
        raise AdminDashboardError(f"{name} is not configured.")
    return value


def main():
    load_env_file(PROJECT_ROOT / ".env")
    load_env_file(PRIVATE_ENV_PATH)
    initialize_database(DATABASE_PATH)

    app = create_admin_app(DATABASE_PATH, build_channel_sender())
    print(f"Admin dashboard: http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    app.run(
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
