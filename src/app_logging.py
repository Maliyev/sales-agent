import hashlib
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAME = "sales_agent"
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_BACKUP_COUNT = 3


logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())


def configure_logging(
    log_path,
    level=logging.INFO,
    max_bytes=DEFAULT_MAX_BYTES,
    backup_count=DEFAULT_BACKUP_COUNT,
):
    path = Path(log_path)

    logger = logging.getLogger(LOGGER_NAME)
    _remove_handlers(logger)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError as error:
        logger.error("File logging is unavailable | path=%s error=%s", path, error)
    else:
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Werkzeug otherwise logs the full webhook verification URL, including
    # the private verify token in its query string.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    return logger


def close_logging():
    logger = logging.getLogger(LOGGER_NAME)
    _remove_handlers(logger)
    logger.addHandler(logging.NullHandler())


def _remove_handlers(logger):
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def get_logger(component):
    return logging.getLogger(f"{LOGGER_NAME}.{component}")


def session_reference(session_id):
    if not isinstance(session_id, str) or not session_id:
        return "unknown"

    channel = session_id.split(":", maxsplit=1)[0] or "session"
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:10]
    return f"{channel}:{digest}"
