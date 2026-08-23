import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


LOGGER_NAME = "sales_agent"
CONVERSATION_LOGGER_NAME = "sales_agent_conversation"
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_BACKUP_COUNT = 3


logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())
logging.getLogger(CONVERSATION_LOGGER_NAME).addHandler(logging.NullHandler())


def configure_logging(
    log_path,
    conversation_log_path=None,
    level=logging.INFO,
    max_bytes=DEFAULT_MAX_BYTES,
    backup_count=DEFAULT_BACKUP_COUNT,
):
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass

    path = Path(log_path)

    logger = logging.getLogger(LOGGER_NAME)
    _remove_handlers(logger)
    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%y-%m-%d %H:%M:%S",
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
        logger.error("⚠️ File logging is unavailable | path=%s error=%s", path, error)
    else:
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _configure_conversation_logging(
        conversation_log_path,
        level,
        max_bytes,
        backup_count,
    )

    # Werkzeug otherwise logs the full webhook verification URL, including
    # the private verify token in its query string.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    return logger


def _configure_conversation_logging(
    conversation_log_path,
    level,
    max_bytes,
    backup_count,
):
    conversation_logger = logging.getLogger(CONVERSATION_LOGGER_NAME)
    _remove_handlers(conversation_logger)
    conversation_logger.setLevel(level)
    conversation_logger.propagate = False

    if conversation_log_path is None:
        conversation_logger.addHandler(logging.NullHandler())
        return conversation_logger

    conversation_formatter = logging.Formatter(
        "%(asctime)s | %(message)s",
        datefmt="%y-%m-%d %H:%M:%S",
    )

    try:
        conversation_path = Path(conversation_log_path)
        conversation_path.parent.mkdir(parents=True, exist_ok=True)
        conversation_handler = RotatingFileHandler(
            conversation_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
    except OSError as error:
        conversation_logger.error(
            "⚠️ Conversation file logging is unavailable | path=%s error=%s",
            conversation_path,
            error,
        )
        conversation_logger.addHandler(logging.NullHandler())
        return conversation_logger

    conversation_handler.setFormatter(conversation_formatter)
    conversation_logger.addHandler(conversation_handler)
    return conversation_logger


def close_logging():
    for name in (LOGGER_NAME, CONVERSATION_LOGGER_NAME):
        logger = logging.getLogger(name)
        _remove_handlers(logger)
        logger.addHandler(logging.NullHandler())


def _remove_handlers(logger):
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def get_logger(component):
    return logging.getLogger(f"{LOGGER_NAME}.{component}")


def get_conversation_logger():
    return logging.getLogger(CONVERSATION_LOGGER_NAME)


EVENT_EMOJI = {
    "USER": "💬",
    "DECISION": "🧠",
    "FOUND": "🔍",
    "SELECTED": "📦",
    "DIRECT_LINKS": "🔗",
    "MODEL": "🤖",
    "OPERATOR_NOTE": "❗",
    "MANUAL": "📝",
}


def log_conversation(session_id, event, detail=""):
    prefix = EVENT_EMOJI.get(event, "")
    label = f"{prefix} {event}".strip()
    message = f"{session_id} | {label}"
    if detail:
        message = f"{message} | {detail}"
    logging.getLogger(CONVERSATION_LOGGER_NAME).info(message)


def flatten_text(text):
    return (
        str(text)
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )
