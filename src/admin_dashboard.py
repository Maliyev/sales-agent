"""Authenticated admin routes mounted on the WhatsApp Flask server."""

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from pathlib import Path

from flask import Blueprint, Flask, jsonify, redirect, render_template, request, session, url_for

from app_config import ConfigError, editable_config, save_config
from admin_report import ReportError, generate_report
from app_logging import flatten_text, get_logger, log_conversation
from database import (
    DatabaseError, admin_session_messages, block_session, dashboard_overview,
    list_blocked_sessions, list_sessions, reset_history,
    save_model_message, session_exists, unblock_session, validate_session_id,
)
from gemini import CHARACTERS_PER_TOKEN
from prompts import load_system_instruction
from telegram_bot import TelegramError, send_message as send_telegram_message
from whatsapp_client import WhatsAppError, send_text_message


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "data" / "sales_agent.db"
CONVERSATION_LOG_PATH = PROJECT_ROOT / "data" / "logs" / "conversations.log"
MAX_MANUAL_MESSAGE_LENGTH = 4000
logger = get_logger("admin")


class AdminDashboardError(RuntimeError):
    pass


def _session_id(value):
    _admin_session_id(value)
    if not re.fullmatch(r"(?:whatsapp:[0-9]{1,20}|telegram:-?[0-9]{1,20})", value):
        raise AdminDashboardError("Invalid WhatsApp or Telegram session ID.")
    return value


def _admin_session_id(value):
    try:
        validate_session_id(value)
    except DatabaseError as error:
        raise AdminDashboardError(str(error)) from error
    if any(ord(character) < 32 for character in value):
        raise AdminDashboardError("Session ID contains invalid characters.")
    return value


def register_admin_routes(app, database_path, send_fn=None, coordinator=None,
                          reset_fn=None, log_path=CONVERSATION_LOG_PATH,
                          system_instruction=None):
    password = os.getenv("ADMIN_PASSWORD")
    secret_key = os.getenv("ADMIN_SESSION_SECRET")
    if not password or not secret_key or len(secret_key) < 32:
        raise RuntimeError("Set ADMIN_PASSWORD and ADMIN_SESSION_SECRET (at least 32 characters).")
    if send_fn is None:
        send_fn = build_channel_sender()
    if not callable(send_fn):
        raise ValueError("send_fn must be callable.")
    if reset_fn is None:
        reset_fn = lambda session_id: reset_history(database_path, session_id)
    if system_instruction is None:
        system_instruction = load_system_instruction()

    app.secret_key = secret_key
    app.config.update(SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SECURE=bool(os.getenv("PORT")),
                      SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=60 * 60 * 12)
    admin = Blueprint("admin", __name__, url_prefix="/admin",
                      template_folder=str(PROJECT_ROOT / "templates"),
                      static_folder=str(PROJECT_ROOT / "static"),
                      static_url_path="/static")
    failures = {}
    failure_lock = threading.Lock()
    report_lock = threading.Lock()

    def csrf_ok():
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        return bool(expected) and hmac.compare_digest(supplied, expected)

    @admin.before_request
    def protect():
        if request.endpoint != "admin.login":
            if not session.get("admin_authenticated"):
                if request.path.startswith("/admin/api/"):
                    return jsonify(error="Authentication required."), 401
                return redirect(url_for("admin.login"))
            if request.method not in ("GET", "HEAD", "OPTIONS") and not csrf_ok():
                return jsonify(error="Invalid CSRF token."), 403

    @admin.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @admin.route("/login", methods=["GET", "POST"])
    def login():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        if request.method == "GET":
            if session.get("admin_authenticated"):
                return redirect(url_for("admin.dashboard"))
            return render_template("admin_login.html", error=None)
        if not csrf_ok():
            return render_template("admin_login.html", error="Invalid request."), 403
        client = request.remote_addr or "unknown"
        now = time.monotonic()
        with failure_lock:
            attempts = [stamp for stamp in failures.get(client, []) if now - stamp < 900]
            failures[client] = attempts
            limited = len(attempts) >= 5
        if limited:
            return render_template("admin_login.html", error="Too many attempts. Try later."), 429
        candidate = request.form.get("password", "")
        valid = hmac.compare_digest(hashlib.sha256(candidate.encode()).digest(),
                                    hashlib.sha256(password.encode()).digest())
        if not valid:
            with failure_lock:
                failures[client].append(now)
            return render_template("admin_login.html", error="Invalid password."), 401
        with failure_lock:
            failures.pop(client, None)
        session.clear()
        session["admin_authenticated"] = True
        session["csrf_token"] = secrets.token_urlsafe(32)
        session.permanent = True
        return redirect(url_for("admin.dashboard"))

    @admin.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("admin.login"))

    @admin.get("")
    @admin.get("/")
    def dashboard():
        return render_template("admin.html", csrf_token=session["csrf_token"])

    @admin.get("/api/overview")
    def overview_api():
        hours = {"24h": 24, "7d": 168, "30d": 720}.get(request.args.get("period", "24h"))
        if hours is None:
            return jsonify(error="Invalid period."), 400
        return jsonify(dashboard_overview(database_path, hours))

    @admin.post("/api/report")
    def report_api():
        payload = request.get_json(silent=True)
        days = payload.get("days") if isinstance(payload, dict) else None
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 30:
            return jsonify(error="Укажите от 1 до 30 календарных дней."), 400
        if not report_lock.acquire(blocking=False):
            return jsonify(error="Отчёт уже генерируется. Дождитесь завершения."), 409
        try:
            result = generate_report(days, log_path, database_path)
        except ReportError as error:
            logger.warning("Admin report failed | error=%s", error)
            return jsonify(error=str(error)), 400
        finally:
            report_lock.release()
        return jsonify(result)

    @admin.get("/api/sessions")
    def sessions_api():
        return jsonify(sessions=list_sessions(database_path))

    @admin.get("/api/sessions/<path:session_id>/messages")
    def messages_api(session_id):
        session_id = _admin_session_id(session_id)
        data = admin_session_messages(database_path, session_id,
                                      include_archived=request.args.get("archived") == "1")
        if data is None:
            return jsonify(error="Session not found."), 404
        data["context_tokens"] = (
            data.pop("context_characters") + len(system_instruction)
        ) // CHARACTERS_PER_TOKEN
        return jsonify(session_id=session_id, **data)

    @admin.post("/api/sessions/<path:session_id>/messages")
    def send_message_api(session_id):
        session_id = _session_id(session_id)
        payload = request.get_json(silent=True)
        message = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(message, str) or not message.strip():
            return jsonify(error="Message must not be empty."), 400
        message = message.strip()
        if len(message) > MAX_MANUAL_MESSAGE_LENGTH:
            return jsonify(error="Message is too long."), 400
        if not session_exists(database_path, session_id):
            return jsonify(error="Session not found."), 404
        try:
            send_fn(session_id, message)
            message_id = save_model_message(database_path, session_id, message)
        except AdminDashboardError as error:
            return jsonify(error=str(error)), 400
        except (DatabaseError, TelegramError, WhatsAppError):
            logger.exception("Manual message delivery failed | session=%s", session_id)
            return jsonify(error="Message could not be sent."), 502
        log_conversation(session_id, "MANUAL", flatten_text(message))
        return jsonify(id=message_id, status="sent"), 201

    @admin.post("/api/sessions/<path:session_id>/reset")
    def reset_api(session_id):
        session_id = _admin_session_id(session_id)
        if not session_exists(database_path, session_id):
            return jsonify(error="Session not found."), 404
        if coordinator is None:
            reset_fn(session_id)
        else:
            coordinator.reset_session(session_id, lambda: reset_fn(session_id))
        log_conversation(session_id, "SYSTEM", "Session reset by admin")
        return jsonify(status="reset")

    @admin.get("/api/blocked")
    def blocked_api():
        return jsonify(blocked=list_blocked_sessions(database_path))

    @admin.post("/api/blocked")
    def block_api():
        payload = request.get_json(silent=True)
        session_id = payload.get("session_id") if isinstance(payload, dict) else None
        reason = payload.get("reason") if isinstance(payload, dict) else None
        session_id = _admin_session_id(session_id)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
            return jsonify(error="Reason must be 1–200 characters."), 400
        if not session_exists(database_path, session_id):
            return jsonify(error="Session not found."), 404
        block_session(database_path, session_id, reason.strip())
        return jsonify(status="blocked"), 201

    @admin.delete("/api/blocked/<path:session_id>")
    def unblock_api(session_id):
        unblock_session(database_path, _admin_session_id(session_id))
        return jsonify(status="unblocked")

    @admin.get("/api/logs")
    def logs_api():
        try:
            offset = int(request.args.get("offset", "0"))
        except ValueError:
            return jsonify(error="Invalid offset."), 400
        if offset < 0:
            return jsonify(error="Invalid offset."), 400
        try:
            with Path(log_path).open("rb") as file:
                size = file.seek(0, 2)
                if offset > size:
                    offset = 0
                if offset == 0:
                    offset = max(0, size - 65536)
                    file.seek(offset)
                    if offset:
                        file.readline()
                else:
                    file.seek(offset)
                start = file.tell()
                data = file.read(65536)
                if len(data) == 65536 and not data.endswith(b"\n"):
                    last_newline = data.rfind(b"\n")
                    if last_newline >= 0:
                        data = data[:last_newline + 1]
                next_offset = start + len(data)
        except FileNotFoundError:
            return jsonify(lines=[], offset=0)
        return jsonify(lines=data.decode("utf-8", errors="replace").splitlines(), offset=next_offset)

    @admin.get("/api/settings")
    def settings_api():
        return jsonify(config=editable_config())

    @admin.put("/api/settings")
    def save_settings_api():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("config"), dict):
            return jsonify(error="Invalid configuration body."), 400
        try:
            config = save_config(payload["config"])
        except ConfigError as error:
            return jsonify(error=str(error)), 400
        return jsonify(config=config, status="saved")

    @admin.errorhandler(AdminDashboardError)
    def bad_input(error):
        return jsonify(error=str(error)), 400

    @admin.errorhandler(DatabaseError)
    def database_error(error):
        logger.error("Admin database operation failed: %s", error)
        return jsonify(error="Database is temporarily unavailable."), 500

    app.register_blueprint(admin)
    return app


def build_channel_sender():
    def send_to_channel(session_id, text):
        channel, recipient = session_id.split(":", 1)
        if channel == "whatsapp":
            send_text_message(require_setting("WHATSAPP_ACCESS_TOKEN"),
                              require_setting("WHATSAPP_PHONE_NUMBER_ID"),
                              recipient, text,
                              os.getenv("WHATSAPP_GRAPH_API_VERSION", "v25.0"))
        elif channel == "telegram":
            send_telegram_message(require_setting("TELEGRAM_BOT_TOKEN"),
                                  int(recipient), text)
        else:
            raise AdminDashboardError("Unsupported channel.")
    return send_to_channel


def require_setting(name):
    value = os.getenv(name)
    if not value:
        raise AdminDashboardError(f"{name} is not configured.")
    return value


def create_admin_app(database_path, send_fn=None):
    """Factory used by tests; runner mounts routes on the webhook app."""
    app = Flask(__name__)
    return register_admin_routes(app, database_path, send_fn=send_fn)
