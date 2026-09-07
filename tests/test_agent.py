from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from agent import AgentError, _estimate_tokens, get_agent_reply
from agent_reply import AgentReply
from app_config import set_config
from database import initialize_database, insert_incoming_message


def text_response(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def function_response(name, args):
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"functionCall": {"name": name, "args": args}}]
                }
            }
        ]
    }


class FakeGemini:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, history, model, api_key, system_instruction, **kwargs):
        self.calls.append(
            {
                "history": history,
                "system_instruction": system_instruction,
                "kwargs": kwargs,
            }
        )
        return self.responses.pop(0)


class AgentTests(unittest.TestCase):
    def setUp(self):
        set_config({"limits": {"max_search_rounds": 3}})
        self.history = [
            {"role": "user", "parts": [{"text": "I need an electronic part"}]},
            {"role": "model", "parts": [{"text": "What specifications?"}]},
        ]
        self.results = [
            {
                "title": "Irrelevant motor",
                "price": 5.0,
                "currency": "AZN",
                "availability": "in_stock",
                "stock_quantity": 2,
                "url": "https://www.elen.az/shop/1/desc/motor",
            },
            {
                "title": "Diode 1N4007 1000V",
                "price": 0.1,
                "currency": "AZN",
                "availability": "in_stock",
                "stock_quantity": 20,
                "url": "https://www.elen.az/shop/2/desc/diode",
            },
            {
                "title": "Diode kit",
                "price": 4.0,
                "currency": "AZN",
                "availability": "in_stock",
                "stock_quantity": 3,
                "url": "https://www.elen.az/shop/3/desc/diode-kit",
            },
        ]

    def call_agent(
        self,
        gemini,
        search_fn=None,
        product_data_fn=None,
        final_system_instruction=None,
    ):
        if search_fn is None:
            search_fn = lambda query, max_results: self.results
        if product_data_fn is None:
            product_data_fn = lambda url: {"title": "Verified diode", "url": url}

        return get_agent_reply(
            self.history,
            "At least 200 volts",
            "model",
            "key",
            "base prompt",
            "selection prompt",
            "response prompt",
            final_system_instruction=final_system_instruction,
            search_fn=search_fn,
            product_data_fn=product_data_fn,
            generate_fn=gemini,
        )

    def tearDown(self):
        set_config(None)

    def test_returns_direct_answer_without_search(self):
        gemini = FakeGemini([text_response("Please specify the package.")])
        original_history = list(self.history)

        reply = self.call_agent(gemini)

        self.assertEqual(reply, AgentReply("Please specify the package."))
        self.assertEqual(self.history, original_history)
        self.assertEqual(len(gemini.calls), 1)

    def test_reads_a_direct_product_link_without_search(self):
        gemini = FakeGemini([text_response("This product is in stock.")])
        product_calls = []

        def search_fn(query, max_results):
            self.fail("Product search should not run for a direct link.")

        def product_data_fn(url):
            product_calls.append(url)
            return {"title": "Arduino Uno", "stock_quantity": 4, "url": url}

        url = "https://www.elen.az/shop/101/desc/arduino-uno"
        reply = get_agent_reply(
            self.history,
            f"Is this available? {url}",
            "model",
            "key",
            "base prompt",
            "selection prompt",
            "response prompt",
            search_fn=search_fn,
            product_data_fn=product_data_fn,
            generate_fn=gemini,
        )

        self.assertEqual(reply, AgentReply("This product is in stock."))
        self.assertEqual(product_calls, [url])
        self.assertEqual(len(gemini.calls), 1)
        final_text = gemini.calls[0]["history"][-1]["parts"][0]["text"]
        self.assertIn("Arduino Uno", final_text)
        self.assertIn("response prompt", gemini.calls[0]["system_instruction"])

    def test_reads_each_direct_product_link_only_once(self):
        gemini = FakeGemini([text_response("Here is the comparison.")])
        product_calls = []
        first_url = "https://elen.az/shop/1/desc/first"
        second_url = "https://www.elen.az/shop/2/desc/second"

        reply = get_agent_reply(
            self.history,
            f"Compare {first_url}, {second_url} and again {first_url}",
            "model",
            "key",
            "base prompt",
            "selection prompt",
            "response prompt",
            search_fn=lambda query, max_results: self.fail(
                "Product search should not run for direct links."
            ),
            product_data_fn=lambda url: product_calls.append(url) or {"url": url},
            generate_fn=gemini,
        )

        self.assertEqual(reply, AgentReply("Here is the comparison."))
        self.assertEqual(product_calls, [first_url, second_url])

    def test_does_not_open_a_link_from_a_false_elen_domain(self):
        gemini = FakeGemini([text_response("I cannot verify that link.")])
        false_url = "https://www.elen.az.example.com/shop/1/desc/fake"

        reply = get_agent_reply(
            self.history,
            false_url,
            "model",
            "key",
            "base prompt",
            "selection prompt",
            "response prompt",
            search_fn=lambda query, max_results: self.results,
            product_data_fn=lambda url: self.fail("A false elen.az URL was opened."),
            generate_fn=gemini,
        )

        self.assertEqual(reply, AgentReply("I cannot verify that link."))
        self.assertEqual(len(gemini.calls), 1)

    def test_operator_request_returns_separate_messages_without_search(self):
        gemini = FakeGemini(
            [
                function_response(
                    "request_operator",
                    {
                        "customer_reply": "Please contact our operator.",
                        "operator_message": "The customer is ready to order.",
                    },
                )
            ]
        )

        reply = self.call_agent(
            gemini,
            search_fn=lambda query, max_results: self.fail(
                "Search should not run after an operator request."
            ),
        )

        self.assertEqual(
            reply,
            AgentReply(
                "Please contact our operator.",
                "The customer is ready to order.",
            ),
        )
        declarations = gemini.calls[0]["kwargs"]["tools"][0][
            "functionDeclarations"
        ]
        self.assertIn("request_operator", [item["name"] for item in declarations])

    def test_operator_request_can_be_returned_after_product_details(self):
        gemini = FakeGemini(
            [
                function_response(
                    "request_operator",
                    {
                        "customer_reply": "The operator will help with the order.",
                        "operator_message": "Customer wants to order Arduino Uno.",
                    },
                )
            ]
        )
        url = "https://www.elen.az/shop/101/desc/arduino-uno"

        reply = get_agent_reply(
            self.history,
            f"I want to order this: {url}",
            "model",
            "key",
            "base prompt",
            "selection prompt",
            "response prompt",
            product_data_fn=lambda product_url: {"title": "Arduino Uno"},
            generate_fn=gemini,
        )

        self.assertEqual(
            reply.operator_message,
            "Customer wants to order Arduino Uno.",
        )
        declarations = gemini.calls[0]["kwargs"]["tools"][0][
            "functionDeclarations"
        ]
        self.assertEqual([item["name"] for item in declarations], ["request_operator"])

    def test_operator_request_requires_both_messages(self):
        gemini = FakeGemini(
            [
                function_response(
                    "request_operator",
                    {
                        "customer_reply": "Please contact the operator.",
                        "operator_message": "",
                    },
                )
            ]
        )

        with self.assertRaisesRegex(AgentError, "empty operator message"):
            self.call_agent(gemini)

    def test_full_search_list_exists_only_in_selection_call(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode 200V"}),
                text_response("The search results look good."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [2, 3],
                        "needs_clarification": True,
                        "clarifying_question": "Do you need one diode or a kit?",
                    },
                ),
                text_response("Do you need one diode or a kit?"),
            ]
        )
        search_calls = []
        detail_calls = []

        def search_fn(query, max_results):
            search_calls.append((query, max_results))
            return self.results

        def product_data_fn(url):
            detail_calls.append(url)
            return {"title": f"Verified {url.rsplit('/', 1)[-1]}", "url": url}

        original_history = list(self.history)
        reply = self.call_agent(gemini, search_fn, product_data_fn)

        self.assertEqual(reply, AgentReply("Do you need one diode or a kit?"))
        self.assertEqual(search_calls, [("diode 200V", 30)])
        self.assertEqual(len(gemini.calls), 4)
        self.assertEqual(
            detail_calls,
            [self.results[1]["url"], self.results[2]["url"]],
        )
        selection_text = gemini.calls[2]["history"][-1]["parts"][0]["text"]
        final_text = gemini.calls[3]["history"][-1]["parts"][0]["text"]
        self.assertIn("Irrelevant motor", selection_text)
        self.assertNotIn("Irrelevant motor", final_text)
        self.assertNotIn("candidate_id", final_text)
        self.assertIn("Verified diode", final_text)
        self.assertIn("Verified diode-kit", final_text)
        self.assertIn("Do you need one diode or a kit?", final_text)
        self.assertNotIn("stock_quantity", selection_text)
        self.assertNotIn("availability", selection_text)
        self.assertEqual(self.history, original_history)
        self.assertIn("selection prompt", gemini.calls[2]["system_instruction"])
        self.assertNotIn("selection prompt", gemini.calls[3]["system_instruction"])
        self.assertIn("response prompt", gemini.calls[3]["system_instruction"])

    def test_rejects_a_candidate_id_that_does_not_exist(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
                text_response("The search results are ready."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [99],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
            ]
        )

        with self.assertRaisesRegex(AgentError, "does not exist"):
            self.call_agent(gemini)

    def test_caps_more_than_ten_selected_products(self):
        results = [
            dict(
                self.results[0],
                url=f"https://www.elen.az/shop/{i}/desc/x",
            )
            for i in range(1, 12)
        ]
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
                text_response("The search results are ready."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": list(range(1, 12)),
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                text_response("Ten useful products"),
            ]
        )
        detail_calls = []

        reply = self.call_agent(
            gemini,
            search_fn=lambda query, max_results: results,
            product_data_fn=lambda url: detail_calls.append(url) or {"url": url},
        )

        self.assertEqual(reply, AgentReply("Ten useful products"))
        self.assertEqual(len(detail_calls), 10)
        self.assertNotIn(results[10]["url"], detail_calls)

    def test_clarification_requires_a_question(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
                text_response("The search results are ready."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [2],
                        "needs_clarification": True,
                        "clarifying_question": "",
                    },
                ),
            ]
        )

        with self.assertRaisesRegex(AgentError, "without a question"):
            self.call_agent(gemini)

    def test_runs_a_second_search_when_the_model_asks_again(self):
        second_results = [
            {
                "title": "Diode 250V 1A",
                "price": 0.2,
                "currency": "AZN",
                "availability": "in_stock",
                "stock_quantity": 7,
                "url": "https://www.elen.az/shop/9/desc/diode-250v",
            },
        ]
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode 200V"}),
                function_response("search_products", {"query": "diode"}),
                text_response("The second search found good options."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [4],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                text_response("Here is a 250V diode."),
            ]
        )
        detail_calls = []

        def search_fn(query, max_results):
            return second_results if query == "diode" else self.results

        def product_data_fn(url):
            detail_calls.append(url)
            return {"title": "Verified diode", "url": url}

        reply = self.call_agent(gemini, search_fn, product_data_fn)

        self.assertEqual(reply, AgentReply("Here is a 250V diode."))
        self.assertEqual(
            detail_calls,
            [second_results[0]["url"]],
        )
        description = gemini.calls[0]["kwargs"]["tools"][0][
            "functionDeclarations"
        ][0]["description"]
        self.assertIn("up to 3 times", description)
        model_turn = gemini.calls[1]["history"][-2]
        response_turn = gemini.calls[1]["history"][-1]
        self.assertEqual(model_turn["role"], "model")
        self.assertEqual(
            model_turn["parts"][0]["functionCall"]["args"],
            {"query": "diode 200V"},
        )
        self.assertEqual(response_turn["role"], "user")
        round_results = response_turn["parts"][0]["functionResponse"][
            "response"
        ]["results"]
        self.assertEqual(
            [item["candidate_id"] for item in round_results],
            [1, 2, 3],
        )
        selection_text = gemini.calls[3]["history"][-1]["parts"][0]["text"]
        self.assertIn("Diode 250V 1A", selection_text)
        self.assertIn("candidate_id\":4", selection_text)

    def test_preserves_the_thought_signature_when_replaying_a_search(self):
        gemini = FakeGemini(
            [
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "search_products",
                                            "args": {"query": "diode"},
                                        },
                                        "thoughtSignature": "sig-abc",
                                    }
                                ]
                            }
                        }
                    ]
                },
                text_response("The search results look good."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [1],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                text_response("Here is a diode."),
            ]
        )

        reply = self.call_agent(gemini)

        self.assertEqual(reply, AgentReply("Here is a diode."))
        model_turn = gemini.calls[1]["history"][-2]
        self.assertEqual(
            model_turn,
            {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "name": "search_products",
                            "args": {"query": "diode"},
                        },
                        "thoughtSignature": "sig-abc",
                    }
                ],
            },
        )

    def test_stops_searching_after_the_configured_round_limit(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "one"}),
                function_response("search_products", {"query": "two"}),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [1],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                text_response("Found it."),
            ]
        )
        search_queries = []

        try:
            set_config({"limits": {"max_search_rounds": 2}})
            reply = self.call_agent(
                gemini,
                search_fn=lambda query, max_results: (
                    search_queries.append(query) or self.results
                ),
            )
        finally:
            set_config(None)

        self.assertEqual(reply, AgentReply("Found it."))
        self.assertEqual(search_queries, ["one", "two"])
        self.assertEqual(len(gemini.calls), 4)

    def test_searches_again_after_an_empty_first_round(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode 10V 1A"}),
                function_response("search_products", {"query": "diode"}),
                text_response("Stopping after the second search."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [1],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                text_response("Here is a diode."),
            ]
        )

        def search_fn(query, max_results):
            return [] if query == "diode 10V 1A" else self.results

        reply = self.call_agent(gemini, search_fn=search_fn)

        self.assertEqual(reply, AgentReply("Here is a diode."))
        selection_text = gemini.calls[3]["history"][-1]["parts"][0]["text"]
        self.assertIn("Diode 1N4007 1000V", selection_text)

    def test_all_empty_searches_end_with_a_clarification_request(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "one"}),
                function_response("search_products", {"query": "two"}),
                function_response("search_products", {"query": "three"}),
                text_response("Please tell me more about what you need."),
            ]
        )
        search_queries = []

        reply = self.call_agent(
            gemini,
            search_fn=lambda query, max_results: (
                search_queries.append(query) or []
            ),
        )

        self.assertEqual(
            reply,
            AgentReply("Please tell me more about what you need."),
        )
        self.assertEqual(len(search_queries), 3)
        self.assertEqual(len(gemini.calls), 4)
        final_text = gemini.calls[3]["history"][-1]["parts"][0]["text"]
        self.assertIn("No matching products", final_text)
        self.assertIn("response prompt", gemini.calls[3]["system_instruction"])

    def test_does_not_duplicate_products_found_in_multiple_rounds(self):
        duplicate = dict(self.results[1])
        second_results = [duplicate, self.results[2]]
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "one"}),
                function_response("search_products", {"query": "two"}),
                text_response("Stopping after the second search."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [2, 3],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                text_response("Here are the diodes."),
            ]
        )
        detail_calls = []

        def search_fn(query, max_results):
            return second_results if query == "two" else self.results[:2]

        def product_data_fn(url):
            detail_calls.append(url)
            return {"title": "Verified diode", "url": url}

        reply = self.call_agent(gemini, search_fn, product_data_fn)

        self.assertEqual(reply, AgentReply("Here are the diodes."))
        model_turn = gemini.calls[2]["history"][-2]
        response_turn = gemini.calls[2]["history"][-1]
        self.assertEqual(
            model_turn["parts"][0]["functionCall"]["args"],
            {"query": "two"},
        )
        round_results = response_turn["parts"][0]["functionResponse"][
            "response"
        ]["results"]
        self.assertEqual(
            [item["candidate_id"] for item in round_results],
            [3],
        )
        selection_text = gemini.calls[3]["history"][-1]["parts"][0]["text"]
        self.assertEqual(selection_text.count("Diode 1N4007 1000V"), 1)
        self.assertEqual(detail_calls, [self.results[1]["url"], self.results[2]["url"]])

    def test_refers_to_the_operator_after_failed_searches(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "one"}),
                function_response(
                    "request_operator",
                    {
                        "customer_reply": "Our operator will help you find it.",
                        "operator_message": "Nothing found after a search.",
                    },
                ),
            ]
        )

        reply = self.call_agent(
            gemini,
            search_fn=lambda query, max_results: [],
        )

        self.assertEqual(
            reply,
            AgentReply(
                "Our operator will help you find it.",
                "Nothing found after a search.",
            ),
        )
        self.assertEqual(len(gemini.calls), 2)

    def test_final_unexpected_tool_call_falls_back_to_the_clarifying_question(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
                text_response("The search results look good."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [],
                        "needs_clarification": True,
                        "clarifying_question": "Which voltage do you need?",
                    },
                ),
                function_response("search_products", {"query": "diode"}),
            ]
        )

        reply = self.call_agent(gemini)

        self.assertEqual(reply, AgentReply("Which voltage do you need?"))

    def test_final_unexpected_tool_call_with_text_returns_the_text(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
                text_response("The search results look good."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [1],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {"text": "Here is a diode."},
                                    {
                                        "functionCall": {
                                            "name": "search_products",
                                            "args": {"query": "diode"},
                                        }
                                    },
                                ]
                            }
                        }
                    ]
                },
            ]
        )

        reply = self.call_agent(gemini)

        self.assertEqual(reply, AgentReply("Here is a diode."))

    def test_final_unknown_tool_without_fallback_still_fails(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
                text_response("The search results look good."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [1],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                function_response("search_products", {"query": "diode"}),
            ]
        )

        with self.assertRaisesRegex(AgentError, "unknown tool"):
            self.call_agent(gemini)

    def test_final_call_uses_a_dedicated_system_instruction(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
                text_response("The search results look good."),
                function_response(
                    "select_product_candidates",
                    {
                        "candidate_ids": [2],
                        "needs_clarification": False,
                        "clarifying_question": "",
                    },
                ),
                text_response("Here is a diode."),
            ]
        )

        reply = self.call_agent(gemini, final_system_instruction="final prompt")

        self.assertEqual(reply, AgentReply("Here is a diode."))
        self.assertIn("base prompt", gemini.calls[0]["system_instruction"])
        self.assertEqual(
            gemini.calls[3]["system_instruction"],
            "final prompt\n\nresponse prompt",
        )

    def test_rejects_multiple_function_calls_in_one_decision(self):
        gemini = FakeGemini(
            [
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "functionCall": {
                                            "name": "search_products",
                                            "args": {"query": "diode"},
                                        }
                                    },
                                    {
                                        "functionCall": {
                                            "name": "request_operator",
                                            "args": {
                                                "customer_reply": "a",
                                                "operator_message": "b",
                                            },
                                        }
                                    },
                                ]
                            }
                        }
                    ]
                }
            ]
        )

        with self.assertRaisesRegex(AgentError, "multiple tools"):
            self.call_agent(gemini)

    def test_rejects_an_unknown_tool_after_a_search_round(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "one"}),
                function_response("some_other_tool", {}),
            ]
        )

        with self.assertRaisesRegex(AgentError, "unknown tool"):
            self.call_agent(
                gemini,
                search_fn=lambda query, max_results: self.results,
            )


class EstimateTokensTests(unittest.TestCase):
    def test_counts_function_call_and_response_parts(self):
        history = [
            {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "name": "search_products",
                            "args": {"query": "a" * 300},
                        }
                    }
                ],
            },
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": "search_products",
                            "response": {"results": "b" * 300},
                        }
                    }
                ],
            },
        ]

        self.assertGreater(_estimate_tokens(history, ""), 0)


class ApiCallRecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)
        self.message_id = insert_incoming_message(
            self.database_path,
            "telegram:77",
            "Hello",
        )

    def tearDown(self):
        self.temp_folder.cleanup()

    def read_api_calls(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT purpose, status, prompt_tokens, completion_tokens,
                       in_reply_to_message_id, error
                FROM api_calls
                ORDER BY id
                """
            ).fetchall()
        return rows

    def test_records_a_successful_model_call(self):
        def generate_fn(history, model, api_key, system_instruction, **kwargs):
            return {
                "candidates": [{"content": {"parts": [{"text": "Прямой ответ"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 120,
                    "candidatesTokenCount": 30,
                },
            }

        reply = get_agent_reply(
            [{"role": "user", "parts": [{"text": "Hi"}]}],
            "Hello",
            "gemini-model",
            "key",
            "system",
            "selection",
            "response",
            generate_fn=generate_fn,
            session_id="telegram:77",
            database_path=self.database_path,
            in_reply_to_message_id=self.message_id,
        )

        self.assertEqual(reply.customer_reply, "Прямой ответ")
        self.assertEqual(
            self.read_api_calls(),
            [("decision", "ok", 120, 30, self.message_id, None)],
        )

    def test_records_a_failed_model_call_and_reraises(self):
        def generate_fn(history, model, api_key, system_instruction, **kwargs):
            raise RuntimeError("Gemini is down")

        with self.assertRaises(RuntimeError):
            get_agent_reply(
                [{"role": "user", "parts": [{"text": "Hi"}]}],
                "Hello",
                "gemini-model",
                "key",
                "system",
                "selection",
                "response",
                generate_fn=generate_fn,
                session_id="telegram:77",
                database_path=self.database_path,
                in_reply_to_message_id=self.message_id,
            )

        purpose, status, prompt, completion, reply_to, error = self.read_api_calls()[0]
        self.assertEqual((purpose, status), ("decision", "failed"))
        self.assertEqual((prompt, completion), (0, 0))
        self.assertEqual(reply_to, self.message_id)
        self.assertIn("RuntimeError", error)


if __name__ == "__main__":
    unittest.main()
