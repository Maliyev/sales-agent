from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from gemini import get_function_call, get_text_response, get_usage_metadata
from agent import get_agent_reply
from openrouter import OpenRouterError, generate_content


class OpenRouterAdapterTests(unittest.TestCase):
    @patch("openrouter.requests.post")
    def test_agent_search_selection_and_final_reply(self, post):
        def reply(message):
            response = Mock()
            response.json.return_value = {"choices": [{"message": message}]}
            return response

        post.side_effect = [
            reply(
                {
                    "content": None,
                    "reasoning_details": [{"type": "reasoning.text", "text": "search"}],
                    "tool_calls": [
                        {
                            "id": "search_1",
                            "function": {
                                "name": "search_products",
                                "arguments": '{"query":"laptop"}',
                            },
                        }
                    ],
                }
            ),
            reply({"content": "I found enough candidates."}),
            reply(
                {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "selection_1",
                            "function": {
                                "name": "select_product_candidates",
                                "arguments": '{"candidate_ids":[1],"needs_clarification":false,"clarifying_question":""}',
                            },
                        }
                    ],
                }
            ),
            reply({"content": "This laptop is available."}),
        ]

        result = get_agent_reply(
            [],
            "Do you have this laptop?",
            "openai/gpt-6-luna",
            "test-key",
            "Search instruction",
            "Selection instruction",
            "Reply instruction",
            search_fn=lambda query, max_results: [
                {"url": "https://elen.az/shop/1/desc/laptop", "title": "Laptop"}
            ],
            product_data_fn=lambda url: {"title": "Laptop", "url": url},
            generate_fn=generate_content,
        )

        self.assertEqual(result.customer_reply, "This laptop is available.")
        self.assertEqual(post.call_count, 4)
        second_messages = post.call_args_list[1].kwargs["json"]["messages"]
        self.assertEqual(second_messages[-2]["tool_calls"][0]["id"], "search_1")
        self.assertEqual(
            second_messages[-2]["reasoning_details"],
            [{"type": "reasoning.text", "text": "search"}],
        )
        self.assertEqual(second_messages[-1]["tool_call_id"], "search_1")

    @patch("openrouter.requests.post")
    def test_converts_text_completion_and_usage(self, post):
        post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Hello", "tool_calls": None}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3},
        }

        result = generate_content(
            [{"role": "user", "parts": [{"text": "Hi"}]}],
            "openai/gpt-6-luna",
            "test-key",
            "Be helpful",
            reasoning_effort="none",
        )

        self.assertEqual(get_text_response(result), "Hello")
        self.assertEqual(
            get_usage_metadata(result),
            {"prompt_tokens": 12, "completion_tokens": 3},
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["messages"],
            [
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hi"},
            ],
        )
        self.assertEqual(post.call_args.kwargs["json"]["model"], "openai/gpt-6-luna")
        self.assertEqual(
            post.call_args.kwargs["json"]["reasoning"], {"effort": "none"}
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["max_completion_tokens"], 8192
        )
        self.assertEqual(
            post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key"
        )

    @patch("openrouter.requests.post")
    def test_converts_tool_schema_response_and_followup(self, post):
        post.return_value.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {
                                    "name": "search_products",
                                    "arguments": '{"query":"laptop"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
        tools = [
            {
                "functionDeclarations": [
                    {
                        "name": "search_products",
                        "description": "Search",
                        "parameters": {
                            "type": "OBJECT",
                            "properties": {"query": {"type": "STRING"}},
                        },
                    }
                ]
            }
        ]
        response = generate_content(
            [{"role": "user", "parts": [{"text": "Find a laptop"}]}],
            "openai/gpt-6-luna",
            "test-key",
            "Search products",
            tools=tools,
        )
        self.assertEqual(
            get_function_call(response, "search_products"),
            {"name": "search_products", "args": {"query": "laptop"}},
        )
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["tools"][0]["function"]["parameters"]["type"], "object")
        self.assertEqual(
            payload["tools"][0]["function"]["parameters"]["properties"]["query"]["type"],
            "string",
        )

        search_part = response["candidates"][0]["content"]["parts"][0]
        generate_content(
            [
                {"role": "user", "parts": [{"text": "Find a laptop"}]},
                {"role": "model", "parts": [search_part]},
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "search_products",
                                "response": {"results": []},
                            }
                        }
                    ],
                },
            ],
            "openai/gpt-6-luna",
            "test-key",
            "Search products",
            tools=tools,
        )
        messages = post.call_args.kwargs["json"]["messages"]
        self.assertEqual(messages[2]["tool_calls"][0]["id"], "call_123")
        self.assertEqual(messages[3]["role"], "tool")
        self.assertEqual(messages[3]["tool_call_id"], "call_123")

    @patch("openrouter.requests.post")
    def test_glm_uses_reasoning_effort_and_its_token_limit_field(self, post):
        post.return_value.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }
        generate_content(
            [{"role": "user", "parts": [{"text": "Hi"}]}],
            "z-ai/glm-5.3-flash",
            "test-key",
            "Reply briefly",
            reasoning_effort="high",
        )
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["reasoning"], {"effort": "high"})
        self.assertEqual(payload["max_tokens"], 8192)
        self.assertNotIn("max_completion_tokens", payload)

    @patch("openrouter.requests.post")
    def test_forced_selection_uses_named_tool_choice(self, post):
        post.return_value.json.return_value = {
            "choices": [{"message": {"content": "done"}}]
        }
        generate_content(
            [{"role": "user", "parts": [{"text": "Select"}]}],
            "openai/gpt-6-luna",
            "test-key",
            "Choose",
            tools=[{"functionDeclarations": []}],
            tool_config={
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": ["select_product_candidates"],
                }
            },
        )
        self.assertEqual(
            post.call_args.kwargs["json"]["tool_choice"],
            {"type": "function", "function": {"name": "select_product_candidates"}},
        )

    @patch("openrouter.requests.post")
    def test_missing_key_never_sends_a_request(self, post):
        with self.assertRaises(OpenRouterError):
            generate_content([], "openai/gpt-6-luna", "", "System")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
