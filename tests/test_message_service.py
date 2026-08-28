from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from message_service import generate_customer_reply, reply_to_customer
from agent_reply import AgentReply
from token_limiter import SessionContextTooLargeError


class MessageServiceTests(unittest.TestCase):
    @patch("message_service.save_model_message")
    @patch("message_service.update_messages_status")
    @patch("message_service.insert_incoming_message", return_value=7)
    @patch(
        "message_service.get_agent_reply",
        return_value=AgentReply("Draft reply"),
    )
    @patch("message_service.load_history", return_value=[])
    def test_generates_a_reply_and_marks_failure_when_generation_fails(
        self,
        load_history,
        get_agent_reply,
        insert_incoming_message,
        update_messages_status,
        save_model_message,
    ):
        get_agent_reply.side_effect = RuntimeError("Gemini down")

        with self.assertRaises(RuntimeError):
            reply_to_customer(
                "database.db",
                "telegram:123",
                "Hello",
                "model",
                "key",
                "system",
                "selection",
                "response",
            )

        insert_incoming_message.assert_called_once_with(
            "database.db",
            "telegram:123",
            "Hello",
        )
        save_model_message.assert_not_called()
        update_messages_status.assert_called_once_with(
            "database.db",
            [7],
            "FAILED_LLM_API",
        )

    @patch("message_service.save_model_message", return_value=9)
    @patch("message_service.update_messages_status")
    @patch("message_service.insert_incoming_message", return_value=8)
    @patch(
        "message_service.get_agent_reply",
        return_value=AgentReply("Agent reply", "Operator summary"),
    )
    @patch("message_service.load_history", return_value=[{"role": "user"}])
    def test_stores_the_message_first_and_returns_the_turn_ids(
        self,
        load_history,
        get_agent_reply,
        insert_incoming_message,
        update_messages_status,
        save_model_message,
    ):
        reply, message_ids = reply_to_customer(
            "database.db",
            "telegram:123",
            "Hello",
            "model",
            "key",
            "system",
            "selection",
            "response",
        )

        self.assertEqual(reply, AgentReply("Agent reply", "Operator summary"))
        self.assertEqual(message_ids, [8, 9])
        load_history.assert_called_once_with("database.db", "telegram:123")
        get_agent_reply.assert_called_once()
        self.assertEqual(
            get_agent_reply.call_args.kwargs["in_reply_to_message_id"],
            8,
        )
        save_model_message.assert_called_once_with(
            "database.db",
            "telegram:123",
            "Agent reply",
            status="RESPONSE_READY",
        )
        update_messages_status.assert_not_called()


class ContextOverflowTests(unittest.TestCase):
    @patch("message_service.log_conversation")
    @patch("message_service.reset_history")
    @patch("message_service.get_context_overflow_auto_reset", return_value=True)
    @patch("message_service.load_history", return_value=[])
    @patch("message_service.get_agent_reply", return_value=AgentReply("Fresh reply"))
    def test_resets_the_context_and_retries_when_it_is_too_large(
        self,
        get_agent_reply,
        load_history,
        get_context_overflow_auto_reset,
        reset_history,
        log_conversation,
    ):
        get_agent_reply.side_effect = [
            SessionContextTooLargeError("Estimated 1500 tokens exceed the limit"),
            AgentReply("Fresh reply"),
        ]

        reply = generate_customer_reply(
            "database.db",
            "telegram:123",
            "Hello",
            "model",
            "key",
            "system",
            "selection",
            "response",
            in_reply_to_message_id=8,
        )

        reset_history.assert_called_once_with("database.db", "telegram:123")
        self.assertEqual(load_history.call_count, 2)
        self.assertEqual(get_agent_reply.call_count, 2)
        self.assertEqual(
            get_agent_reply.call_args.kwargs["in_reply_to_message_id"],
            8,
        )
        self.assertEqual(
            reply,
            AgentReply(
                "Your conversation became too long, so we had to reset it.\n\nFresh reply"
            ),
        )

    @patch("message_service.reset_history")
    @patch("message_service.get_context_overflow_auto_reset", return_value=False)
    @patch("message_service.load_history", return_value=[])
    @patch("message_service.get_agent_reply")
    def test_propagates_the_error_when_auto_reset_is_disabled(
        self,
        get_agent_reply,
        load_history,
        get_context_overflow_auto_reset,
        reset_history,
    ):
        get_agent_reply.side_effect = SessionContextTooLargeError("too large")

        with self.assertRaises(SessionContextTooLargeError):
            generate_customer_reply(
                "database.db",
                "telegram:123",
                "Hello",
                "model",
                "key",
                "system",
                "selection",
                "response",
            )

        reset_history.assert_not_called()
        get_agent_reply.assert_called_once()


if __name__ == "__main__":
    unittest.main()
