from pathlib import Path
import sys
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from agent import AgentError, get_agent_reply


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

    def call_agent(self, gemini, search_fn=None, product_data_fn=None):
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
            search_fn=search_fn,
            product_data_fn=product_data_fn,
            generate_fn=gemini,
        )

    def test_returns_direct_answer_without_search(self):
        gemini = FakeGemini([text_response("Please specify the package.")])
        original_history = list(self.history)

        reply = self.call_agent(gemini)

        self.assertEqual(reply, "Please specify the package.")
        self.assertEqual(self.history, original_history)
        self.assertEqual(len(gemini.calls), 1)

    def test_full_search_list_exists_only_in_selection_call(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode 200V"}),
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

        self.assertEqual(reply, "Do you need one diode or a kit?")
        self.assertEqual(search_calls, [("diode 200V", 30)])
        self.assertEqual(
            detail_calls,
            [self.results[1]["url"], self.results[2]["url"]],
        )
        selection_text = gemini.calls[1]["history"][-1]["parts"][0]["text"]
        final_text = gemini.calls[2]["history"][-1]["parts"][0]["text"]
        self.assertIn("Irrelevant motor", selection_text)
        self.assertNotIn("Irrelevant motor", final_text)
        self.assertNotIn("candidate_id", final_text)
        self.assertIn("Verified diode", final_text)
        self.assertIn("Verified diode-kit", final_text)
        self.assertIn("Do you need one diode or a kit?", final_text)
        self.assertNotIn("stock_quantity", selection_text)
        self.assertNotIn("availability", selection_text)
        self.assertEqual(self.history, original_history)
        self.assertIn("selection prompt", gemini.calls[1]["system_instruction"])
        self.assertNotIn("selection prompt", gemini.calls[2]["system_instruction"])
        self.assertIn("response prompt", gemini.calls[2]["system_instruction"])

    def test_rejects_a_candidate_id_that_does_not_exist(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
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

        self.assertEqual(reply, "Ten useful products")
        self.assertEqual(len(detail_calls), 10)
        self.assertNotIn(results[10]["url"], detail_calls)

    def test_clarification_requires_a_question(self):
        gemini = FakeGemini(
            [
                function_response("search_products", {"query": "diode"}),
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


if __name__ == "__main__":
    unittest.main()
