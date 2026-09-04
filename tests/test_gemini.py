from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import requests

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from app_config import set_config
from gemini import (
    MAX_HISTORY_CHARACTERS,
    GeminiFatalError,
    GeminiTransientError,
    check_history_size,
    generate_content,
    get_function_call,
    get_model_reply,
    get_text_response,
)


class GeminiHistoryTests(unittest.TestCase):
    def tearDown(self):
        set_config(None)

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

    def test_sends_the_thinking_level_when_it_is_configured(self):
        set_config(
            {
                "gemini": {
                    "model": "test-model",
                    "thinking_level": "high",
                    "retry": {"delays": [1], "max_wait_seconds": 2},
                }
            }
        )
        response = Mock()
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hi"}]}}]
        }
        history = [{"role": "user", "parts": [{"text": "Hello"}]}]

        with patch("gemini.requests.post", return_value=response) as post:
            generate_content(history, "test-model", "test-key", "Be helpful.")

        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            payload["generationConfig"],
            {"thinkingConfig": {"thinkingLevel": "high"}},
        )

    def test_omits_the_thinking_config_when_it_is_not_configured(self):
        set_config(
            {
                "gemini": {
                    "model": "test-model",
                    "retry": {"delays": [1], "max_wait_seconds": 2},
                }
            }
        )
        response = Mock()
        response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Hi"}]}}]
        }
        history = [{"role": "user", "parts": [{"text": "Hello"}]}]

        with patch("gemini.requests.post", return_value=response) as post:
            generate_content(history, "test-model", "test-key", "Be helpful.")

        payload = post.call_args.kwargs["json"]
        self.assertNotIn("generationConfig", payload)

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


class GeminiRetryTests(unittest.TestCase):
    HISTORY = [{"role": "user", "parts": [{"text": "Hello"}]}]

    def setUp(self):
        self.sleeps = []

    def sleep_fn(self, seconds):
        self.sleeps.append(seconds)

    def make_response(self, status_code, body=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = body if body is not None else {
            "candidates": [{"content": {"parts": [{"text": "Hi"}]}}]
        }
        return response

    def test_retries_a_rate_limit_error_and_succeeds(self):
        rate_limited = self.make_response(
            429, {"error": {"message": "Resource exhausted"}}
        )
        ok = self.make_response(200)

        with (
            patch("gemini.get_gemini_retry_settings", return_value=([15, 30, 60], 600)),
            patch("gemini.requests.post", side_effect=[
                requests.exceptions.HTTPError(response=rate_limited),
                ok,
            ]) as post,
        ):
            data = generate_content(
                self.HISTORY, "test-model", "key", "Be helpful.", sleep_fn=self.sleep_fn
            )

        self.assertEqual(get_text_response(data), "Hi")
        self.assertEqual(self.sleeps, [15])
        self.assertEqual(post.call_count, 2)

    def test_gives_up_after_the_maximum_wait(self):
        rate_limited = self.make_response(429)

        with (
            patch("gemini.get_gemini_retry_settings", return_value=([15, 30], 100)),
            patch(
                "gemini.requests.post",
                side_effect=requests.exceptions.HTTPError(response=rate_limited),
            ) as post,
        ):
            with self.assertRaises(GeminiTransientError):
                generate_content(
                    self.HISTORY, "test-model", "key", "Be helpful.", sleep_fn=self.sleep_fn
                )

        self.assertEqual(self.sleeps, [15, 30, 30, 30])
        self.assertEqual(post.call_count, 5)

    def test_treats_server_errors_as_transient(self):
        unavailable = self.make_response(503)
        ok = self.make_response(200)

        with (
            patch("gemini.get_gemini_retry_settings", return_value=([15], 600)),
            patch("gemini.requests.post", side_effect=[
                requests.exceptions.HTTPError(response=unavailable),
                ok,
            ]),
        ):
            data = generate_content(
                self.HISTORY, "test-model", "key", "Be helpful.", sleep_fn=self.sleep_fn
            )

        self.assertEqual(self.sleeps, [15])
        self.assertEqual(get_text_response(data), "Hi")

    def test_retries_network_failures(self):
        ok = self.make_response(200)

        with (
            patch("gemini.get_gemini_retry_settings", return_value=([15], 600)),
            patch("gemini.requests.post", side_effect=[
                requests.exceptions.ConnectionError("no route to host"),
                ok,
            ]),
        ):
            data = generate_content(
                self.HISTORY, "test-model", "key", "Be helpful.", sleep_fn=self.sleep_fn
            )

        self.assertEqual(self.sleeps, [15])
        self.assertEqual(get_text_response(data), "Hi")

    def test_retries_timeouts(self):
        ok = self.make_response(200)

        with (
            patch("gemini.get_gemini_retry_settings", return_value=([15], 600)),
            patch("gemini.requests.post", side_effect=[
                requests.exceptions.Timeout("timed out"),
                ok,
            ]),
        ):
            data = generate_content(
                self.HISTORY, "test-model", "key", "Be helpful.", sleep_fn=self.sleep_fn
            )

        self.assertEqual(self.sleeps, [15])
        self.assertEqual(get_text_response(data), "Hi")

    def test_fails_fast_on_a_fatal_status(self):
        unauthorized = self.make_response(
            401, {"error": {"message": "API key not valid. Please pass a valid API key."}}
        )

        with (
            patch("gemini.get_gemini_retry_settings", return_value=([15], 600)),
            patch(
                "gemini.requests.post",
                side_effect=requests.exceptions.HTTPError(response=unauthorized),
            ) as post,
        ):
            with self.assertRaisesRegex(GeminiFatalError, "API key not valid"):
                generate_content(
                    self.HISTORY, "test-model", "key", "Be helpful.", sleep_fn=self.sleep_fn
                )

        self.assertEqual(self.sleeps, [])
        post.assert_called_once()

    def test_fatal_error_without_a_readable_body(self):
        forbidden = self.make_response(403, body=None)

        with (
            patch("gemini.get_gemini_retry_settings", return_value=([15], 600)),
            patch(
                "gemini.requests.post",
                side_effect=requests.exceptions.HTTPError(response=forbidden),
            ),
        ):
            with self.assertRaisesRegex(GeminiFatalError, "403"):
                generate_content(
                    self.HISTORY, "test-model", "key", "Be helpful.", sleep_fn=self.sleep_fn
                )

        self.assertEqual(self.sleeps, [])
