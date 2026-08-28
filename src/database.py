import math
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


class DatabaseError(RuntimeError):
    pass


MESSAGE_STATUSES = (
    "INITIALIZING",
    "AWAITING_RESPONSE",
    "AGENT_PROCESSING",
    "RESPONSE_READY",
    "DELIVERED",
    "FAILED_LLM_API",
    "FAILED_DELIVERY",
    "FAILED_OTHER",
)

MESSAGE_STATUS_CHECK = ", ".join(repr(status) for status in MESSAGE_STATUSES)


def migration_001_initial_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            channel TEXT NOT NULL DEFAULT 'unknown',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            role TEXT NOT NULL CHECK(role IN ('user', 'model', 'operator', 'tool')),
            text TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0, 1)),
            status TEXT NOT NULL DEFAULT 'INITIALIZING' CHECK(status IN ({MESSAGE_STATUS_CHECK})),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            message_id INTEGER NOT NULL REFERENCES messages(id),
            tool_call_id TEXT,
            tool_name TEXT NOT NULL,
            arguments_json TEXT,
            result_json TEXT,
            status TEXT NOT NULL CHECK(status IN ('pending', 'succeeded', 'failed')),
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS tool_calls_by_message
        ON tool_calls(message_id)
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
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS whatsapp_inbound_messages (
            message_id TEXT PRIMARY KEY,
            sender_id TEXT NOT NULL,
            received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def migration_002_api_calls(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS api_calls (
            id INTEGER PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES sessions(session_id),
            in_reply_to_message_id INTEGER REFERENCES messages(id),
            purpose TEXT NOT NULL CHECK(purpose IN ('decision', 'selection', 'final')),
            model TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            duration_ms INTEGER,
            status TEXT NOT NULL CHECK(status IN ('ok', 'failed')),
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS api_calls_by_session_time
        ON api_calls(session_id, created_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS api_calls_by_time
        ON api_calls(created_at)
        """
    )


MIGRATIONS = (
    migration_001_initial_schema,
    migration_002_api_calls,
)


def initialize_database(database_path):
    def apply_migrations(connection):
        connection.execute("PRAGMA journal_mode = WAL")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        for target_version, migration in enumerate(MIGRATIONS, start=1):
            if target_version > version:
                migration(connection)
                connection.execute(f"PRAGMA user_version = {target_version}")

    run_database_operation(database_path, apply_migrations)


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
            WHERE session_id = ? AND archived = 0 AND status != 'INITIALIZING'
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()
        return [
            {"role": row["role"], "parts": [{"text": row["text"]}]}
            for row in rows
        ]

    return run_database_operation(database_path, read_messages)


def save_exchange(
    database_path,
    session_id,
    user_text,
    model_text,
    status="DELIVERED",
):
    session_id = validate_session_id(session_id)
    user_text = validate_message_text(user_text)
    model_text = validate_message_text(model_text)
    if status not in MESSAGE_STATUSES:
        raise DatabaseError("Unknown message status.")

    def add_exchange(connection):
        connection.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
            (session_id,),
        )
        cursor = connection.execute(
            """
            INSERT INTO messages (session_id, role, text, status)
            VALUES (?, 'user', ?, ?)
            """,
            (session_id, user_text, status),
        )
        user_message_id = cursor.lastrowid
        cursor = connection.execute(
            """
            INSERT INTO messages (session_id, role, text, status)
            VALUES (?, 'model', ?, ?)
            """,
            (session_id, model_text, status),
        )
        return user_message_id, cursor.lastrowid

    return run_database_operation(database_path, add_exchange)


def list_session_ids(database_path):
    def read_session_ids(connection):
        rows = connection.execute(
            "SELECT session_id FROM sessions ORDER BY created_at, session_id"
        ).fetchall()
        return [row["session_id"] for row in rows]

    return run_database_operation(database_path, read_session_ids)


def list_sessions(database_path):
    def read_sessions(connection):
        rows = connection.execute(
            """
            SELECT
                sessions.session_id,
                sessions.created_at,
                COUNT(messages.id) AS message_count,
                MAX(messages.id) AS last_message_id,
                (
                    SELECT latest.role
                    FROM messages AS latest
                    WHERE latest.session_id = sessions.session_id
                      AND latest.archived = 0
                      AND latest.role != 'tool'
                    ORDER BY latest.id DESC
                    LIMIT 1
                ) AS last_role,
                (
                    SELECT latest.text
                    FROM messages AS latest
                    WHERE latest.session_id = sessions.session_id
                      AND latest.archived = 0
                      AND latest.role != 'tool'
                    ORDER BY latest.id DESC
                    LIMIT 1
                ) AS last_text
            FROM sessions
            LEFT JOIN messages
                ON messages.session_id = sessions.session_id
                AND messages.archived = 0
                AND messages.role != 'tool'
            GROUP BY sessions.session_id, sessions.created_at
            ORDER BY COALESCE(MAX(messages.id), 0) DESC, sessions.created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    return run_database_operation(database_path, read_sessions)


def load_session_messages(database_path, session_id):
    session_id = validate_session_id(session_id)

    def read_messages(connection):
        rows = connection.execute(
            """
            SELECT id, role, text
            FROM messages
            WHERE session_id = ? AND archived = 0
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    return run_database_operation(database_path, read_messages)


def insert_incoming_message(database_path, session_id, text):
    session_id = validate_session_id(session_id)
    text = validate_message_text(text)

    def add_message(connection):
        connection.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
            (session_id,),
        )
        cursor = connection.execute(
            """
            INSERT INTO messages (session_id, role, text, status)
            VALUES (?, 'user', ?, 'INITIALIZING')
            """,
            (session_id, text),
        )
        return cursor.lastrowid

    return run_database_operation(database_path, add_message)


def save_model_message(database_path, session_id, text, status="DELIVERED"):
    session_id = validate_session_id(session_id)
    text = validate_message_text(text)
    if status not in MESSAGE_STATUSES:
        raise DatabaseError("Unknown message status.")

    def add_message(connection):
        connection.execute(
            "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
            (session_id,),
        )
        cursor = connection.execute(
            """
            INSERT INTO messages (session_id, role, text, status)
            VALUES (?, 'model', ?, ?)
            """,
            (session_id, text, status),
        )
        return cursor.lastrowid

    return run_database_operation(database_path, add_message)


def update_messages_status(database_path, message_ids, status):
    if status not in MESSAGE_STATUSES:
        raise DatabaseError("Unknown message status.")
    if not message_ids:
        return
    validated_ids = []
    for message_id in message_ids:
        if isinstance(message_id, bool) or not isinstance(message_id, int):
            raise DatabaseError("Message ID must be a number.")
        validated_ids.append(message_id)

    def update_status(connection):
        connection.executemany(
            "UPDATE messages SET status = ? WHERE id = ?",
            [(status, message_id) for message_id in validated_ids],
        )

    run_database_operation(database_path, update_status)


def record_api_call(
    database_path,
    session_id,
    in_reply_to_message_id,
    purpose,
    model,
    prompt_tokens=0,
    completion_tokens=0,
    duration_ms=None,
    status="ok",
    error=None,
):
    session_id = validate_session_id(session_id)
    if not isinstance(model, str) or not model.strip():
        raise DatabaseError("Model name must not be empty.")
    if status not in ("ok", "failed"):
        raise DatabaseError("Unknown API call status.")
    if duration_ms is not None and (
        isinstance(duration_ms, bool) or not isinstance(duration_ms, (int, float))
    ):
        raise DatabaseError("Duration must be a number.")

    def add_call(connection):
        cursor = connection.execute(
            """
            INSERT INTO api_calls (
                session_id,
                in_reply_to_message_id,
                purpose,
                model,
                prompt_tokens,
                completion_tokens,
                duration_ms,
                status,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                in_reply_to_message_id,
                purpose,
                model,
                int(prompt_tokens or 0),
                int(completion_tokens or 0),
                int(duration_ms) if duration_ms is not None else None,
                status,
                error,
            ),
        )
        return cursor.lastrowid

    return run_database_operation(database_path, add_call)


def sum_tokens_in_window(database_path, seconds, session_id=None, now=None):
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or seconds <= 0
    ):
        raise DatabaseError("Window must be a positive number of seconds.")

    def read_sum(connection):
        if now is not None:
            reference = datetime.fromtimestamp(now, tz=timezone.utc)
        else:
            reference = datetime.now(tz=timezone.utc)
        cutoff = (reference - timedelta(seconds=seconds)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if session_id is None:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0)
                FROM api_calls
                WHERE created_at >= ?
                """,
                (cutoff,),
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT COALESCE(SUM(prompt_tokens + completion_tokens), 0)
                FROM api_calls
                WHERE created_at >= ? AND session_id = ?
                """,
                (cutoff, session_id),
            ).fetchone()
        return row[0]

    return run_database_operation(database_path, read_sum)


def block_session(database_path, session_id, reason, blocked_at=None):
    session_id = validate_session_id(session_id)
    if not isinstance(reason, str) or not reason.strip():
        raise DatabaseError("Block reason must not be empty.")
    if blocked_at is None:
        blocked_at = time.time()
    if isinstance(blocked_at, bool) or not isinstance(blocked_at, (int, float)):
        raise DatabaseError("Block time must be a number.")

    def add_block(connection):
        connection.execute(
            """
            INSERT OR IGNORE INTO blocked_sessions (session_id, blocked_at, reason)
            VALUES (?, ?, ?)
            """,
            (session_id, blocked_at, reason),
        )

    run_database_operation(database_path, add_block)


def reset_history(database_path, session_id):
    session_id = validate_session_id(session_id)

    def archive_messages(connection):
        connection.execute(
            """
            UPDATE messages
            SET archived = 1
            WHERE session_id = ? AND archived = 0
            """,
            (session_id,),
        )

    run_database_operation(database_path, archive_messages)


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
