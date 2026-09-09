import json
import time

import requests

from app_config import get_gemini_retry_settings, get_thinking_level
from app_logging import get_logger


MAX_ESTIMATED_TOKENS = 250_000
CHARACTERS_PER_TOKEN = 3
MAX_HISTORY_CHARACTERS = MAX_ESTIMATED_TOKENS * CHARACTERS_PER_TOKEN

TRANSIENT_STATUS_CODES = frozenset({429, 500, 503, 504})
RETRYABLE_NETWORK_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)

logger = get_logger("gemini")


class GeminiTransientError(RuntimeError):
    pass


class GeminiFatalError(RuntimeError):
    pass


def generate_content(
    history,
    model,
    api_key,
    system_instruction,
    tools=None,
    tool_config=None,
    timeout=60,
    sleep_fn=time.sleep,
):
    check_history_size(history)
    check_system_instruction(system_instruction)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": history,
    }
    thinking_level = get_thinking_level()
    if thinking_level:
        payload["generationConfig"] = {
            "thinkingConfig": {"thinkingLevel": thinking_level}
        }
    if tools is not None:
        payload["tools"] = tools
    if tool_config is not None:
        payload["toolConfig"] = tool_config

    delays, max_wait_seconds = get_gemini_retry_settings()
    waited = 0
    attempt = 0
    while True:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except RETRYABLE_NETWORK_ERRORS as error:
            _retry_or_fail(
                None,
                error,
                delays,
                max_wait_seconds,
                waited,
                attempt,
                sleep_fn,
            )
            waited += delays[min(attempt, len(delays) - 1)]
            attempt += 1
        except requests.exceptions.HTTPError as error:
            status_code = error.response.status_code
            if status_code not in TRANSIENT_STATUS_CODES:
                raise GeminiFatalError(
                    _describe_fatal_error(status_code, error.response)
                ) from error
            _retry_or_fail(
                status_code,
                error,
                delays,
                max_wait_seconds,
                waited,
                attempt,
                sleep_fn,
            )
            waited += delays[min(attempt, len(delays) - 1)]
            attempt += 1


def _retry_or_fail(status_code, error, delays, max_wait_seconds, waited, attempt, sleep_fn):
    if waited >= max_wait_seconds:
        label = f"HTTP {status_code}" if status_code else type(error).__name__
        raise GeminiTransientError(
            f"Gemini request kept failing ({label}) for over "
            f"{max_wait_seconds} seconds."
        ) from error

    delay = delays[min(attempt, len(delays) - 1)]
    label = f"HTTP {status_code}" if status_code else type(error).__name__
    logger.warning(
        "🔁 Gemini request failed (%s) | retry in %ds | attempt=%d",
        label,
        delay,
        attempt + 1,
    )
    sleep_fn(delay)


def _describe_fatal_error(status_code, response):
    message = _extract_error_message(response)
    if message:
        return f"Gemini request failed permanently (HTTP {status_code}): {message}"
    return f"Gemini request failed permanently with HTTP status {status_code}."


def _extract_error_message(response):
    try:
        error = response.json().get("error")
    except (AttributeError, ValueError):
        return ""
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"].strip()
    return ""


def get_model_reply(history, model, api_key, system_instruction, timeout=60):
    data = generate_content(
        history,
        model,
        api_key,
        system_instruction,
        timeout=timeout,
    )
    return get_text_response(data)


def get_usage_metadata(data):
    usage = data.get("usageMetadata") if isinstance(data, dict) else None
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0}

    prompt_tokens = usage.get("promptTokenCount")
    completion_tokens = usage.get("candidatesTokenCount")
    return {
        "prompt_tokens": prompt_tokens if isinstance(prompt_tokens, int) else 0,
        "completion_tokens": (
            completion_tokens if isinstance(completion_tokens, int) else 0
        ),
    }


def get_text_response(data):
    parts = _get_response_parts(data)
    text_parts = [part["text"] for part in parts if isinstance(part.get("text"), str)]

    if not text_parts:
        raise RuntimeError("Gemini returned a response without text.")
    return "".join(text_parts)


def get_function_calls(data):
    function_calls = []
    for part in _get_response_parts(data):
        function_call = part.get("functionCall")
        if isinstance(function_call, dict):
            function_calls.append(function_call)
    return function_calls


def get_function_call(data, expected_name=None):
    for function_call in get_function_calls(data):
        if expected_name is None or function_call.get("name") == expected_name:
            return function_call
    return None


def get_function_call_part(data, expected_name=None):
    parts = get_function_call_parts(data, expected_name)
    return parts[0] if parts else None


def get_function_call_parts(data, expected_name=None):
    function_call_parts = []
    for part in _get_response_parts(data):
        function_call = part.get("functionCall")
        if isinstance(function_call, dict):
            if expected_name is None or function_call.get("name") == expected_name:
                function_call_parts.append(part)
    return function_call_parts


def _get_response_parts(data):
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (IndexError, KeyError, TypeError) as error:
        raise RuntimeError(
            f"Gemini returned an invalid response. {_describe_response_state(data)}"
        ) from error

    if not isinstance(parts, list):
        raise RuntimeError("Gemini returned an invalid response.")
    if any(not isinstance(part, dict) for part in parts):
        raise RuntimeError("Gemini returned an invalid response.")
    return parts


def _describe_response_state(data):
    if not isinstance(data, dict):
        return "The response is not a JSON object."
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        candidate = candidates[0]
        if isinstance(candidate, dict) and candidate.get("finishReason"):
            return f"finishReason={candidate['finishReason']}."
    feedback = data.get("promptFeedback")
    if isinstance(feedback, dict) and feedback.get("blockReason"):
        return f"blockReason={feedback['blockReason']}."
    return "No candidate content was returned."


def check_history_size(history):
    total_characters = 0

    for message in history:
        try:
            parts = message["parts"]
        except (KeyError, TypeError) as error:
            raise RuntimeError("Conversation history has an invalid message format.") from error

        if not isinstance(parts, list):
            raise RuntimeError("Conversation history has an invalid message format.")

        for part in parts:
            if not isinstance(part, dict):
                raise RuntimeError("Conversation history has an invalid message format.")

            text = part.get("text")
            if isinstance(text, str):
                total_characters += len(text)
            elif (
                "functionCall" in part
                or "functionResponse" in part
                or "inline_data" in part
                or "inlineData" in part
            ):
                total_characters += len(json.dumps(part, ensure_ascii=False))
            else:
                raise RuntimeError("Conversation history has an invalid message format.")

    if total_characters > MAX_HISTORY_CHARACTERS:
        estimated_tokens = total_characters // CHARACTERS_PER_TOKEN
        raise RuntimeError(
            "Conversation history is too long "
            f"(about {estimated_tokens:,} tokens). The limit is 250,000 tokens. "
            "Start a new session or wait for conversation summaries to be added."
        )


def check_system_instruction(system_instruction):
    if not isinstance(system_instruction, str) or not system_instruction.strip():
        raise RuntimeError("System instruction is missing or invalid.")
