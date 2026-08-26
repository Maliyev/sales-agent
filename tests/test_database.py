from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from database import (
    DatabaseError,
    create_session,
    initialize_database,
    list_sessions,
    load_history,
    load_session_messages,
    reset_history,
    run_database_operation,
    save_exchange,
    save_model_message,
)


class DatabaseSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_folder.cleanup()

    def read_table_names(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        return {row[0] for row in rows}

    def test_creates_all_tables_from_one_entry_point(self):
        self.assertLessEqual(
            {
                "sessions",
                "messages",
                "tool_calls",
                "recent_messages",
                "blocked_sessions",
                "whatsapp_inbound_messages",
            },
            self.read_table_names(),
        )

    def test_reinitializing_an_up_to_date_database_changes_nothing(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            version_before = connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]

        initialize_database(self.database_path)

        with closing(sqlite3.connect(self.database_path)) as connection:
            version_after = connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        self.assertEqual(version_before, 1)
        self.assertEqual(version_after, 1)

    def test_saved_exchanges_get_delivered_status_and_visible_by_default(self):
        save_exchange(self.database_path, "telegram:1", "Hello", "Hi")

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT role, archived, status FROM messages ORDER BY id"
            ).fetchall()

        self.assertEqual(
            rows,
            [
                ("user", 0, "DELIVERED"),
                ("model", 0, "DELIVERED"),
            ],
        )

    def test_sessions_get_a_channel_by_default(self):
        create_session(self.database_path, "terminal:new_client")

        with closing(sqlite3.connect(self.database_path)) as connection:
            channel = connection.execute(
                "SELECT channel FROM sessions WHERE session_id = ?",
                ("terminal:new_client",),
            ).fetchone()[0]

        self.assertEqual(channel, "unknown")

    def test_rejects_a_role_outside_the_allowed_set(self):
        def write_invalid_role():
            def operation(connection):
                connection.execute(
                    """
                    INSERT INTO messages (session_id, role, text)
                    VALUES ('telegram:1', 'system', 'nope')
                    """
                )

            return run_database_operation(self.database_path, operation)

        self.assertRaises(DatabaseError, write_invalid_role)

    def test_rejects_a_status_outside_the_allowed_set(self):
        def write_invalid_status():
            def operation(connection):
                connection.execute(
                    """
                    INSERT INTO messages (session_id, role, text, status)
                    VALUES ('telegram:1', 'user', 'nope', 'LOST')
                    """
                )

            return run_database_operation(self.database_path, operation)

        self.assertRaises(DatabaseError, write_invalid_status)


class ArchiveAndResetTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_folder.cleanup()

    def test_reset_archives_messages_instead_of_deleting_them(self):
        save_exchange(self.database_path, "telegram:1", "Hello", "Hi")

        reset_history(self.database_path, "telegram:1")

        self.assertEqual(load_history(self.database_path, "telegram:1"), [])
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT archived FROM messages WHERE session_id = 'telegram:1'"
            ).fetchall()
        self.assertEqual(rows, [(1,), (1,)])

    def test_archived_rows_are_hidden_from_all_readers(self):
        save_exchange(self.database_path, "telegram:1", "Hello", "Hi")
        reset_history(self.database_path, "telegram:1")
        save_exchange(self.database_path, "telegram:1", "Again", "Ok")

        history = load_history(self.database_path, "telegram:1")
        stored = load_session_messages(self.database_path, "telegram:1")
        overview = list_sessions(self.database_path)

        self.assertEqual(
            [entry["parts"][0]["text"] for entry in history],
            ["Again", "Ok"],
        )
        self.assertEqual(
            [message["text"] for message in stored],
            ["Again", "Ok"],
        )
        self.assertEqual(overview[0]["message_count"], 2)
        self.assertEqual(overview[0]["last_text"], "Ok")

    def test_session_overview_ignores_tool_rows_and_archived_rows(self):
        save_exchange(self.database_path, "telegram:1", "Hello", "Hi")
        save_model_message(self.database_path, "telegram:1", "Manual answer")

        def insert_tool_row():
            def operation(connection):
                connection.execute(
                    """
                    INSERT INTO messages (session_id, role, text, status)
                    VALUES ('telegram:1', 'tool', 'Summary', 'DELIVERED')
                    """
                )

            return run_database_operation(self.database_path, operation)

        insert_tool_row()
        reset_history(self.database_path, "telegram:1")
        save_exchange(self.database_path, "telegram:1", "New question", "New answer")

        overview = list_sessions(self.database_path)

        self.assertEqual(overview[0]["message_count"], 2)
        self.assertEqual(overview[0]["last_role"], "model")
        self.assertEqual(overview[0]["last_text"], "New answer")


if __name__ == "__main__":
    unittest.main()
