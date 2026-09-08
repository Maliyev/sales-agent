import json
from pathlib import Path

from app_logging import get_logger


logger = get_logger("config")

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"

THINKING_LEVELS = frozenset({"minimal", "low", "medium", "high"})

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

    _merge_into(config, raw)
    _validate_config(config)
    return config


def get_config():
    global _cached_config
    if _cached_config is None:
        _cached_config = load_config()
    return _cached_config


def set_config(config):
    global _cached_config
    _cached_config = config


def get_gemini_model():
    return get_config()["gemini"]["model"]


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
