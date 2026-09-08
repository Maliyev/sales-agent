import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from whatsapp_server import create_webhook_app
from whatsapp_webhook import (
    WhatsAppDocumentMessage,
    WhatsAppImageMessage,
    WhatsAppTextMessage,
    WhatsAppWebhookError,
    get_verification_challenge,
    is_valid_signature,
    parse_messages,
)


def create_payload():
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {
                                "phone_number_id": "1242528055613330",
                            },
                            "messages": [
                                {
                                    "from": "994501234567",
                                    "id": "wamid.123",
                                    "type": "text",
                                    "text": {"body": " Salam "},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }


class WhatsAppWebhookTests(unittest.TestCase):
    def test_returns_the_meta_verification_challenge(self):
        challenge = get_verification_challenge(
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "12345",
            },
            "verify-me",
        )

        self.assertEqual(challenge, "12345")

    def test_rejects_the_wrong_verification_token(self):
        with self.assertRaisesRegex(WhatsAppWebhookError, "rejected"):
            get_verification_challenge(
                {
                    "hub.mode": "subscribe",
                    "hub.verify_token": "wrong",
                    "hub.challenge": "12345",
                },
                "verify-me",
            )

    def test_validates_the_meta_signature(self):
        body = b'{"hello":"world"}'
        signature = "sha256=" + hmac.new(
            b"app-secret",
            body,
            hashlib.sha256,
        ).hexdigest()

        self.assertTrue(is_valid_signature(body, signature, "app-secret"))
        self.assertFalse(is_valid_signature(body, signature, "wrong-secret"))

    def test_parses_text_messages(self):
        self.assertEqual(
            parse_messages(create_payload()),
            [
                WhatsAppTextMessage(
                    message_id="wamid.123",
                    sender_id="994501234567",
                    text="Salam",
                    phone_number_id="1242528055613330",
                )
            ],
        )

    def test_ignores_status_updates_and_non_text_messages(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.image",
                "type": "image",
                "image": {"id": "image-id"},
            }
        ]
        value["statuses"] = [{"id": "wamid.sent", "status": "sent"}]

        self.assertEqual(parse_messages(payload), [])

    def test_parses_a_document_message(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.doc",
                "type": "document",
                "document": {
                    "id": "media-9",
                    "filename": " bom.xlsx ",
                    "caption": " Check these ",
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                },
            }
        ]

        self.assertEqual(
            parse_messages(payload),
            [
                WhatsAppDocumentMessage(
                    message_id="wamid.doc",
                    sender_id="994501234567",
                    media_id="media-9",
                    filename="bom.xlsx",
                    caption="Check these",
                    phone_number_id="1242528055613330",
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            ],
        )

    def test_parses_a_document_message_without_a_caption(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.doc",
                "type": "document",
                "document": {"id": "media-9", "filename": "bom.xlsx"},
            }
        ]

        parsed = parse_messages(payload)

        self.assertIsNone(parsed[0].caption)

    def test_ignores_an_invalid_document_message(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.doc1",
                "type": "document",
                "document": {"filename": "bom.xlsx"},
            },
            {
                "from": "994501234567",
                "id": "wamid.doc2",
                "type": "document",
                "document": {"id": "media-9"},
            },
        ]

        self.assertEqual(parse_messages(payload), [])

    def test_parses_text_and_document_messages_together(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.123",
                "type": "text",
                "text": {"body": "Salam"},
            },
            {
                "from": "994501234567",
                "id": "wamid.doc",
                "type": "document",
                "document": {"id": "media-9", "filename": "bom.xlsx"},
            },
        ]

        parsed = parse_messages(payload)

        self.assertEqual([type(message) for message in parsed],
                         [WhatsAppTextMessage, WhatsAppDocumentMessage])

    def test_parses_an_image_message(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.img",
                "type": "image",
                "image": {
                    "id": " media-5 ",
                    "mime_type": " image/jpeg ",
                    "caption": " What is this? ",
                },
            }
        ]

        self.assertEqual(
            parse_messages(payload),
            [
                WhatsAppImageMessage(
                    message_id="wamid.img",
                    sender_id="994501234567",
                    media_id="media-5",
                    mime_type="image/jpeg",
                    caption="What is this?",
                    phone_number_id="1242528055613330",
                )
            ],
        )

    def test_parses_an_image_message_without_a_caption(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.img",
                "type": "image",
                "image": {"id": "media-5", "mime_type": "image/png"},
            }
        ]

        parsed = parse_messages(payload)

        self.assertIsNone(parsed[0].caption)

    def test_ignores_an_invalid_image_message(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.img1",
                "type": "image",
                "image": {"mime_type": "image/jpeg"},
            },
            {
                "from": "994501234567",
                "id": "wamid.img2",
                "type": "image",
                "image": {"id": "media-5"},
            },
        ]

        self.assertEqual(parse_messages(payload), [])

    def test_parses_text_image_and_document_messages_together(self):
        payload = create_payload()
        value = payload["entry"][0]["changes"][0]["value"]
        value["messages"] = [
            {
                "from": "994501234567",
                "id": "wamid.123",
                "type": "text",
                "text": {"body": "Salam"},
            },
            {
                "from": "994501234567",
                "id": "wamid.img",
                "type": "image",
                "image": {"id": "media-5", "mime_type": "image/jpeg"},
            },
            {
                "from": "994501234567",
                "id": "wamid.doc",
                "type": "document",
                "document": {"id": "media-9", "filename": "bom.xlsx"},
            },
        ]

        parsed = parse_messages(payload)

        self.assertEqual(
            [type(message) for message in parsed],
            [WhatsAppTextMessage, WhatsAppImageMessage, WhatsAppDocumentMessage],
        )

    def test_webhook_app_verifies_and_receives_signed_payloads(self):
        received = []
        app = create_webhook_app("verify-me", "app-secret", received.append)
        client = app.test_client()

        verification = client.get(
            "/webhooks/whatsapp",
            query_string={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "12345",
            },
        )
        self.assertEqual(verification.status_code, 200)
        self.assertEqual(verification.get_data(as_text=True), "12345")

        body = json.dumps(create_payload(), separators=(",", ":")).encode()
        signature = "sha256=" + hmac.new(
            b"app-secret",
            body,
            hashlib.sha256,
        ).hexdigest()
        delivery = client.post(
            "/webhooks/whatsapp",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": signature},
        )

        self.assertEqual(delivery.status_code, 200)
        self.assertEqual(received, parse_messages(create_payload()))

    def test_webhook_app_rejects_an_invalid_signature(self):
        app = create_webhook_app("verify-me", "app-secret", lambda message: None)
        response = app.test_client().post(
            "/webhooks/whatsapp",
            json=create_payload(),
            headers={"X-Hub-Signature-256": "sha256=invalid"},
        )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
