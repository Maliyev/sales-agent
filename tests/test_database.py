from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from database import (
    DatabaseError,
    block_session,
    create_session,
    initialize_database,
    insert_incoming_message,
    list_sessions,
    load_history,
    load_session_messages,
    record_api_call,
    reset_history,
    run_database_operation,
    save_exchange,
    save_model_message,
    sum_tokens_in_window,
    update_messages_status,
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
                "api_calls",
                "recent_messages",
                "blocked_sessions",
                "whatsapp_inbound_messages",
            },
            self.read_table_names(),
        )

    def test_migration_adds_api_calls_to_an_older_database(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("DROP TABLE api_calls")
            connection.execute("PRAGMA user_version = 1")
            connection.commit()

        initialize_database(self.database_path)

        with closing(sqlite3.connect(self.database_path)) as connection:
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertIn("api_calls", names)
        self.assertEqual(version, 2)

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
        self.assertEqual(version_before, 2)
        self.assertEqual(version_after, 2)

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

    def test_saved_exchanges_can_start_as_response_ready_and_become_delivered(self):
        user_id, model_id = save_exchange(
            self.database_path,
            "telegram:9",
            "Hello",
            "Hi",
            status="RESPONSE_READY",
        )
        self.assertIsInstance(user_id, int)
        self.assertIsInstance(model_id, int)

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT id, status FROM messages ORDER BY id"
            ).fetchall()
        self.assertEqual(
            rows,
            [(user_id, "RESPONSE_READY"), (model_id, "RESPONSE_READY")],
        )

        update_messages_status(self.database_path, [user_id, model_id], "DELIVERED")

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT status FROM messages ORDER BY id"
            ).fetchall()
        self.assertEqual(rows, [("DELIVERED",), ("DELIVERED",)])

    def test_rejects_an_unknown_status_on_save_and_update(self):
        self.assertRaises(
            DatabaseError,
            save_exchange,
            self.database_path,
            "telegram:1",
            "Hello",
            "Hi",
            "WRONG",
        )
        self.assertRaises(
            DatabaseError,
            update_messages_status,
            self.database_path,
            [1],
            "WRONG",
        )

    def test_incoming_messages_start_as_initializing_and_hide_from_history(self):
        insert_incoming_message(
            self.database_path,
            "telegram:5",
            "Pending question",
        )

        history = load_history(self.database_path, "telegram:5")
        stored = load_session_messages(self.database_path, "telegram:5")

        self.assertEqual(history, [])
        self.assertEqual([message["text"] for message in stored], ["Pending question"])
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT role, status FROM messages WHERE session_id = 'telegram:5'"
            ).fetchall()
        self.assertEqual(rows, [("user", "INITIALIZING")])

    def test_api_calls_are_recorded_and_summed_per_window(self):
        create_session(self.database_path, "telegram:6")
        reply_to = insert_incoming_message(self.database_path, "telegram:6", "Hello")
        record_api_call(
            self.database_path,
            "telegram:6",
            None,
            "decision",
            "gemini-model",
            prompt_tokens=100,
            completion_tokens=20,
            duration_ms=250,
        )
        record_api_call(
            self.database_path,
            "telegram:6",
            reply_to,
            "final",
            "gemini-model",
            prompt_tokens=50,
            completion_tokens=30,
        )

        total = sum_tokens_in_window(self.database_path, 60)
        per_session = sum_tokens_in_window(
            self.database_path,
            60,
            session_id="telegram:6",
        )
        other = sum_tokens_in_window(self.database_path, 60, session_id="telegram:9")

        self.assertEqual(total, 200)
        self.assertEqual(per_session, 200)
        self.assertEqual(other, 0)

    def test_the_token_window_ignores_old_calls(self):
        create_session(self.database_path, "telegram:6")
        record_api_call(self.database_path, "telegram:6", None, "final", "gemini-model")

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("UPDATE api_calls SET created_at = '2020-01-01 00:00:00'")
            connection.commit()

        self.assertEqual(sum_tokens_in_window(self.database_path, 60), 0)

    def test_block_session_is_idempotent(self):
        block_session(self.database_path, "telegram:7", "Token abuse")
        block_session(self.database_path, "telegram:7", "Token abuse again")

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT session_id, reason FROM blocked_sessions"
            ).fetchall()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "telegram:7")

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
