from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from message_service import generate_customer_reply, reply_to_customer
from agent_reply import AgentReply
from compaction import CompactionError
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

    @patch("message_service.save_model_message", return_value=9)
    @patch("message_service.insert_incoming_message", return_value=8)
    @patch(
        "message_service.get_agent_reply",
        return_value=AgentReply("Agent reply"),
    )
    @patch("message_service.load_history", return_value=[{"role": "user"}])
    def test_passes_the_list_start_notifier_to_the_agent(
        self,
        load_history,
        get_agent_reply,
        insert_incoming_message,
        save_model_message,
    ):
        notify = Mock()

        generate_customer_reply(
            "database.db",
            "telegram:123",
            "Hello",
            "model",
            "key",
            "system",
            "selection",
            "response",
            in_reply_to_message_id=8,
            list_start_notify_fn=notify,
        )

        self.assertEqual(
            get_agent_reply.call_args.kwargs["list_start_notify_fn"],
            notify,
        )


class ContextOverflowTests(unittest.TestCase):
    @patch("message_service.get_context_overflow_auto_compaction", return_value=False)
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
        get_context_overflow_auto_compaction,
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

    @patch("message_service.get_context_overflow_auto_compaction", return_value=False)
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
        get_context_overflow_auto_compaction,
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


class ContextCompactionTests(unittest.TestCase):
    @staticmethod
    def reply():
        return generate_customer_reply(
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

    @patch("message_service.get_compaction_model", return_value="compactor-model")
    @patch("message_service.get_context_overflow_auto_reset", return_value=False)
    @patch("message_service.get_context_overflow_auto_compaction", return_value=True)
    @patch("message_service.load_history", return_value=[])
    @patch("message_service.compact_history")
    @patch("message_service.get_agent_reply", return_value=AgentReply("Fresh reply"))
    def test_compacts_the_context_and_retries_without_a_notice(
        self,
        get_agent_reply,
        compact_history,
        load_history,
        get_context_overflow_auto_compaction,
        get_context_overflow_auto_reset,
        get_compaction_model,
    ):
        get_agent_reply.side_effect = [
            SessionContextTooLargeError("too large"),
            AgentReply("Fresh reply"),
        ]

        reply = self.reply()

        compact_history.assert_called_once_with(
            "database.db",
            "telegram:123",
            model="compactor-model",
            api_key="key",
            in_reply_to_message_id=8,
        )
        self.assertEqual(get_agent_reply.call_count, 2)
        self.assertEqual(
            get_agent_reply.call_args.kwargs["in_reply_to_message_id"],
            8,
        )
        self.assertEqual(reply, AgentReply("Fresh reply"))

    @patch("message_service.get_compaction_model", return_value="compactor-model")
    @patch("message_service.log_conversation")
    @patch("message_service.reset_history")
    @patch("message_service.get_context_overflow_auto_reset", return_value=True)
    @patch("message_service.get_context_overflow_auto_compaction", return_value=True)
    @patch("message_service.load_history", return_value=[])
    @patch("message_service.compact_history")
    @patch("message_service.get_agent_reply", return_value=AgentReply("Fresh reply"))
    def test_falls_back_to_reset_when_compaction_fails(
        self,
        get_agent_reply,
        compact_history,
        load_history,
        get_context_overflow_auto_compaction,
        get_context_overflow_auto_reset,
        reset_history,
        log_conversation,
        get_compaction_model,
    ):
        get_agent_reply.side_effect = [
            SessionContextTooLargeError("too large"),
            AgentReply("Fresh reply"),
        ]
        compact_history.side_effect = CompactionError("Gemini down")

        reply = self.reply()

        compact_history.assert_called_once()
        reset_history.assert_called_once_with("database.db", "telegram:123")
        self.assertEqual(
            reply,
            AgentReply(
                "Your conversation became too long, so we had to reset it.\n\nFresh reply"
            ),
        )

    @patch("message_service.get_compaction_model", return_value="compactor-model")
    @patch("message_service.reset_history")
    @patch("message_service.get_context_overflow_auto_reset", return_value=False)
    @patch("message_service.get_context_overflow_auto_compaction", return_value=True)
    @patch("message_service.load_history", return_value=[])
    @patch("message_service.compact_history")
    @patch("message_service.get_agent_reply")
    def test_propagates_when_compaction_fails_and_reset_is_disabled(
        self,
        get_agent_reply,
        compact_history,
        load_history,
        get_context_overflow_auto_compaction,
        get_context_overflow_auto_reset,
        reset_history,
        get_compaction_model,
    ):
        get_agent_reply.side_effect = SessionContextTooLargeError("too large")
        compact_history.side_effect = CompactionError("Gemini down")

        with self.assertRaises(SessionContextTooLargeError):
            self.reply()

        compact_history.assert_called_once()
        reset_history.assert_not_called()
        get_agent_reply.assert_called_once()

    @patch("message_service.log_conversation")
    @patch("message_service.reset_history")
    @patch("message_service.get_context_overflow_auto_reset", return_value=True)
    @patch("message_service.get_context_overflow_auto_compaction", return_value=True)
    @patch("message_service.load_history", return_value=[])
    @patch("message_service.compact_history")
    @patch("message_service.get_agent_reply", return_value=AgentReply("Last reply"))
    def test_falls_back_to_reset_when_the_compacted_context_is_still_too_large(
        self,
        get_agent_reply,
        compact_history,
        load_history,
        get_context_overflow_auto_compaction,
        get_context_overflow_auto_reset,
        reset_history,
        log_conversation,
    ):
        get_agent_reply.side_effect = [
            SessionContextTooLargeError("too large"),
            SessionContextTooLargeError("still too large"),
            AgentReply("Last reply"),
        ]

        reply = self.reply()

        compact_history.assert_called_once()
        reset_history.assert_called_once_with("database.db", "telegram:123")
        self.assertEqual(get_agent_reply.call_count, 3)
        self.assertEqual(
            reply,
            AgentReply(
                "Your conversation became too long, so we had to reset it.\n\nLast reply"
            ),
        )

    @patch("message_service.reset_history")
    @patch("message_service.get_context_overflow_auto_reset", return_value=False)
    @patch("message_service.get_context_overflow_auto_compaction", return_value=True)
    @patch("message_service.load_history", return_value=[])
    @patch("message_service.compact_history")
    @patch("message_service.get_agent_reply")
    def test_propagates_when_the_compacted_context_is_still_too_large(
        self,
        get_agent_reply,
        compact_history,
        load_history,
        get_context_overflow_auto_compaction,
        get_context_overflow_auto_reset,
        reset_history,
    ):
        get_agent_reply.side_effect = [
            SessionContextTooLargeError("too large"),
            SessionContextTooLargeError("still too large"),
        ]

        with self.assertRaises(SessionContextTooLargeError):
            self.reply()

        reset_history.assert_not_called()
        self.assertEqual(get_agent_reply.call_count, 2)


if __name__ == "__main__":
    unittest.main()
