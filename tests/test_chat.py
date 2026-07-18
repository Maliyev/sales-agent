from pathlib import Path
import sys
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from chat import send_message
from sessions import get_history, reset_history


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

    def test_each_session_has_its_own_history(self):
        sessions = {}

        magerram_history = get_history(sessions, "terminal:magerram")
        test_history = get_history(sessions, "terminal:test_client")

        magerram_history.append({"role": "user", "parts": [{"text": "Hello"}]})

        self.assertEqual(len(magerram_history), 1)
        self.assertEqual(test_history, [])

    def test_reset_clears_only_one_session(self):
        sessions = {
            "terminal:magerram": [{"role": "user", "parts": [{"text": "Hello"}]}],
            "terminal:test_client": [{"role": "user", "parts": [{"text": "Hi"}]}],
        }

        reset_history(sessions, "terminal:magerram")

        self.assertEqual(sessions["terminal:magerram"], [])
        self.assertEqual(len(sessions["terminal:test_client"]), 1)
