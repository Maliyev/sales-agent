import time

from database import record_incoming_message


MAX_MESSAGES = 15
WINDOW_SECONDS = 60


def is_message_allowed(database_path, session_id, now=None):
    if now is None:
        now = time.time()

    return record_incoming_message(
        database_path,
        session_id,
        now,
        MAX_MESSAGES,
        WINDOW_SECONDS,
    )
