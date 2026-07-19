from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

import requests

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot import (
    MAX_MESSAGE_LENGTH,
    TelegramError,
    get_updates,
    handle_update,
    send_message,
    split_message,
)


class TelegramBotTests(unittest.TestCase):
    def test_regular_message_uses_a_separate_telegram_session(self):
        replies = []
        sent = []

        handle_update(
            {"message": {"chat": {"id": 123}, "text": "Arduino Uno"}},
            lambda session_id, text: replies.append((session_id, text)) or "Found",
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
        )

        self.assertEqual(replies, [("telegram:123", "Arduino Uno")])
        self.assertEqual(sent, [(123, "Found")])

    def test_reset_clears_only_the_current_telegram_session(self):
        resets = []
        sent = []

        handle_update(
            {"message": {"chat": {"id": 456}, "text": "/reset@demo_bot"}},
            lambda session_id, text: self.fail("Agent should not be called"),
            resets.append,
            lambda chat_id, text: sent.append((chat_id, text)),
        )

        self.assertEqual(resets, ["telegram:456"])
        self.assertEqual(sent[0][0], 456)
        self.assertIn("silindi", sent[0][1])

    def test_non_text_message_does_not_call_the_agent(self):
        sent = []

        handle_update(
            {"message": {"chat": {"id": 7}, "photo": []}},
            lambda session_id, text: self.fail("Agent should not be called"),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
        )

        self.assertEqual(sent[0][0], 7)

    def test_splits_long_replies_before_sending(self):
        text = "a" * (MAX_MESSAGE_LENGTH * 2 + 1)

        chunks = split_message(text)

        self.assertEqual([len(chunk) for chunk in chunks], [4000, 4000, 1])

    def test_get_updates_uses_offset_and_long_polling(self):
        response = Mock()
        response.json.return_value = {"ok": True, "result": []}
        session = Mock()
        session.get.return_value = response

        updates = get_updates("secret-token", offset=12, session=session)

        self.assertEqual(updates, [])
        request = session.get.call_args
        self.assertEqual(request.kwargs["params"]["offset"], 12)
        self.assertGreater(request.kwargs["timeout"], 25)

    def test_send_message_sends_every_chunk(self):
        response = Mock()
        response.json.return_value = {"ok": True, "result": {}}
        session = Mock()
        session.post.return_value = response

        send_message(
            "secret-token",
            42,
            "a" * (MAX_MESSAGE_LENGTH + 1),
            session=session,
        )

        self.assertEqual(session.post.call_count, 2)

    def test_request_error_does_not_put_the_token_in_the_message(self):
        session = Mock()
        session.get.side_effect = requests.ConnectionError("network down")

        with self.assertRaises(TelegramError) as result:
            get_updates("very-secret-token", session=session)

        self.assertNotIn("very-secret-token", str(result.exception))


if __name__ == "__main__":
    unittest.main()
