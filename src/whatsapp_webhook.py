from dataclasses import dataclass
import hashlib
import hmac


class WhatsAppWebhookError(RuntimeError):
    pass


@dataclass(frozen=True)
class WhatsAppTextMessage:
    message_id: str
    sender_id: str
    text: str
    phone_number_id: str | None = None


def get_verification_challenge(query, expected_token):
    if not isinstance(expected_token, str) or not expected_token:
        raise WhatsAppWebhookError("Webhook verify token is not configured.")

    mode = query.get("hub.mode")
    token = query.get("hub.verify_token")
    challenge = query.get("hub.challenge")

    if mode != "subscribe" or token != expected_token:
        raise WhatsAppWebhookError("Webhook verification was rejected.")
    if not isinstance(challenge, str) or not challenge:
        raise WhatsAppWebhookError("Webhook challenge is missing.")

    return challenge


def is_valid_signature(raw_body, signature_header, app_secret):
    if not isinstance(raw_body, bytes):
        return False
    if not isinstance(signature_header, str):
        return False
    if not isinstance(app_secret, str) or not app_secret:
        return False

    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def parse_text_messages(payload):
    if not isinstance(payload, dict):
        raise WhatsAppWebhookError("Webhook payload must be a JSON object.")
    if payload.get("object") != "whatsapp_business_account":
        return []

    parsed_messages = []
    seen_ids = set()

    for entry in _as_list(payload.get("entry")):
        for change in _as_list(entry.get("changes")):
            if change.get("field") != "messages":
                continue

            value = change.get("value")
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata")
            phone_number_id = None
            if isinstance(metadata, dict):
                candidate = metadata.get("phone_number_id")
                if isinstance(candidate, str) and candidate:
                    phone_number_id = candidate

            for message in _as_list(value.get("messages")):
                parsed = _parse_text_message(message, phone_number_id)
                if parsed is None or parsed.message_id in seen_ids:
                    continue
                seen_ids.add(parsed.message_id)
                parsed_messages.append(parsed)

    return parsed_messages


def _parse_text_message(message, phone_number_id):
    if message.get("type") != "text":
        return None

    message_id = message.get("id")
    sender_id = message.get("from")
    text_data = message.get("text")
    text = text_data.get("body") if isinstance(text_data, dict) else None

    if not isinstance(message_id, str) or not message_id:
        return None
    if not isinstance(sender_id, str) or not sender_id:
        return None
    if not isinstance(text, str) or not text.strip():
        return None

    return WhatsAppTextMessage(
        message_id=message_id,
        sender_id=sender_id,
        text=text.strip(),
        phone_number_id=phone_number_id,
    )


def _as_list(value):
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
