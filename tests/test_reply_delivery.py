import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_reply import AgentReply
from reply_delivery import ReplyDeliveryError, deliver_agent_reply


class ReplyDeliveryTests(unittest.TestCase):
    def test_delivers_customer_and_operator_messages_separately(self):
        customer_messages = []
        operator_messages = []

        deliver_agent_reply(
            "destination",
            "whatsapp:123",
            AgentReply("Customer text", "Operator summary"),
            lambda destination, text: customer_messages.append((destination, text)),
            lambda session_id, text: operator_messages.append((session_id, text)),
        )

        self.assertEqual(customer_messages, [("destination", "Customer text")])
        self.assertEqual(
            operator_messages,
            [("whatsapp:123", "Operator summary")],
        )

    def test_rejects_an_invalid_agent_reply(self):
        with self.assertRaisesRegex(ReplyDeliveryError, "invalid reply"):
            deliver_agent_reply(
                "destination",
                "whatsapp:123",
                "plain text",
                lambda destination, text: None,
                lambda session_id, text: None,
            )


if __name__ == "__main__":
    unittest.main()
