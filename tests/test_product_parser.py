from pathlib import Path
import sys
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from product_parser import get_product_data, parse_product_page


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, page_html, option_responses):
        self.page_html = page_html
        self.option_responses = option_responses
        self.posted_data = []

    def get(self, url, timeout):
        return FakeResponse(self.page_html)

    def post(self, url, data, timeout):
        self.posted_data.append(data)
        return FakeResponse(self.option_responses[data["opt"]])


class ProductParserTests(unittest.TestCase):
    def test_parses_current_product_facts(self):
        html = """
        <h1>LED 3 mm</h1>
        <b class="shop-itempage-price">
            <span class="id-good-999-price">0.20 AZN</span>
        </b>
        <span class="val stock">62</span>
        """

        product = parse_product_page(html, "https://www.elen.az/shop/999/desc/led-3-mm")

        self.assertEqual(
            product,
            {
                "title": "LED 3 mm",
                "price": 0.2,
                "currency": "AZN",
                "availability": "in_stock",
                "stock_quantity": 62,
                "description": None,
                "url": "https://www.elen.az/shop/999/desc/led-3-mm",
            },
        )

    def test_parses_description_and_keeps_table_rows_separate(self):
        html = """
        <h1>Resistor</h1>
        <div class="shop-info">
            <p>Metal film resistor.</p>
            <table>
                <tr><td>Nominal</td><td>Pcs.</td></tr>
                <tr><td>24kOm</td><td>40</td></tr>
            </table>
            <script>Do not include me</script>
        </div>
        """

        product = parse_product_page(html, "https://www.elen.az/shop/936/desc/x")

        self.assertEqual(
            product["description"],
            "Metal film resistor.\nNominal Pcs.\n24kOm 40",
        )

    def test_uses_new_price_when_old_price_is_present(self):
        html = """
        <h1>OLED display</h1>
        <b class="shop-itempage-price">
            <s><span class="id-good-631-oldprice">7.15 AZN</span></s>
            <span class="newprice"><span class="id-good-631-price">5,79 AZN</span></span>
        </b>
        <span class="val stock">0</span>
        """

        product = parse_product_page(html, "https://www.elen.az/shop/631/desc/oled")

        self.assertEqual(product["price"], 5.79)
        self.assertEqual(product["currency"], "AZN")
        self.assertEqual(product["stock_quantity"], 0)
        self.assertEqual(product["availability"], "out_of_stock")

    def test_returns_none_for_missing_price_and_stock(self):
        html = "<h1>Product without current facts</h1>"

        product = parse_product_page(html, "https://www.elen.az/shop/example")

        self.assertEqual(product["title"], "Product without current facts")
        self.assertIsNone(product["price"])
        self.assertIsNone(product["currency"])
        self.assertIsNone(product["stock_quantity"])
        self.assertIsNone(product["availability"])

    def test_ignores_price_like_text_inside_a_script(self):
        html = """
        <script>var price = '99.99 AZN';</script>
        <h1>Only title</h1>
        """

        product = parse_product_page(html, "https://www.elen.az/shop/example")

        self.assertEqual(product["title"], "Only title")
        self.assertIsNone(product["price"])

    def test_downloads_every_radio_variant(self):
        page_html = """
        <h1>LED 3 mm</h1>
        <span class="id-good-999-price">0.20 AZN</span>
        <span class="val stock">62</span>
        <ul id="id-999-options-selectors">
            <li id="id-999-oitem-10">
                <span class="opt">color:</span>
                <label>
                    <input type="radio" id="id-999-oval-10-0" value="0">
                    <span class="opt-val-name">white</span>
                </label>
                <label>
                    <input type="radio" id="id-999-oval-10-4" value="4">
                    <span class="opt-val-name">red</span>
                </label>
            </li>
        </ul>
        """
        option_responses = {
            "10": "$('.id-good-999-price').html('0.20 AZN');$('#id-999-options .val.stock').text('62');",
            "10-4": "$('.id-good-999-price').html('0.25 AZN');$('#id-999-options .val.stock').text('51');",
        }
        session = FakeSession(page_html, option_responses)

        product = get_product_data(
            "https://www.elen.az/shop/999/desc/led-3-mm", session=session
        )

        self.assertEqual(
            product["variants"],
            [
                {
                    "name": "color: white",
                    "price": 0.2,
                    "stock_quantity": 62,
                },
                {
                    "name": "color: red",
                    "price": 0.25,
                    "stock_quantity": 51,
                },
            ],
        )
        self.assertEqual(product["currency"], "AZN")
        self.assertNotIn("price", product)
        self.assertNotIn("stock_quantity", product)
        self.assertEqual([data["opt"] for data in session.posted_data], ["10", "10-4"])

    def test_downloads_every_dropdown_variant(self):
        page_html = """
        <h1>Resistor</h1>
        <span class="id-good-936-price">0.09 AZN</span>
        <span class="val stock">0</span>
        <ul id="id-936-options-selectors">
            <li id="id-936-oitem-9">
                <span class="opt">Nominal:</span>
                <select id="id-936-oval-9">
                    <option value="72"><span class="opt-val-name">10</span></option>
                    <option value="81"><span class="opt-val-name">24</span></option>
                </select>
            </li>
        </ul>
        """
        option_responses = {
            "9-72": "$('.id-good-936-price').html('0.09 AZN');$('#id-936-options .val.stock').text('0');",
            "9-81": "$('.id-good-936-price').html('0.09 AZN');$('#id-936-options .val.stock').text('40');",
        }
        session = FakeSession(page_html, option_responses)

        product = get_product_data(
            "https://www.elen.az/shop/936/desc/resistor", session=session
        )

        self.assertEqual(
            product["variants"],
            [
                {"name": "Nominal: 10", "price": 0.09, "stock_quantity": 0},
                {"name": "Nominal: 24", "price": 0.09, "stock_quantity": 40},
            ],
        )
        self.assertEqual([data["opt"] for data in session.posted_data], ["9-72", "9-81"])

    def test_restores_a_truncated_dropdown_name_from_the_description_table(self):
        page_html = """
        <h1>Resistor</h1>
        <span class="id-good-936-price">0.09 AZN</span>
        <span class="val stock">0</span>
        <ul id="id-936-options-selectors">
            <li id="id-936-oitem-9">
                <span class="opt">Nominal:</span>
                <select id="id-936-oval-9">
                    <option value="72"><span class="opt-val-name">10</span></option>
                    <option value="75"><span class="opt-val-name">1...</span></option>
                </select>
            </li>
        </ul>
        <div class="shop-info">
            <table>
                <tr><td>№</td><td>Nominal</td><td>Pcs.</td></tr>
                <tr><td>1</td><td>10kOm</td><td>0</td></tr>
                <tr><td>2</td><td>13kOm</td><td>0</td></tr>
            </table>
        </div>
        """
        response_text = "$('.id-good-936-price').html('0.09 AZN');$('#id-936-options .val.stock').text('0');"
        session = FakeSession(
            page_html,
            {"9-72": response_text, "9-75": response_text},
        )

        product = get_product_data(
            "https://www.elen.az/shop/936/desc/resistor", session=session
        )

        self.assertEqual(product["variants"][1]["name"], "Nominal: 13")

    def test_keeps_price_and_stock_on_a_product_without_variants(self):
        page_html = """
        <h1>Arduino UNO</h1>
        <span class="id-good-100-price">12.50 AZN</span>
        <span class="val stock">4</span>
        <div class="shop-info"><p>Development board.</p></div>
        """
        session = FakeSession(page_html, {})

        product = get_product_data(
            "https://www.elen.az/shop/100/desc/arduino", session=session
        )

        self.assertEqual(
            product,
            {
                "title": "Arduino UNO",
                "price": 12.5,
                "currency": "AZN",
                "stock_quantity": 4,
                "description": "Development board.",
                "url": "https://www.elen.az/shop/100/desc/arduino",
            },
        )

    def test_downloads_every_combination_of_two_option_groups(self):
        page_html = """
        <h1>Configurable product</h1>
        <span class="id-good-100-price">1.00 AZN</span>
        <span class="val stock">1</span>
        <ul id="id-100-options-selectors">
            <li id="id-100-oitem-10">
                <span class="opt">color:</span>
                <input type="radio" id="id-100-oval-10-0" value="0"><span class="opt-val-name">white</span>
                <input type="radio" id="id-100-oval-10-4" value="4"><span class="opt-val-name">red</span>
            </li>
            <li id="id-100-oitem-11">
                <span class="opt">size:</span>
                <input type="radio" id="id-100-oval-11-0" value="0"><span class="opt-val-name">small</span>
                <input type="radio" id="id-100-oval-11-1" value="1"><span class="opt-val-name">large</span>
            </li>
        </ul>
        """
        response_text = "$('.id-good-100-price').html('1.00 AZN');$('#id-100-options .val.stock').text('1');"
        session = FakeSession(
            page_html,
            {
                "10:11": response_text,
                "10:11-1": response_text,
                "10-4:11": response_text,
                "10-4:11-1": response_text,
            },
        )

        product = get_product_data(
            "https://www.elen.az/shop/100/desc/example", session=session
        )

        self.assertEqual(len(product["variants"]), 4)
        self.assertEqual(
            product["variants"][3]["name"],
            "color: red | size: large",
        )

    def test_rejects_a_url_from_another_site(self):
        with self.assertRaisesRegex(ValueError, "elen.az"):
            get_product_data("https://example.com/product")
