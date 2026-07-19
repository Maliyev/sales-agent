import math
import sqlite3
from pathlib import Path


class DatabaseError(RuntimeError):
    pass


def initialize_database(database_path):
    def create_tables(connection):
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'model')),
                text TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS messages_by_session
            ON messages(session_id, id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recent_messages (
                id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                received_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS recent_messages_by_session
            ON recent_messages(session_id, received_at)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS blocked_sessions (
                session_id TEXT PRIMARY KEY,
                blocked_at REAL NOT NULL,
                reason TEXT NOT NULL
            )
            """
        )

    run_database_operation(database_path, create_tables)


def create_session(database_path, session_id):
    session_id = validate_session_id(session_id)

    def add_session(connection):
        connection.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
            (session_id,),
        )

    run_database_operation(database_path, add_session)


def load_history(database_path, session_id):
    session_id = validate_session_id(session_id)

    def read_messages(connection):
        rows = connection.execute(
            """
            SELECT role, text
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()
        return [
            {"role": row["role"], "parts": [{"text": row["text"]}]}
            for row in rows
        ]

    return run_database_operation(database_path, read_messages)


def save_exchange(database_path, session_id, user_text, model_text):
    session_id = validate_session_id(session_id)
    user_text = validate_message_text(user_text)
    model_text = validate_message_text(model_text)

    def add_exchange(connection):
        connection.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
            (session_id,),
        )
        connection.executemany(
            "INSERT INTO messages (session_id, role, text) VALUES (?, ?, ?)",
            [
                (session_id, "user", user_text),
                (session_id, "model", model_text),
            ],
        )

    run_database_operation(database_path, add_exchange)


def list_session_ids(database_path):
    def read_session_ids(connection):
        rows = connection.execute(
            "SELECT session_id FROM sessions ORDER BY created_at, session_id"
        ).fetchall()
        return [row["session_id"] for row in rows]

    return run_database_operation(database_path, read_session_ids)


def reset_history(database_path, session_id):
    session_id = validate_session_id(session_id)

    def delete_messages(connection):
        connection.execute(
            "DELETE FROM messages WHERE session_id = ?",
            (session_id,),
        )

    run_database_operation(database_path, delete_messages)


def record_incoming_message(
    database_path,
    session_id,
    received_at,
    max_messages,
    window_seconds,
):
    session_id = validate_session_id(session_id)
    if isinstance(received_at, bool) or not isinstance(received_at, (int, float)):
        raise DatabaseError("Message time must be a number.")
    if not math.isfinite(received_at):
        raise DatabaseError("Message time must be finite.")

    def record_message(connection):
        connection.execute("BEGIN IMMEDIATE")

        blocked = connection.execute(
            "SELECT 1 FROM blocked_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if blocked is not None:
            return False

        cutoff = received_at - window_seconds
        connection.execute(
            "DELETE FROM recent_messages WHERE received_at <= ?",
            (cutoff,),
        )
        message_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM recent_messages
            WHERE session_id = ? AND received_at > ?
            """,
            (session_id, cutoff),
        ).fetchone()[0]

        if message_count >= max_messages:
            reason = (
                f"More than {max_messages} messages in {window_seconds} seconds"
            )
            connection.execute(
                """
                INSERT INTO blocked_sessions (session_id, blocked_at, reason)
                VALUES (?, ?, ?)
                """,
                (session_id, received_at, reason),
            )
            connection.execute(
                "DELETE FROM recent_messages WHERE session_id = ?",
                (session_id,),
            )
            return False

        connection.execute(
            "INSERT INTO recent_messages (session_id, received_at) VALUES (?, ?)",
            (session_id, received_at),
        )
        return True

    return run_database_operation(database_path, record_message)


def validate_session_id(session_id):
    if not isinstance(session_id, str) or not session_id.strip():
        raise DatabaseError("Session ID must not be empty.")

    if len(session_id) > 200:
        raise DatabaseError("Session ID is too long.")

    return session_id


def validate_message_text(text):
    if not isinstance(text, str) or not text.strip():
        raise DatabaseError("Message text must not be empty.")

    return text


def run_database_operation(database_path, operation):
    connection = None

    try:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")

        result = operation(connection)
        connection.commit()
        return result
    except (OSError, sqlite3.Error) as error:
        raise DatabaseError(f"Database operation failed: {error}") from error
    finally:
        if connection is not None:
            connection.close()
