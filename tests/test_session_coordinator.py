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

        def generate_reply(session_id, text):
            barrier.wait(timeout=2)
            with result_lock:
                calls.append((session_id, text))
            return f"Reply for {session_id}"

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, text, reply: saved.append(
                (session_id, text, reply)
            ),
            max_workers=2,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", "First", delivered.append, errors.append)
        coordinator.submit("telegram:2", "Second", delivered.append, errors.append)
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

        def generate_reply(session_id, text):
            calls.append(text)
            if len(calls) == 1:
                first_started.set()
                if not release_first.wait(timeout=2):
                    raise TimeoutError("Test did not release the first request")
            return f"Reply: {text}"

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, text, reply: saved.append((text, reply)),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("website:ali", "Power supply", delivered.append, errors.append)
        self.assertTrue(first_started.wait(timeout=2))
        coordinator.submit("website:ali", "12 volts", delivered.append, errors.append)
        release_first.set()
        coordinator.shutdown()

        self.assertEqual(calls, ["Power supply", "Power supply\n12 volts"])
        self.assertEqual(saved, [("Power supply\n12 volts", "Reply: Power supply\n12 volts")])
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

        def generate_reply(session_id, text):
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
            lambda session_id, text, reply: saved.append(text),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("website:ali", "One", delivered.append, self.fail)
        self.assertTrue(first_started.wait(timeout=2))
        coordinator.submit("website:ali", "Two", delivered.append, self.fail)
        release_first.set()
        self.assertTrue(second_started.wait(timeout=2))
        coordinator.submit("website:ali", "Three", delivered.append, self.fail)
        release_second.set()
        coordinator.shutdown()

        self.assertEqual(calls, ["One", "One\nTwo", "Three"])
        self.assertEqual(saved, ["One\nTwo", "Three"])
        self.assertEqual(delivered, ["Reply: One\nTwo", "Reply: Three"])

    def test_reset_discards_a_running_reply(self):
        request_started = Event()
        release_request = Event()
        saved = []
        delivered = []
        reset_calls = []

        def generate_reply(session_id, text):
            request_started.set()
            release_request.wait(timeout=2)
            return "Old reply"

        coordinator = SessionCoordinator(
            generate_reply,
            lambda session_id, text, reply: saved.append(reply),
            max_workers=1,
            debounce_seconds=0,
        )

        coordinator.submit("telegram:1", "Old message", delivered.append, self.fail)
        self.assertTrue(request_started.wait(timeout=2))
        coordinator.reset_session("telegram:1", lambda: reset_calls.append(True))
        release_request.set()
        coordinator.shutdown()

        self.assertEqual(reset_calls, [True])
        self.assertEqual(saved, [])
        self.assertEqual(delivered, [])


if __name__ == "__main__":
    unittest.main()
