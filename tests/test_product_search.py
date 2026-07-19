from pathlib import Path
import sys
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from product_search import parse_search_results, search_products


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def get(self, url, params, timeout):
        self.requests.append(params)
        return FakeResponse(self.pages[params.get("page", 1)])


class ProductSearchTests(unittest.TestCase):
    def setUp(self):
        self.page_1 = (FIXTURES / "search_page_1.html").read_text(encoding="utf-8")
        self.page_2 = (FIXTURES / "search_page_2.html").read_text(encoding="utf-8")

    def test_parses_compact_product_facts(self):
        results = parse_search_results(
            self.page_1,
            "https://www.elen.az/shop/search?query=arduino",
        )

        self.assertEqual(
            results,
            [
                {
                    "title": "Arduino UNO R3",
                    "price": 12.5,
                    "currency": "AZN",
                    "availability": "in_stock",
                    "stock_quantity": 4,
                    "url": "https://www.elen.az/shop/101/desc/arduino-uno",
                },
                {
                    "title": "Arduino Nano",
                    "price": 7.5,
                    "currency": "AZN",
                    "availability": "out_of_stock",
                    "stock_quantity": 0,
                    "url": "https://www.elen.az/shop/102/desc/arduino-nano",
                },
            ],
        )

    def test_loads_more_pages_until_the_limit_and_removes_duplicates(self):
        session = FakeSession({1: self.page_1, 2: self.page_2})

        results = search_products("arduino uno", max_results=3, session=session)

        self.assertEqual([result["title"] for result in results], [
            "Arduino UNO R3",
            "Arduino Nano",
            "Arduino Mega",
        ])
        self.assertEqual(
            session.requests,
            [{"query": "arduino uno"}, {"query": "arduino uno", "page": 2}],
        )

    def test_stops_before_loading_another_page_when_the_limit_is_reached(self):
        session = FakeSession({1: self.page_1, 2: self.page_2})

        results = search_products("arduino", max_results=1, session=session)

        self.assertEqual(len(results), 1)
        self.assertEqual(session.requests, [{"query": "arduino"}])

    def test_rejects_empty_or_long_queries(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            search_products("   ")
        with self.assertRaisesRegex(ValueError, "30 characters"):
            search_products("a" * 31)
