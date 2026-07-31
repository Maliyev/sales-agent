import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from whatsapp_bot import handle_incoming_message
from whatsapp_webhook import WhatsAppTextMessage


class WhatsAppBotTests(unittest.TestCase):
    def setUp(self):
        self.message = WhatsAppTextMessage(
            message_id="wamid.123",
            sender_id="994501234567",
            text="Arduino Uno",
            phone_number_id="1242528055613330",
        )

    def test_submits_a_new_message_to_a_separate_whatsapp_session(self):
        claim = Mock(return_value=True)
        release = Mock()
        allow = Mock(return_value=True)
        submit = Mock()

        handled = handle_incoming_message(
            self.message,
            "1242528055613330",
            claim,
            release,
            allow,
            submit,
        )

        self.assertTrue(handled)
        claim.assert_called_once_with("wamid.123", "994501234567")
        allow.assert_called_once_with("whatsapp:994501234567")
        submit.assert_called_once_with(
            "whatsapp:994501234567",
            "Arduino Uno",
            "994501234567",
        )
        release.assert_not_called()

    def test_ignores_a_repeated_message(self):
        submit = Mock()

        handled = handle_incoming_message(
            self.message,
            "1242528055613330",
            Mock(return_value=False),
            Mock(),
            Mock(),
            submit,
        )

        self.assertFalse(handled)
        submit.assert_not_called()

    def test_ignores_an_event_for_another_phone_number(self):
        claim = Mock()

        handled = handle_incoming_message(
            self.message,
            "different-phone-id",
            claim,
            Mock(),
            Mock(),
            Mock(),
        )

        self.assertFalse(handled)
        claim.assert_not_called()

    def test_blocked_session_is_not_submitted(self):
        submit = Mock()

        handled = handle_incoming_message(
            self.message,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=False),
            submit,
        )

        self.assertFalse(handled)
        submit.assert_not_called()

    def test_releases_the_message_if_submission_fails(self):
        release = Mock()

        with self.assertRaisesRegex(RuntimeError, "queue failed"):
            handle_incoming_message(
                self.message,
                "1242528055613330",
                Mock(return_value=True),
                release,
                Mock(return_value=True),
                Mock(side_effect=RuntimeError("queue failed")),
            )

        release.assert_called_once_with("wamid.123")


if __name__ == "__main__":
    unittest.main()
