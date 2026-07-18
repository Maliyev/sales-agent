import requests


MAX_ESTIMATED_TOKENS = 250_000
CHARACTERS_PER_TOKEN = 3
MAX_HISTORY_CHARACTERS = MAX_ESTIMATED_TOKENS * CHARACTERS_PER_TOKEN


def get_model_reply(history, model, api_key, system_instruction, timeout=60):
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

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()

    data = response.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (IndexError, KeyError, TypeError) as error:
        raise RuntimeError("Gemini returned a response without text.") from error


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
