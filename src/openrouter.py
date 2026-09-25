"""OpenRouter chat completion adapter for the agent's Gemini-shaped messages."""

import json

import requests


API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_COMPLETION_TOKENS = 8192


class OpenRouterError(RuntimeError):
    pass


def generate_content(
    history,
    model,
    api_key,
    system_instruction,
    tools=None,
    tool_config=None,
    timeout=60,
    reasoning_effort="",
    max_completion_tokens=MAX_COMPLETION_TOKENS,
):
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is missing.")
    payload = {
        "model": model,
        "messages": _to_messages(history, system_instruction),
    }
    token_limit_field = (
        "max_completion_tokens" if model.startswith("openai/") else "max_tokens"
    )
    payload[token_limit_field] = max_completion_tokens
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    if tools is not None:
        payload["tools"] = _to_tools(tools)
    if tool_config is not None:
        payload["tool_choice"] = _to_tool_choice(tool_config)

    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.HTTPError as error:
        raise OpenRouterError(
            f"OpenRouter request failed (HTTP {error.response.status_code})."
        ) from error
    except requests.exceptions.RequestException as error:
        raise OpenRouterError(
            f"OpenRouter request failed ({type(error).__name__})."
        ) from error
    except ValueError as error:
        raise OpenRouterError("OpenRouter returned invalid JSON.") from error
    return _to_gemini_response(data)


def _to_messages(history, system_instruction):
    messages = [{"role": "system", "content": system_instruction}]
    pending_tool_ids = []
    for turn in history:
        if not isinstance(turn, dict) or not isinstance(turn.get("parts"), list):
            raise OpenRouterError("Conversation history has an invalid format.")
        role = turn.get("role")
        parts = turn["parts"]
        if role == "model":
            content = []
            calls = []
            reasoning_details = None
            for part in parts:
                if not isinstance(part, dict):
                    raise OpenRouterError("Conversation history has an invalid part.")
                if isinstance(part.get("text"), str):
                    content.append(part["text"])
                elif isinstance(part.get("functionCall"), dict):
                    function = part["functionCall"]
                    call_id = part.get("_openrouter_id") or f"call_{len(messages)}_{len(calls)}"
                    calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": function["name"],
                                "arguments": json.dumps(function.get("args", {})),
                            },
                        }
                    )
                    if reasoning_details is None:
                        reasoning_details = part.get("_openrouter_reasoning_details")
                else:
                    raise OpenRouterError("Conversation history has an unsupported model part.")
            message = {"role": "assistant", "content": "".join(content) or None}
            if calls:
                message["tool_calls"] = calls
                pending_tool_ids = [call["id"] for call in calls]
            if reasoning_details is not None:
                message["reasoning_details"] = reasoning_details
            messages.append(message)
        elif role == "user":
            content = []
            response_index = 0
            for part in parts:
                if not isinstance(part, dict):
                    raise OpenRouterError("Conversation history has an invalid part.")
                if isinstance(part.get("text"), str):
                    content.append({"type": "text", "text": part["text"]})
                elif isinstance(part.get("functionResponse"), dict):
                    if response_index >= len(pending_tool_ids):
                        raise OpenRouterError("A tool response has no matching tool call.")
                    result = part["functionResponse"].get("response", {})
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": pending_tool_ids[response_index],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                    response_index += 1
                elif isinstance(part.get("inline_data"), dict):
                    image = part["inline_data"]
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image['mime_type']};base64,{image['data']}"
                            },
                        }
                    )
                else:
                    raise OpenRouterError("Conversation history has an unsupported user part.")
            if response_index:
                pending_tool_ids = []
            if content:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            content[0]["text"]
                            if len(content) == 1 and content[0]["type"] == "text"
                            else content
                        ),
                    }
                )
        else:
            raise OpenRouterError("Conversation history has an unsupported role.")
    return messages


def _to_tools(tools):
    converted = []
    for group in tools:
        for declaration in group["functionDeclarations"]:
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": declaration["name"],
                        "description": declaration.get("description", ""),
                        "parameters": _lowercase_schema_types(declaration["parameters"]),
                    },
                }
            )
    return converted


def _lowercase_schema_types(value):
    if isinstance(value, list):
        return [_lowercase_schema_types(item) for item in value]
    if isinstance(value, dict):
        return {
            key: item.lower() if key == "type" and isinstance(item, str)
            else _lowercase_schema_types(item)
            for key, item in value.items()
        }
    return value


def _to_tool_choice(tool_config):
    config = tool_config["functionCallingConfig"]
    names = config["allowedFunctionNames"]
    if config["mode"] != "ANY" or len(names) != 1:
        raise OpenRouterError("Unsupported tool selection configuration.")
    return {"type": "function", "function": {"name": names[0]}}


def _to_gemini_response(data):
    try:
        message = data["choices"][0]["message"]
        content = message.get("content")
        tool_calls = message.get("tool_calls") or []
        parts = []
        if isinstance(content, str) and content:
            parts.append({"text": content})
        for call in tool_calls:
            function = call["function"]
            args = json.loads(function["arguments"])
            if not isinstance(args, dict):
                raise ValueError("Tool arguments are not an object.")
            part = {
                "functionCall": {"name": function["name"], "args": args},
                "_openrouter_id": call["id"],
            }
            if message.get("reasoning_details") is not None:
                part["_openrouter_reasoning_details"] = message["reasoning_details"]
            parts.append(part)
        if not parts:
            raise ValueError("The model returned no text or tool call.")
        usage = data.get("usage") or {}
        return {
            "candidates": [{"content": {"parts": parts}}],
            "usageMetadata": {
                "promptTokenCount": usage.get("prompt_tokens", 0),
                "candidatesTokenCount": usage.get("completion_tokens", 0),
            },
        }
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise OpenRouterError("OpenRouter returned an invalid completion.") from error
