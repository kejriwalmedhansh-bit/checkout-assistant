import os
import re
import httpx
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from dotenv import load_dotenv

load_dotenv()

ZYTE_API_URL = "https://api.zyte.com/v1/extract"
TIMEOUT = 60.0
TIMEOUT_LIST = 120.0  # productList calls are slower (full page render + parsing)


def _auth() -> tuple[str, str]:
    key = os.getenv("ZYTE_API_KEY")
    if not key:
        raise RuntimeError("ZYTE_API_KEY not set in .env")
    return (key, "")


def _normalise_url(url: str) -> str:
    """
    Apply locale fixes before passing a URL to Zyte.

    Amazon India serves Hindi content by default when Zyte's IP resolves to IN.
    Adding ?language=en_IN forces the English-India locale while keeping prices
    and availability in INR — confirmed to return English product names and a
    correct brand field.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "amazon.in" in host:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if "language" not in qs:
            qs["language"] = ["en_IN"]
            new_query = urlencode({k: v[0] for k, v in qs.items()})
            parsed = parsed._replace(query=new_query)
            url = urlunparse(parsed)

    return url


def extract_product(url: str) -> dict:
    """Call Zyte Extract API with Product data type. Returns the product dict.

    Response schema (flat, no 'offers' nesting):
      name, price (str), regularPrice (str), currency, sku, brand.name,
      mainImage.url, aggregateRating, metadata, ...
    """
    url = _normalise_url(url)
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(ZYTE_API_URL, json={"url": url, "product": True}, auth=_auth())
        resp.raise_for_status()
    return resp.json().get("product") or {}


def extract_product_list(url: str) -> list[dict]:
    """Call Zyte Extract API with productList data type. Returns list of product dicts."""
    with httpx.Client(timeout=TIMEOUT_LIST) as client:
        resp = client.post(ZYTE_API_URL, json={"url": url, "productList": True}, auth=_auth())
        resp.raise_for_status()
    data = resp.json()
    return (data.get("productList") or {}).get("products") or []


def fetch_browser_html(url: str) -> str:
    """Fetch browser-rendered HTML via Zyte (uses headless Chrome)."""
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(ZYTE_API_URL, json={"url": url, "browserHtml": True}, auth=_auth())
        resp.raise_for_status()
    return resp.json().get("browserHtml") or ""
