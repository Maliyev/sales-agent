from flask import Flask, Response, request

from whatsapp_webhook import (
    WhatsAppWebhookError,
    get_verification_challenge,
    is_valid_signature,
    parse_text_messages,
)


WEBHOOK_PATH = "/webhooks/whatsapp"


def create_webhook_app(verify_token, app_secret, message_handler):
    if not isinstance(verify_token, str) or not verify_token:
        raise ValueError("verify_token must not be empty.")
    if not isinstance(app_secret, str) or not app_secret:
        raise ValueError("app_secret must not be empty.")
    if not callable(message_handler):
        raise ValueError("message_handler must be callable.")

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get(WEBHOOK_PATH)
    def verify_webhook():
        try:
            challenge = get_verification_challenge(request.args, verify_token)
        except WhatsAppWebhookError:
            return Response("Forbidden", status=403, mimetype="text/plain")
        return Response(challenge, status=200, mimetype="text/plain")

    @app.post(WEBHOOK_PATH)
    def receive_webhook():
        raw_body = request.get_data(cache=True)
        signature = request.headers.get("X-Hub-Signature-256")
        if not is_valid_signature(raw_body, signature, app_secret):
            return Response("Unauthorized", status=401, mimetype="text/plain")

        payload = request.get_json(silent=True)
        try:
            messages = parse_text_messages(payload)
        except WhatsAppWebhookError:
            return Response("Invalid payload", status=400, mimetype="text/plain")

        for message in messages:
            message_handler(message)

        return Response(status=200)

    return app
