import time

from app_config import get_token_abuse_settings, get_tpm_limit
from app_logging import get_logger
from database import block_session, sum_tokens_in_window


TPM_WINDOW_SECONDS = 60
MAX_WAIT_SECONDS = 600
CHECK_INTERVAL_SECONDS = 2
LOG_INTERVAL_SECONDS = 30

logger = get_logger("tokens")


class TokenLimitError(RuntimeError):
    pass


class SessionContextTooLargeError(TokenLimitError):
    pass


def wait_for_token_budget(
    database_path,
    estimated_tokens,
    tpm_limit=None,
    clock=time.time,
    sleep_fn=time.sleep,
    max_wait_seconds=MAX_WAIT_SECONDS,
):
    if tpm_limit is None:
        tpm_limit = get_tpm_limit()
    if tpm_limit <= 0:
        return

    if estimated_tokens > tpm_limit:
        raise SessionContextTooLargeError(
            f"Estimated request size {estimated_tokens} tokens exceeds "
            f"the whole TPM limit of {tpm_limit}."
        )

    started_at = clock()
    last_logged_at = None
    while True:
        used = sum_tokens_in_window(
            database_path,
            TPM_WINDOW_SECONDS,
            now=clock(),
        )
        if used + estimated_tokens <= tpm_limit:
            return

        waited = clock() - started_at
        if waited >= max_wait_seconds:
            raise TokenLimitError(
                "Token budget stayed above the TPM limit for over "
                f"{max_wait_seconds} seconds."
            )

        if last_logged_at is None or clock() - last_logged_at >= LOG_INTERVAL_SECONDS:
            logger.info(
                "🚦 TPM limit reached | used=%d estimated=%d limit=%d",
                used,
                estimated_tokens,
                tpm_limit,
            )
            last_logged_at = clock()
        sleep_fn(CHECK_INTERVAL_SECONDS)


def guard_session_consumption(database_path, session_id, now=None):
    limit, window_seconds = get_token_abuse_settings()
    if limit <= 0 or window_seconds <= 0:
        return False

    used = sum_tokens_in_window(
        database_path,
        window_seconds,
        session_id=session_id,
        now=now,
    )
    if used <= limit:
        return False

    block_session(
        database_path,
        session_id,
        f"Used more than {limit} tokens in {window_seconds} seconds",
        blocked_at=now,
    )
    logger.warning(
        "🚫 Session blocked for token abuse | session=%s used=%d limit=%d window=%ds",
        session_id,
        used,
        limit,
        window_seconds,
    )
    return True
