import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from whatsapp_client import WhatsAppError, send_text_message


class WhatsAppClientTests(unittest.TestCase):
    def test_sends_a_text_message_through_graph_api(self):
        response = Mock()
        response.json.return_value = {"messages": [{"id": "wamid.123"}]}
        session = Mock()
        session.post.return_value = response

        message_id = send_text_message(
            "secret-token",
            "1242528055613330",
            "+994501234567",
            "Salam",
            session=session,
        )

        self.assertEqual(message_id, "wamid.123")
        session.post.assert_called_once_with(
            "https://graph.facebook.com/v25.0/1242528055613330/messages",
            headers={
                "Authorization": "Bearer secret-token",
                "Content-Type": "application/json",
            },
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": "994501234567",
                "type": "text",
                "text": {"preview_url": False, "body": "Salam"},
            },
            timeout=15,
        )

    def test_wraps_http_errors_without_exposing_the_token(self):
        session = Mock()
        session.post.side_effect = requests.RequestException("network error")

        with self.assertRaisesRegex(WhatsAppError, "send request failed") as error:
            send_text_message(
                "secret-token",
                "1242528055613330",
                "994501234567",
                "Salam",
                session=session,
            )

        self.assertNotIn("secret-token", str(error.exception))

    def test_rejects_an_invalid_recipient(self):
        with self.assertRaisesRegex(WhatsAppError, "only digits"):
            send_text_message(
                "token",
                "1242528055613330",
                "not-a-number",
                "Salam",
            )

    def test_rejects_an_invalid_api_response(self):
        response = Mock()
        response.json.return_value = {"messages": []}
        session = Mock()
        session.post.return_value = response

        with self.assertRaisesRegex(WhatsAppError, "invalid send response"):
            send_text_message(
                "token",
                "1242528055613330",
                "994501234567",
                "Salam",
                session=session,
            )


if __name__ == "__main__":
    unittest.main()
