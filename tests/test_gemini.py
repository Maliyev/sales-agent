from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from gemini import (
    MAX_HISTORY_CHARACTERS,
    check_history_size,
    generate_content,
    get_function_call,
    get_model_reply,
    get_text_response,
)


class GeminiHistoryTests(unittest.TestCase):
    def test_allows_history_under_the_limit(self):
        history = [{"role": "user", "parts": [{"text": "Hello"}]}]

        check_history_size(history)

    def test_rejects_history_over_the_limit(self):
        history = [
            {
                "role": "user",
                "parts": [{"text": "a" * (MAX_HISTORY_CHARACTERS + 1)}],
            }
        ]

        with self.assertRaisesRegex(RuntimeError, "250,000 tokens"):
            check_history_size(history)

    def test_rejects_invalid_history_format(self):
        history = [{"role": "user", "parts": [{}]}]

        with self.assertRaisesRegex(RuntimeError, "invalid message format"):
            check_history_size(history)

    def test_sends_system_instruction_separately_from_history(self):
        response = Mock()
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hi"}]}}]
        }
        history = [{"role": "user", "parts": [{"text": "Hello"}]}]

        with patch("gemini.requests.post", return_value=response) as post:
            get_model_reply(history, "test-model", "test-key", "Be helpful.")

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["contents"], history)
        self.assertEqual(
            payload["systemInstruction"]["parts"][0]["text"], "Be helpful."
        )

    def test_sends_optional_tool_configuration(self):
        response = Mock()
        response.json.return_value = {"candidates": [{"content": {"parts": []}}]}
        history = [{"role": "user", "parts": [{"text": "Find Arduino"}]}]
        tools = [{"functionDeclarations": [{"name": "search_products"}]}]
        tool_config = {"functionCallingConfig": {"mode": "ANY"}}

        with patch("gemini.requests.post", return_value=response) as post:
            generate_content(
                history,
                "test-model",
                "test-key",
                "Be helpful.",
                tools=tools,
                tool_config=tool_config,
            )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["tools"], tools)
        self.assertEqual(payload["toolConfig"], tool_config)

    def test_reads_text_and_function_calls_from_all_parts(self):
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "First "},
                            {"functionCall": {"name": "search_products", "args": {}}},
                            {"text": "second"},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(get_text_response(data), "First second")
        self.assertEqual(get_function_call(data)["name"], "search_products")
