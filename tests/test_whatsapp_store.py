import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from whatsapp_store import (
    claim_incoming_message,
    initialize_whatsapp_store,
    release_incoming_message,
)


class WhatsAppStoreTests(unittest.TestCase):
    @patch("whatsapp_store.run_database_operation")
    def test_creates_the_whatsapp_deduplication_table(self, run_operation):
        connection = Mock()
        run_operation.side_effect = lambda path, operation: operation(connection)

        initialize_whatsapp_store("database.db")

        sql = connection.execute.call_args.args[0]
        self.assertIn("whatsapp_inbound_messages", sql)
        self.assertIn("message_id TEXT PRIMARY KEY", sql)

    @patch("whatsapp_store.run_database_operation")
    def test_claims_a_new_message_only_once(self, run_operation):
        connection = Mock()
        connection.execute.return_value.rowcount = 1
        run_operation.side_effect = lambda path, operation: operation(connection)

        claimed = claim_incoming_message(
            "database.db",
            "wamid.123",
            "994501234567",
        )

        self.assertTrue(claimed)
        self.assertEqual(
            connection.execute.call_args.args[1],
            ("wamid.123", "994501234567"),
        )

    @patch("whatsapp_store.run_database_operation")
    def test_rejects_a_message_that_was_already_claimed(self, run_operation):
        connection = Mock()
        connection.execute.return_value.rowcount = 0
        run_operation.side_effect = lambda path, operation: operation(connection)

        claimed = claim_incoming_message(
            "database.db",
            "wamid.123",
            "994501234567",
        )

        self.assertFalse(claimed)

    @patch("whatsapp_store.run_database_operation")
    def test_releases_a_claim_when_message_submission_fails(self, run_operation):
        connection = Mock()
        run_operation.side_effect = lambda path, operation: operation(connection)

        release_incoming_message("database.db", "wamid.123")

        self.assertIn(
            "DELETE FROM whatsapp_inbound_messages",
            connection.execute.call_args.args[0],
        )
        self.assertEqual(connection.execute.call_args.args[1], ("wamid.123",))


if __name__ == "__main__":
    unittest.main()
