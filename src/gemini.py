import requests


MAX_ESTIMATED_TOKENS = 250_000
CHARACTERS_PER_TOKEN = 3
MAX_HISTORY_CHARACTERS = MAX_ESTIMATED_TOKENS * CHARACTERS_PER_TOKEN


def generate_content(
    history,
    model,
    api_key,
    system_instruction,
    tools=None,
    tool_config=None,
    timeout=60,
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
    if tools is not None:
        payload["tools"] = tools
    if tool_config is not None:
        payload["toolConfig"] = tool_config

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_model_reply(history, model, api_key, system_instruction, timeout=60):
    data = generate_content(
        history,
        model,
        api_key,
        system_instruction,
        timeout=timeout,
    )
    return get_text_response(data)


def get_text_response(data):
    parts = _get_response_parts(data)
    text_parts = [part["text"] for part in parts if isinstance(part.get("text"), str)]

    if not text_parts:
        raise RuntimeError("Gemini returned a response without text.")
    return "".join(text_parts)


def get_function_call(data, expected_name=None):
    for part in _get_response_parts(data):
        function_call = part.get("functionCall")
        if not isinstance(function_call, dict):
            continue
        if expected_name is None or function_call.get("name") == expected_name:
            return function_call
    return None


def _get_response_parts(data):
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (IndexError, KeyError, TypeError) as error:
        raise RuntimeError("Gemini returned an invalid response.") from error

    if not isinstance(parts, list):
        raise RuntimeError("Gemini returned an invalid response.")
    if any(not isinstance(part, dict) for part in parts):
        raise RuntimeError("Gemini returned an invalid response.")
    return parts


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
            try:
                text = part["text"]
            except (KeyError, TypeError) as error:
                raise RuntimeError("Conversation history has an invalid message format.") from error

            if not isinstance(text, str):
                raise RuntimeError("Conversation history has an invalid message format.")

            total_characters += len(text)

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
