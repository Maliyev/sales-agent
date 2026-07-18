from pathlib import Path
import sys
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from chat import send_message


class ChatTests(unittest.TestCase):
    def test_send_message_keeps_user_and_model_messages(self):
        history = []

        reply = send_message(history, "Hello", lambda messages: "Hi there")

        self.assertEqual(reply, "Hi there")
        self.assertEqual(
            history,
            [
                {"role": "user", "parts": [{"text": "Hello"}]},
                {"role": "model", "parts": [{"text": "Hi there"}]},
            ],
        )

