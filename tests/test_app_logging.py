import logging
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app_logging import (
    LOGGER_NAME,
    close_logging,
    configure_logging,
    flatten_text,
    get_logger,
    log_conversation,
)


class ApplicationLoggingTests(unittest.TestCase):
    log_path = PROJECT_ROOT / "data" / "logs" / "test_sales_agent.log"
    conversation_log_path = PROJECT_ROOT / "data" / "logs" / "test_conversations.log"

    def setUp(self):
        self._remove_log_files()

    def tearDown(self):
        close_logging()
        self._remove_log_files()

    def _remove_log_files(self):
        for path in (
            self.log_path,
            Path(f"{self.log_path}.1"),
            self.conversation_log_path,
            Path(f"{self.conversation_log_path}.1"),
        ):
            if path.exists():
                path.unlink()

    def test_writes_to_a_rotating_file_with_raw_session_id(self):
        configure_logging(self.log_path, max_bytes=250, backup_count=1)
        logger = get_logger("test")

        for index in range(8):
            logger.info(
                "Test event | session=%s index=%d padding=%s",
                "whatsapp:994501234567",
                index,
                "x" * 80,
            )

        close_logging()
        combined = "".join(
            path.read_text(encoding="utf-8")
            for path in (self.log_path, Path(f"{self.log_path}.1"))
            if path.exists()
        )

        self.assertIn("whatsapp:994501234567", combined)
        self.assertTrue(Path(f"{self.log_path}.1").exists())

    def test_conversation_log_keeps_text_out_of_the_operational_log(self):
        configure_logging(self.log_path, self.conversation_log_path)
        logger = get_logger("test")

        log_conversation(
            "telegram:555",
            "USER",
            flatten_text("First line\nSecond line"),
        )
        log_conversation("telegram:555", "MODEL", "Ответ модели")
        logger.info("Operational event | session=telegram:555")

        close_logging()

        conversation = self.conversation_log_path.read_text(encoding="utf-8")
        operational = self.log_path.read_text(encoding="utf-8")

        self.assertIn("telegram:555 | 💬 USER | First line\\nSecond line", conversation)
        self.assertIn("telegram:555 | 🤖 MODEL | Ответ модели", conversation)
        self.assertIn("Operational event", operational)
        self.assertNotIn("USER |", operational)
        self.assertNotIn("MODEL |", operational)

    def test_close_logging_removes_handlers(self):
        configure_logging(self.log_path)
        close_logging()

        handlers = logging.getLogger(LOGGER_NAME).handlers
        self.assertEqual(len(handlers), 1)
        self.assertIsInstance(handlers[0], logging.NullHandler)

    def test_keeps_console_logging_if_the_file_cannot_be_created(self):
        with patch(
            "app_logging.RotatingFileHandler",
            side_effect=PermissionError("denied"),
        ):
            logger = configure_logging(self.log_path)

        self.assertTrue(
            any(
                isinstance(handler, logging.StreamHandler)
                and not isinstance(handler, logging.NullHandler)
                for handler in logger.handlers
            )
        )


if __name__ == "__main__":
    unittest.main()
