import time

from app_config import get_message_rate_limits
from database import record_incoming_message


def is_message_allowed(database_path, session_id, now=None):
    if now is None:
        now = time.time()

    max_messages, window_seconds = get_message_rate_limits()

    return record_incoming_message(
        database_path,
        session_id,
        now,
        max_messages,
        window_seconds,
    )
