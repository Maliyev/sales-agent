from pathlib import Path
import sys
import tempfile
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from database import initialize_database
from message_guard import is_message_allowed


class MessageGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_folder.cleanup()

    def test_blocks_the_sixteenth_message_in_one_minute(self):
        for second in range(15):
            self.assertTrue(
                is_message_allowed(
                    self.database_path,
                    "telegram:123",
                    now=1000 + second,
                )
            )

        self.assertFalse(
            is_message_allowed(self.database_path, "telegram:123", now=1015)
        )

    def test_block_remains_after_the_time_window_has_passed(self):
        for second in range(16):
            is_message_allowed(
                self.database_path,
                "whatsapp:994501234567",
                now=1000 + second,
            )

        self.assertFalse(
            is_message_allowed(
                self.database_path,
                "whatsapp:994501234567",
                now=5000,
            )
        )

    def test_different_sessions_have_separate_limits(self):
        for second in range(15):
            is_message_allowed(
                self.database_path,
                "website:spammer",
                now=1000 + second,
            )

        self.assertTrue(
            is_message_allowed(self.database_path, "website:customer", now=1015)
        )

    def test_old_messages_leave_the_sliding_window(self):
        for second in range(15):
            is_message_allowed(
                self.database_path,
                "telegram:slow-customer",
                now=1000 + second,
            )

        self.assertTrue(
            is_message_allowed(
                self.database_path,
                "telegram:slow-customer",
                now=1061,
            )
        )


if __name__ == "__main__":
    unittest.main()
