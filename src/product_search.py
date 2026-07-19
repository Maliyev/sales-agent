from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlparse

import requests


SEARCH_URL = "https://www.elen.az/shop/search"
REQUEST_TIMEOUT_SECONDS = 15


class ProductSearchError(RuntimeError):
    pass


class SearchResultsParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.results = []
        self.card_depth = 0
        self.current_card = None
        self.current_field = None
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if tag in {"script", "style"}:
            self.ignored_depth += 1
            return

        if self.ignored_depth:
            return

        if self.current_card is None:
            if tag == "div" and re.fullmatch(r"id-item-\d+", attributes.get("id", "")):
                self.current_card = {
                    "title": None,
                    "url": None,
                    "price_text": None,
                    "stock_text": None,
                }
                self.card_depth = 1
            return

        if tag == "div":
            self.card_depth += 1

        classes = attributes.get("class", "").split()
        if tag == "a" and "product-card-title" in classes:
            self.current_card["url"] = urljoin(self.base_url, attributes.get("href", ""))
            self.current_field = "title"
        elif tag == "span" and any(
            class_name.endswith("-price") for class_name in classes
        ):
            self.current_field = "price"
        elif tag == "span" and "val" in classes and "stock" in classes:
            self.current_field = "stock"

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
            return

        if self.ignored_depth or self.current_card is None:
            return

        if tag in {"a", "span"}:
            self.current_field = None

        if tag == "div":
            self.card_depth -= 1
            if self.card_depth == 0:
                self._save_current_card()
                self.current_card = None

    def handle_data(self, data):
        if self.ignored_depth or self.current_field is None:
            return

        value = " ".join(data.split())
        if not value:
            return

        field_name = f"{self.current_field}_text"
        if self.current_field == "title":
            field_name = "title"
        self.current_card[field_name] = _join_text(self.current_card[field_name], value)

    def _save_current_card(self):
        if not self.current_card["title"] or not _is_elen_product_url(
            self.current_card["url"]
        ):
            return

        price, currency = _parse_price(self.current_card["price_text"])
        stock_quantity = _parse_stock(self.current_card["stock_text"])
        self.results.append(
            {
                "title": self.current_card["title"],
                "price": price,
                "currency": currency,
                "availability": _availability_from_stock(stock_quantity),
                "stock_quantity": stock_quantity,
                "url": self.current_card["url"],
            }
        )


def parse_search_results(html, base_url):
    """Return compact product facts from one already downloaded search page."""
    parser = SearchResultsParser(base_url)
    parser.feed(html)

    unique_results = []
    seen_urls = set()
    for result in parser.results:
        if result["url"] not in seen_urls:
            seen_urls.add(result["url"])
            unique_results.append(result)
    return unique_results


def search_products(query, max_results=30, session=None):
    """Search elen.az without downloading each product page."""
    query = _validate_query(query)
    max_results = _validate_max_results(max_results)
    if session is None:
        session = requests.Session()

    first_page_html = _download_search_page(session, query, page=1)
    results = parse_search_results(first_page_html, SEARCH_URL)
    total_pages = _get_page_count(first_page_html)

    seen_urls = {result["url"] for result in results}
    for page in range(2, total_pages + 1):
        if len(results) >= max_results:
            break

        page_html = _download_search_page(session, query, page)
        for result in parse_search_results(page_html, SEARCH_URL):
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                results.append(result)
                if len(results) >= max_results:
                    break

    return results[:max_results]


def _download_search_page(session, query, page):
    params = {"query": query}
    if page > 1:
        params["page"] = page

    try:
        response = session.get(
            SEARCH_URL,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise ProductSearchError("elen.az search request timed out") from error
    except requests.RequestException as error:
        raise ProductSearchError(f"elen.az search request failed: {error}") from error

    return response.text


def _get_page_count(html):
    match = re.search(r"shop_num_pages\s*=\s*(\d+)", html)
    if not match:
        return 1
    return max(1, int(match.group(1)))


def _validate_query(query):
    if not isinstance(query, str):
        raise ValueError("Search query must be text")

    query = query.strip()
    if not query:
        raise ValueError("Search query must not be empty")
    if len(query) > 30:
        raise ValueError("Search query must be 30 characters or shorter")
    return query


def _validate_max_results(max_results):
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        raise ValueError("max_results must be a number from 1 to 100")
    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be a number from 1 to 100")
    return max_results


def _is_elen_product_url(url):
    parsed_url = urlparse(url)
    return (
        parsed_url.scheme in {"http", "https"}
        and parsed_url.hostname in {"elen.az", "www.elen.az"}
        and re.fullmatch(r"/shop/\d+/desc/[^/]+/?", parsed_url.path) is not None
    )


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
