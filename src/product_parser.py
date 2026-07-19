from html import unescape
from html.parser import HTMLParser
from itertools import product
import re
from urllib.parse import urlparse

import requests


class ProductPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.price_text = None
        self.stock_text = None
        self.current_field = None
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag in {"script", "style"}:
            self.ignored_depth += 1
            return

        if self.ignored_depth:
            return

        classes = attributes.get("class", "").split()
        if tag == "h1" and self.title is None:
            self.current_field = "title"
        elif tag == "span" and "val" in classes and "stock" in classes:
            self.current_field = "stock"
        elif tag == "span" and any(
            class_name.endswith("-price") for class_name in classes
        ):
            self.current_field = "price"

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
            return

        if tag in {"h1", "span"}:
            self.current_field = None

    def handle_data(self, data):
        if self.ignored_depth or self.current_field is None:
            return

        value = " ".join(data.split())
        if not value:
            return

        if self.current_field == "title":
            self.title = _join_text(self.title, value)
        elif self.current_field == "price":
            self.price_text = _join_text(self.price_text, value)
        elif self.current_field == "stock":
            self.stock_text = _join_text(self.stock_text, value)


def parse_product_page(html, url):
    """Return facts visible in one already downloaded elen.az product page."""
    parser = ProductPageParser()
    parser.feed(html)

    price, currency = _parse_price(parser.price_text)
    stock_quantity = _parse_stock(parser.stock_text)

    return {
        "title": parser.title,
        "price": price,
        "currency": currency,
        "availability": _availability_from_stock(stock_quantity),
        "stock_quantity": stock_quantity,
        "url": url,
    }


class ProductOptionsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.product_id = None
        self.option_groups = []
        self.current_group = None
        self.current_field = None
        self.pending_value = None
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag in {"script", "style"}:
            self.ignored_depth += 1
            return

        if self.ignored_depth:
            return

        element_id = attributes.get("id", "")
        classes = attributes.get("class", "").split()

        selectors_match = re.fullmatch(r"id-(\d+)-options-selectors", element_id)
        if tag == "ul" and selectors_match:
            self.product_id = selectors_match.group(1)
            return

        group_match = re.fullmatch(r"id-\d+-oitem-(\d+)", element_id)
        if tag == "li" and group_match:
            self.current_group = {
                "id": group_match.group(1),
                "name": None,
                "values": [],
            }
            self.option_groups.append(self.current_group)
            return

        if self.current_group is None:
            return

        if tag == "span" and "opt" in classes:
            self.current_field = "option_name"
        elif tag == "input" and attributes.get("type") == "radio":
            value_match = re.fullmatch(
                r"id-\d+-oval-(\d+)-(\d+)", element_id
            )
            if value_match:
                self.pending_value = {
                    "id": value_match.group(1),
                    "value": value_match.group(2),
                    "name": None,
                }
                self.current_group["values"].append(self.pending_value)
        elif tag == "option":
            self.pending_value = {
                "id": self.current_group["id"],
                "value": attributes.get("value", ""),
                "name": None,
            }
            self.current_group["values"].append(self.pending_value)
            self.current_field = "option_value"
        elif tag == "span" and "opt-val-name" in classes:
            self.current_field = "option_value"

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
            return

        if tag == "li":
            self.current_group = None
        elif tag in {"span", "option"}:
            self.current_field = None

    def handle_data(self, data):
        if self.ignored_depth or self.current_field is None:
            return

        value = " ".join(data.split())
        if not value:
            return

        if self.current_field == "option_name" and self.current_group is not None:
            self.current_group["name"] = _join_text(
                self.current_group["name"], value
            )
        elif self.current_field == "option_value" and self.pending_value is not None:
            self.pending_value["name"] = _join_text(
                self.pending_value["name"], value
            )


def parse_product_options(html):
    """Return the option values visible in one already downloaded product page."""
    parser = ProductOptionsParser()
    parser.feed(html)

    option_groups = [
        group
        for group in parser.option_groups
        if group["name"] and all(value["name"] is not None for value in group["values"])
    ]
    for group in option_groups:
        group["name"] = group["name"].rstrip(":").strip()
    return parser.product_id, option_groups


def parse_product_option_response(response_text):
    """Read the price and stock returned by elen.az after one option change."""
    price_text = _find_javascript_value(
        response_text,
        r"\.[^'\"]+-price['\"]\)\.html\((['\"])(.*?)\1\)",
    )
    stock_text = _find_javascript_value(
        response_text,
        r"\.val\.stock['\"]\)\.text\((['\"])(.*?)\1\)",
    )
    price, currency = _parse_price(price_text)
    stock_quantity = _parse_stock(stock_text)

    return {
        "price": price,
        "currency": currency,
        "availability": _availability_from_stock(stock_quantity),
        "stock_quantity": stock_quantity,
    }


def get_product_data(url, session=None):
    """Download one elen.az product page and return its current facts and variants."""
    _validate_elen_url(url)

    if session is None:
        session = requests.Session()

    response = session.get(url, timeout=15)
    response.raise_for_status()
    html = response.text
    product_data = parse_product_page(html, url)
    product_id, option_groups = parse_product_options(html)

    product_data["variants"] = []
    if not product_id or not option_groups:
        return product_data

    for selected_values in product(*(group["values"] for group in option_groups)):
        request_data = _build_option_request(product_id, selected_values)
        option_response = session.post(url, data=request_data, timeout=15)
        option_response.raise_for_status()

        variant = {
            "options": {
                group["name"]: value["name"]
                for group, value in zip(option_groups, selected_values)
            }
        }
        variant.update(parse_product_option_response(option_response.text))
        product_data["variants"].append(variant)

    return product_data


def _join_text(current, value):
    if current:
        return f"{current} {value}"
    return value


def _parse_price(price_text):
    if not price_text:
        return None, None

    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)", price_text)
    if not match:
        return None, None

    return float(match.group(1).replace(",", ".")), match.group(2)


def _parse_stock(stock_text):
    if not stock_text or not stock_text.isdigit():
        return None
    return int(stock_text)


def _availability_from_stock(stock_quantity):
    if stock_quantity is None:
        return None
    if stock_quantity == 0:
        return "out_of_stock"
    return "in_stock"


def _find_javascript_value(response_text, pattern):
    match = re.search(pattern, response_text, re.DOTALL)
    if not match:
        return None
    return unescape(match.group(2)).strip()


def _build_option_request(product_id, selected_values):
    option_parts = []
    for value in selected_values:
        if value["value"] == "0":
            option_parts.append(value["id"])
        else:
            option_parts.append(f"{value['id']}-{value['value']}")

    return {
        "mode": "opt-sel",
        "pref": "id",
        "opt": ":".join(option_parts),
        "opt_id": selected_values[-1]["id"],
        "cnt": "1",
    }


def _validate_elen_url(url):
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"} or parsed_url.hostname not in {
        "elen.az",
        "www.elen.az",
    }:
        raise ValueError("Product URL must be an http(s) URL from elen.az")
