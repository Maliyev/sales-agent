from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from message_service import generate_customer_reply, reply_to_customer


class MessageServiceTests(unittest.TestCase):
    @patch("message_service.save_exchange")
    @patch("message_service.get_agent_reply", return_value="Draft reply")
    @patch("message_service.load_history", return_value=[])
    def test_generates_a_reply_without_saving_it(
        self,
        load_history,
        get_agent_reply,
        save_exchange,
    ):
        reply = generate_customer_reply(
            "database.db",
            "telegram:123",
            "Hello",
            "model",
            "key",
            "system",
            "selection",
            "response",
        )

        self.assertEqual(reply, "Draft reply")
        load_history.assert_called_once()
        get_agent_reply.assert_called_once()
        save_exchange.assert_not_called()

    @patch("message_service.save_exchange")
    @patch("message_service.get_agent_reply", return_value="Agent reply")
    @patch("message_service.load_history", return_value=[{"role": "user"}])
    def test_loads_history_and_saves_only_the_final_exchange(
        self,
        load_history,
        get_agent_reply,
        save_exchange,
    ):
        reply = reply_to_customer(
            "database.db",
            "telegram:123",
            "Hello",
            "model",
            "key",
            "system",
            "selection",
            "response",
        )

        self.assertEqual(reply, "Agent reply")
        load_history.assert_called_once_with("database.db", "telegram:123")
        get_agent_reply.assert_called_once()
        save_exchange.assert_called_once_with(
            "database.db",
            "telegram:123",
            "Hello",
            "Agent reply",
        )


if __name__ == "__main__":
    unittest.main()
