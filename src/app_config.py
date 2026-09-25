import json
import os
import re
import tempfile
from pathlib import Path
from threading import Lock

from app_logging import get_logger


logger = get_logger("config")

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"

THINKING_LEVELS = frozenset({"minimal", "low", "medium", "high"})
OPENROUTER_REASONING_EFFORTS = frozenset(
    {"", "none", "minimal", "low", "medium", "high", "xhigh", "max"}
)

DEFAULT_CONFIG = {
    "gemini": {
        "model": "gemini-2.5-flash-lite",
        "vision_model": "",
        "tpm_limit": 0,
        "thinking_level": "",
        "retry": {
            "delays": [15, 30, 60, 120, 240],
            "max_wait_seconds": 600,
        },
    },
    "openrouter": {
        "enabled": False,
        "model": "",
        "reasoning_effort": "",
        "allowed_numbers": [],
    },
    "limits": {
        "max_search_rounds": 3,
        "max_api_calls_per_reply": 70,
        "list_mode_enabled": True,
        "message_rate": {
            "max_messages": 15,
            "window_seconds": 60,
        },
        "token_abuse": {
            "limit": 0,
            "window_seconds": 60,
        },
        "context_overflow": {
            "auto_reset": True,
            "auto_compaction": False,
            "compaction_model": "",
            "context_token_limit": 0,
        },
    },
}

_cached_config = None
_cached_stamp = None
_no_rejected_stamp = object()
_rejected_stamp = _no_rejected_stamp
_config_override = None
_config_lock = Lock()


class ConfigError(RuntimeError):
    pass


def load_config(path=None):
    path = Path(path) if path is not None else CONFIG_PATH
    config = _deep_copy(DEFAULT_CONFIG)

    if not path.exists():
        logger.warning(
            "⚠️ Config file is missing, defaults are used | path=%s",
            path,
        )
        return config

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"Config file is invalid: {error}") from error

    if not isinstance(raw, dict):
        raise ConfigError("Config file must contain a JSON object.")

    try:
        _merge_into(config, raw)
        _validate_config(config)
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError(f"Config file has an invalid structure: {error}") from error
    return config


def get_config():
    global _cached_config, _cached_stamp, _rejected_stamp
    with _config_lock:
        if _config_override is not None:
            return _config_override

        try:
            stat = CONFIG_PATH.stat()
            stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        except FileNotFoundError:
            stamp = None
        except OSError as error:
            if _cached_config is None:
                raise ConfigError(f"Cannot read config file: {error}") from error
            logger.warning("Could not check config file; keeping previous settings: %s", error)
            return _cached_config

        if _cached_config is None or (stamp != _cached_stamp and stamp != _rejected_stamp):
            try:
                updated = load_config()
            except ConfigError as error:
                if _cached_config is None:
                    raise
                _rejected_stamp = stamp
                logger.warning("Invalid config file; keeping previous settings: %s", error)
            else:
                if _cached_config is not None:
                    logger.info("Config file changed; new settings applied")
                _cached_config = updated
                _cached_stamp = stamp
                _rejected_stamp = _no_rejected_stamp

        return _cached_config


def set_config(config):
    global _cached_config, _cached_stamp, _rejected_stamp, _config_override
    with _config_lock:
        _config_override = config
        if config is None:
            _cached_config = None
            _cached_stamp = None
            _rejected_stamp = _no_rejected_stamp


def editable_config():
    """Return only known, non-secret configuration keys."""
    return _known_keys(get_config(), DEFAULT_CONFIG)


def save_config(config):
    """Validate and atomically replace the file read by the running agent."""
    global _cached_config, _cached_stamp, _rejected_stamp
    if not isinstance(config, dict) or not _same_keys(config, DEFAULT_CONFIG):
        raise ConfigError("Configuration has missing or unknown fields.")
    candidate = _deep_copy(config)
    try:
        _validate_config(candidate)
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError(f"Configuration has an invalid structure: {error}") from error
    temporary = None
    with _config_lock:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=CONFIG_PATH.parent,
                prefix=".config-", suffix=".json", delete=False,
            ) as file:
                temporary = Path(file.name)
                json.dump(candidate, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, CONFIG_PATH)
            stat = CONFIG_PATH.stat()
        except OSError as error:
            logger.error("Could not save config file: %s", error)
            raise ConfigError("Could not save config file.") from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        _cached_config = candidate
        _cached_stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
        _rejected_stamp = _no_rejected_stamp
    logger.info("Config saved from admin dashboard")
    return _deep_copy(candidate)


def _known_keys(source, shape):
    return {
        key: _known_keys(source[key], value) if isinstance(value, dict) else _deep_copy(source[key])
        for key, value in shape.items()
    }


def _same_keys(value, shape):
    return isinstance(value, dict) and value.keys() == shape.keys() and all(
        _same_keys(value[key], item) if isinstance(item, dict) else True
        for key, item in shape.items()
    )


def get_gemini_model():
    return get_config()["gemini"]["model"]


def get_openrouter_settings():
    return get_config().get("openrouter", DEFAULT_CONFIG["openrouter"])


def get_vision_model():
    vision_model = get_config()["gemini"].get("vision_model", "")
    if isinstance(vision_model, str) and vision_model.strip():
        return vision_model.strip()
    return get_gemini_model()


def get_tpm_limit():
    return get_config()["gemini"]["tpm_limit"]


def get_thinking_level():
    return get_config()["gemini"].get("thinking_level", "")


def get_gemini_retry_settings():
    retry = get_config()["gemini"]["retry"]
    return list(retry["delays"]), retry["max_wait_seconds"]


def get_message_rate_limits():
    limits = get_config()["limits"]["message_rate"]
    return limits["max_messages"], limits["window_seconds"]


def get_token_abuse_settings():
    limits = get_config()["limits"]["token_abuse"]
    return limits["limit"], limits["window_seconds"]


def get_context_overflow_auto_reset():
    return get_config()["limits"]["context_overflow"]["auto_reset"]


def get_context_overflow_auto_compaction():
    return get_config()["limits"]["context_overflow"]["auto_compaction"]


def get_compaction_model():
    compaction_model = get_config()["limits"]["context_overflow"]["compaction_model"]
    if isinstance(compaction_model, str) and compaction_model.strip():
        return compaction_model.strip()
    return get_gemini_model()


def get_context_token_limit():
    return get_config()["limits"]["context_overflow"].get("context_token_limit", 0)


def get_max_search_rounds():
    return get_config()["limits"].get("max_search_rounds", 3)


def get_max_api_calls_per_reply():
    return get_config()["limits"].get("max_api_calls_per_reply", 70)


def get_list_mode_enabled():
    return get_config()["limits"].get("list_mode_enabled", True)


def _deep_copy(value):
    if isinstance(value, dict):
        return {key: _deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_deep_copy(item) for item in value]
    return value


def _merge_into(target, source):
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
        ):
            _merge_into(target[key], value)
        else:
            target[key] = value


def _validate_config(config):
    openrouter = config.get("openrouter")
    if not isinstance(openrouter, dict):
        raise ConfigError("openrouter must be an object.")
    if not isinstance(openrouter.get("enabled"), bool):
        raise ConfigError("openrouter.enabled must be a boolean.")
    model = openrouter.get("model")
    if not isinstance(model, str) or (openrouter["enabled"] and not model.strip()):
        raise ConfigError("openrouter.model must be a string and non-empty when enabled.")
    effort = openrouter.get("reasoning_effort")
    if not isinstance(effort, str) or effort not in OPENROUTER_REASONING_EFFORTS:
        raise ConfigError("openrouter.reasoning_effort has an invalid value.")
    if openrouter["enabled"] and model == "openai/gpt-6-luna" and effort != "none":
        raise ConfigError(
            "openai/gpt-6-luna requires reasoning_effort 'none' for tools "
            "with the Chat Completions API."
        )
    if openrouter["enabled"] and model == "z-ai/glm-5.3-flash" and effort not in {
        "low", "high", "max"
    }:
        raise ConfigError(
            "z-ai/glm-5.3-flash supports reasoning_effort low, high, or max."
        )
    allowed_numbers = openrouter.get("allowed_numbers")
    if not isinstance(allowed_numbers, list) or any(
        not isinstance(number, str)
        or re.fullmatch(r"\+[1-9][0-9]{7,14}", number) is None
        for number in allowed_numbers
    ):
        raise ConfigError("openrouter.allowed_numbers must contain E.164 phone numbers.")
    if len(set(allowed_numbers)) != len(allowed_numbers):
        raise ConfigError("openrouter.allowed_numbers must not contain duplicates.")
    if openrouter["enabled"] and not allowed_numbers:
        raise ConfigError("openrouter.allowed_numbers must not be empty when enabled.")

    model = config["gemini"].get("model")
    if not isinstance(model, str) or not model.strip():
        raise ConfigError("gemini.model must be a non-empty string.")
    if not isinstance(config["gemini"].get("vision_model"), str):
        raise ConfigError("gemini.vision_model must be a string.")
    _validate_non_negative_int(
        config["gemini"].get("tpm_limit"),
        "gemini.tpm_limit",
    )
    thinking_level = config["gemini"].get("thinking_level")
    if not isinstance(thinking_level, str) or (
        thinking_level and thinking_level not in THINKING_LEVELS
    ):
        raise ConfigError(
            "gemini.thinking_level must be an empty string or one of: "
            "minimal, low, medium, high."
        )
    retry = config["gemini"].get("retry")
    delays = retry.get("delays") if isinstance(retry, dict) else None
    if (
        not isinstance(delays, list)
        or not delays
        or any(
            isinstance(item, bool) or not isinstance(item, int) or item < 1
            for item in delays
        )
    ):
        raise ConfigError(
            "gemini.retry.delays must be a non-empty list of positive integers."
        )
    _validate_positive_int(
        retry.get("max_wait_seconds"),
        "gemini.retry.max_wait_seconds",
    )

    message_rate = config["limits"]["message_rate"]
    _validate_positive_int(
        config["limits"].get("max_search_rounds"),
        "limits.max_search_rounds",
    )
    _validate_positive_int(
        config["limits"].get("max_api_calls_per_reply"),
        "limits.max_api_calls_per_reply",
    )
    if not isinstance(config["limits"].get("list_mode_enabled"), bool):
        raise ConfigError("limits.list_mode_enabled must be a boolean.")
    max_messages = message_rate.get("max_messages")
    if (
        isinstance(max_messages, bool)
        or not isinstance(max_messages, int)
        or max_messages < 1
    ):
        raise ConfigError(
            "limits.message_rate.max_messages must be a positive integer."
        )
    _validate_positive_int(
        message_rate.get("window_seconds"),
        "limits.message_rate.window_seconds",
    )

    token_abuse = config["limits"]["token_abuse"]
    _validate_non_negative_int(
        token_abuse.get("limit"),
        "limits.token_abuse.limit",
    )
    _validate_positive_int(
        token_abuse.get("window_seconds"),
        "limits.token_abuse.window_seconds",
    )

    context_overflow = config["limits"]["context_overflow"]
    if not isinstance(context_overflow.get("auto_reset"), bool):
        raise ConfigError(
            "limits.context_overflow.auto_reset must be a boolean."
        )
    if not isinstance(context_overflow.get("auto_compaction"), bool):
        raise ConfigError(
            "limits.context_overflow.auto_compaction must be a boolean."
        )
    if not isinstance(context_overflow.get("compaction_model"), str):
        raise ConfigError(
            "limits.context_overflow.compaction_model must be a string."
        )
    _validate_non_negative_int(
        context_overflow.get("context_token_limit"),
        "limits.context_overflow.context_token_limit",
    )


def _validate_non_negative_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigError(f"{name} must be a non-negative integer.")


def _validate_positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{name} must be a positive integer.")
