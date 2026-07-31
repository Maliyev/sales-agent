import re

import requests


DEFAULT_TIMEOUT_SECONDS = 15
MAX_TEXT_LENGTH = 4096


class WhatsAppError(RuntimeError):
    pass


def send_text_message(
    access_token,
    phone_number_id,
    recipient,
    text,
    api_version="v25.0",
    session=requests,
):
    access_token = _require_text(access_token, "access token")
    phone_number_id = _require_digits(phone_number_id, "phone number ID")
    recipient = _normalize_recipient(recipient)
    text = _require_text(text, "message text")
    api_version = _validate_api_version(api_version)

    if len(text) > MAX_TEXT_LENGTH:
        raise WhatsAppError(
            f"WhatsApp message is longer than {MAX_TEXT_LENGTH} characters."
        )

    url = (
        f"https://graph.facebook.com/{api_version}/"
        f"{phone_number_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text,
        },
    }

    try:
        response = session.post(
            url,
            headers=headers,
            json=payload,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as error:
        raise WhatsAppError("WhatsApp send request failed.") from error

    try:
        message_id = data["messages"][0]["id"]
    except (KeyError, IndexError, TypeError) as error:
        raise WhatsAppError("WhatsApp returned an invalid send response.") from error

    if not isinstance(message_id, str) or not message_id.strip():
        raise WhatsAppError("WhatsApp returned an invalid message ID.")

    return message_id


def _normalize_recipient(recipient):
    recipient = _require_text(recipient, "recipient")
    if recipient.startswith("+"):
        recipient = recipient[1:]
    return _require_digits(recipient, "recipient")


def _validate_api_version(api_version):
    api_version = _require_text(api_version, "Graph API version")
    if re.fullmatch(r"v\d+\.\d+", api_version) is None:
        raise WhatsAppError("Graph API version must look like v25.0.")
    return api_version


def _require_digits(value, name):
    value = _require_text(value, name)
    if not value.isdigit():
        raise WhatsAppError(f"WhatsApp {name} must contain only digits.")
    return value


def _require_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise WhatsAppError(f"WhatsApp {name} must not be empty.")
    return value.strip()
