from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from app_config import get_token_abuse_settings, get_tpm_limit, set_config
from app_logging import LOGGER_NAME
from database import (
    create_session,
    initialize_database,
    record_api_call,
)
from message_guard import is_message_allowed
from token_limiter import (
    SessionContextTooLargeError,
    TokenLimitError,
    guard_session_consumption,
    wait_for_token_budget,
)


def build_config(
    tpm_limit=0,
    max_messages=15,
    message_window=60,
    token_abuse_limit=0,
    token_abuse_window=60,
):
    return {
        "gemini": {"model": "gemini-model", "tpm_limit": tpm_limit},
        "limits": {
            "message_rate": {
                "max_messages": max_messages,
                "window_seconds": message_window,
            },
            "token_abuse": {
                "limit": token_abuse_limit,
                "window_seconds": token_abuse_window,
            },
        },
    }


class FakeClock:
    def __init__(self):
        self.now = time.time()

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class WaitForTokenBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)
        create_session(self.database_path, "telegram:1")
        self.clock = FakeClock()
        self.sleeps = []

    def tearDown(self):
        self.temp_folder.cleanup()

    def sleep_fn(self, seconds):
        self.sleeps.append(seconds)
        self.clock.advance(seconds)

    def test_returns_immediately_when_the_limit_is_disabled(self):
        wait_for_token_budget(
            self.database_path,
            999_999,
            tpm_limit=0,
            clock=self.clock.time,
            sleep_fn=self.sleep_fn,
        )

        self.assertEqual(self.sleeps, [])

    def test_proceeds_while_the_budget_allows_the_request(self):
        record_api_call(
            self.database_path,
            "telegram:1",
            None,
            "final",
            "gemini-model",
            prompt_tokens=300,
            completion_tokens=100,
        )

        wait_for_token_budget(
            self.database_path,
            500,
            tpm_limit=1000,
            clock=self.clock.time,
            sleep_fn=self.sleep_fn,
        )

        self.assertEqual(self.sleeps, [])

    def test_waits_until_the_window_frees_up(self):
        record_api_call(
            self.database_path,
            "telegram:1",
            None,
            "final",
            "gemini-model",
            prompt_tokens=800,
            completion_tokens=100,
        )

        wait_for_token_budget(
            self.database_path,
            500,
            tpm_limit=1000,
            clock=self.clock.time,
            sleep_fn=self.sleep_fn,
        )

        self.assertGreater(len(self.sleeps), 0)

    def test_fails_fast_when_a_single_request_exceeds_the_limit(self):
        with self.assertRaises(SessionContextTooLargeError):
            wait_for_token_budget(
                self.database_path,
                1500,
                tpm_limit=1000,
                clock=self.clock.time,
                sleep_fn=self.sleep_fn,
            )

        self.assertEqual(self.sleeps, [])

    def test_context_error_is_a_token_limit_error(self):
        self.assertTrue(issubclass(SessionContextTooLargeError, TokenLimitError))

    def test_does_not_spam_the_log_while_waiting(self):
        record_api_call(
            self.database_path,
            "telegram:1",
            None,
            "final",
            "gemini-model",
            prompt_tokens=900,
        )

        with self.assertLogs(f"{LOGGER_NAME}.tokens", level="INFO") as logs:
            wait_for_token_budget(
                self.database_path,
                500,
                tpm_limit=1000,
                clock=self.clock.time,
                sleep_fn=self.sleep_fn,
            )

        limit_logs = [
            message for message in logs.output if "TPM limit reached" in message
        ]
        self.assertGreater(len(self.sleeps), 0)
        self.assertLess(len(limit_logs), len(self.sleeps))

    def test_gives_up_after_the_maximum_wait(self):
        record_api_call(
            self.database_path,
            "telegram:1",
            None,
            "final",
            "gemini-model",
            prompt_tokens=800,
            completion_tokens=100,
        )

        with self.assertRaises(TokenLimitError):
            wait_for_token_budget(
                self.database_path,
                500,
                tpm_limit=1000,
                clock=self.clock.time,
                sleep_fn=self.sleep_fn,
                max_wait_seconds=10,
            )


class LimitSettingsTests(unittest.TestCase):
    def tearDown(self):
        set_config(None)

    def test_reads_limits_from_the_active_config(self):
        set_config(build_config(tpm_limit=250000, token_abuse_limit=5000, token_abuse_window=120))

        self.assertEqual(get_tpm_limit(), 250000)
        self.assertEqual(get_token_abuse_settings(), (5000, 120))


class ConsumptionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)
        create_session(self.database_path, "telegram:2")
        create_session(self.database_path, "telegram:3")
        create_session(self.database_path, "telegram:4")

    def tearDown(self):
        set_config(None)
        self.temp_folder.cleanup()

    def test_blocks_a_session_that_exceeds_the_token_budget(self):
        record_api_call(
            self.database_path,
            "telegram:2",
            None,
            "final",
            "gemini-model",
            prompt_tokens=150,
        )
        set_config(build_config(token_abuse_limit=100, token_abuse_window=60))

        blocked = guard_session_consumption(self.database_path, "telegram:2")

        self.assertTrue(blocked)
        self.assertFalse(
            is_message_allowed(self.database_path, "telegram:2", now=time.time())
        )

    def test_ignores_sessions_below_the_budget(self):
        record_api_call(
            self.database_path,
            "telegram:3",
            None,
            "final",
            "gemini-model",
            prompt_tokens=50,
        )
        set_config(build_config(token_abuse_limit=100, token_abuse_window=60))

        blocked = guard_session_consumption(self.database_path, "telegram:3")

        self.assertFalse(blocked)
        self.assertTrue(
            is_message_allowed(self.database_path, "telegram:3", now=time.time())
        )

    def test_is_disabled_without_settings(self):
        record_api_call(
            self.database_path,
            "telegram:4",
            None,
            "final",
            "gemini-model",
            prompt_tokens=999_999,
        )
        set_config(build_config())

        blocked = guard_session_consumption(self.database_path, "telegram:4")

        self.assertFalse(blocked)


if __name__ == "__main__":
    unittest.main()
