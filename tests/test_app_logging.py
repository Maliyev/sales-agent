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
    get_logger,
    session_reference,
)


class ApplicationLoggingTests(unittest.TestCase):
    log_path = PROJECT_ROOT / "data" / "logs" / "test_sales_agent.log"

    def setUp(self):
        self._remove_log_files()

    def tearDown(self):
        close_logging()
        self._remove_log_files()

    def _remove_log_files(self):
        for path in (self.log_path, Path(f"{self.log_path}.1")):
            if path.exists():
                path.unlink()

    def test_writes_to_a_rotating_file_without_raw_session_id(self):
        configure_logging(self.log_path, max_bytes=250, backup_count=1)
        logger = get_logger("test")
        reference = session_reference("whatsapp:994501234567")

        for index in range(8):
            logger.info(
                "Test event | session=%s index=%d padding=%s",
                reference,
                index,
                "x" * 80,
            )

        close_logging()
        combined = "".join(
            path.read_text(encoding="utf-8")
            for path in (self.log_path, Path(f"{self.log_path}.1"))
            if path.exists()
        )

        self.assertIn(reference, combined)
        self.assertNotIn("994501234567", combined)
        self.assertTrue(Path(f"{self.log_path}.1").exists())

    def test_session_reference_is_stable_and_channel_qualified(self):
        first = session_reference("telegram:123")
        second = session_reference("telegram:123")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("telegram:"))
        self.assertNotIn("123", first)

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
