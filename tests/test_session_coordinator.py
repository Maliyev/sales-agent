from pathlib import Path
import sys
from threading import Barrier, Event, Lock
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from session_coordinator import SessionCoordinator


class SessionCoordinatorTests(unittest.TestCase):
    def test_different_sessions_run_at_the_same_time(self):
        barrier = Barrier(2)
        calls = []
        saved = []
        delivered = []
        errors = []
        result_lock = Lock()

        def generate_reply(session_id, text, in_reply_to_message_id):
            barrier.wait(timeout=2)
            with result_lock:
                calls.append((session_id, text))
            return f"Reply for {session_id}"

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, reply: saved.append((session_id, reply)) or 1,
            max_workers=2,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", 101, "First", delivered.append, errors.append)
        coordinator.submit("telegram:2", 202, "Second", delivered.append, errors.append)
        coordinator.shutdown()

        self.assertCountEqual(
            calls,
            [("telegram:1", "First"), ("telegram:2", "Second")],
        )
        self.assertEqual(len(saved), 2)
        self.assertEqual(len(delivered), 2)
        self.assertEqual(errors, [])

    def test_new_message_restarts_one_running_session(self):
        first_started = Event()
        release_first = Event()
        calls = []
        saved = []
        delivered = []
        errors = []

        def generate_reply(session_id, text, in_reply_to_message_id):
            calls.append(text)
            if len(calls) == 1:
                first_started.set()
                if not release_first.wait(timeout=2):
                    raise TimeoutError("Test did not release the first request")
            return f"Reply: {text}"

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, reply: saved.append(reply),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("website:ali", 1, "Power supply", delivered.append, errors.append)
        self.assertTrue(first_started.wait(timeout=2))
        coordinator.submit("website:ali", 2, "12 volts", delivered.append, errors.append)
        release_first.set()
        coordinator.shutdown()

        self.assertEqual(calls, ["Power supply", "Power supply\n12 volts"])
        self.assertEqual(saved, ["Reply: Power supply\n12 volts"])
        self.assertEqual(delivered, ["Reply: Power supply\n12 volts"])
        self.assertEqual(errors, [])

    def test_only_one_restart_is_used_for_a_message_batch(self):
        first_started = Event()
        second_started = Event()
        release_first = Event()
        release_second = Event()
        calls = []
        saved = []
        delivered = []

        def generate_reply(session_id, text, in_reply_to_message_id):
            calls.append(text)
            if len(calls) == 1:
                first_started.set()
                release_first.wait(timeout=2)
            elif len(calls) == 2:
                second_started.set()
                release_second.wait(timeout=2)
            return f"Reply: {text}"

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, reply: saved.append(reply),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("website:ali", 1, "One", delivered.append, self.fail)
        self.assertTrue(first_started.wait(timeout=2))
        coordinator.submit("website:ali", 2, "Two", delivered.append, self.fail)
        release_first.set()
        self.assertTrue(second_started.wait(timeout=2))
        coordinator.submit("website:ali", 3, "Three", delivered.append, self.fail)
        release_second.set()
        coordinator.shutdown()

        self.assertEqual(calls, ["One", "One\nTwo", "Three"])
        self.assertEqual(saved, ["Reply: One\nTwo", "Reply: Three"])
        self.assertEqual(delivered, ["Reply: One\nTwo", "Reply: Three"])

    def test_reset_discards_a_running_reply(self):
        request_started = Event()
        release_request = Event()
        saved = []
        delivered = []
        reset_calls = []

        def generate_reply(session_id, text, in_reply_to_message_id):
            request_started.set()
            release_request.wait(timeout=2)
            return "Old reply"

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, reply: saved.append(reply),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", 1, "Old message", delivered.append, self.fail)
        self.assertTrue(request_started.wait(timeout=2))
        coordinator.reset_session("telegram:1", lambda: reset_calls.append(True))
        release_request.set()
        coordinator.shutdown()

        self.assertEqual(reset_calls, [True])
        self.assertEqual(saved, [])
        self.assertEqual(delivered, [])

    def test_delivery_result_is_marked_after_successful_send(self):
        marks = []
        delivered = []

        coordinator = SessionCoordinator(
            lambda session_id, text, in_reply_to: "Reply",
            lambda session_id, reply: 12,
            mark_messages_status=lambda session_id, ids, status: marks.append(
                (session_id, list(ids), status)
            ),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", 11, "Hi", delivered.append, self.fail)
        coordinator.shutdown()

        self.assertEqual(delivered, ["Reply"])
        self.assertEqual(marks, [("telegram:1", [11, 12], "DELIVERED")])

    def test_delivery_failure_marks_the_reply_and_the_message(self):
        marks = []
        errors = []

        def failing_callback(reply):
            raise RuntimeError("send failed")

        coordinator = SessionCoordinator(
            lambda session_id, text, in_reply_to: "Reply",
            lambda session_id, reply: 22,
            mark_messages_status=lambda session_id, ids, status: marks.append(
                (session_id, list(ids), status)
            ),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", 21, "Hi", failing_callback, errors.append)
        coordinator.shutdown()

        self.assertEqual(marks, [("telegram:1", [21, 22], "FAILED_DELIVERY")])
        self.assertEqual(len(errors), 1)

    def test_generation_failure_marks_the_turn_as_llm_failure(self):
        marks = []
        errors = []

        def generate_reply(session_id, text, in_reply_to_message_id):
            raise RuntimeError("gemini down")

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, reply: self.fail("Reply must not be saved"),
            mark_messages_status=lambda session_id, ids, status: marks.append(
                (session_id, list(ids), status)
            ),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", 31, "Hi", self.fail, errors.append)
        coordinator.shutdown()

        self.assertEqual(marks, [("telegram:1", [31], "FAILED_LLM_API")])
        self.assertEqual(len(errors), 1)

    def test_saver_without_an_id_still_marks_the_turn(self):
        marks = []
        delivered = []

        coordinator = SessionCoordinator(
            lambda session_id, text, in_reply_to: "Reply",
            lambda session_id, reply: None,
            mark_messages_status=lambda session_id, ids, status: marks.append(
                (session_id, list(ids), status)
            ),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", 41, "Hi", delivered.append, self.fail)
        coordinator.shutdown()

        self.assertEqual(delivered, ["Reply"])
        self.assertEqual(marks, [("telegram:1", [41], "DELIVERED")])

    def test_rejects_a_non_callable_status_marker(self):
        self.assertRaises(
            ValueError,
            SessionCoordinator,
            lambda session_id, text, in_reply_to: "Reply",
            lambda session_id, reply: 1,
            "not callable",
        )


if __name__ == "__main__":
    unittest.main()
