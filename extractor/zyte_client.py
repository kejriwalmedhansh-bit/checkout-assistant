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


_AMAZON_TITLE_RE = re.compile(
    r'<span[^>]+id=["\']productTitle["\'][^>]*>(.*?)</span>', re.DOTALL
)
_AMAZON_PRICE_RE = re.compile(
    r'<span[^>]+class=["\'][^"\']*a-price-whole[^"\']*["\'][^>]*>([\d,]+)<'
)
_AMAZON_BRAND_RE = re.compile(
    r'<a[^>]+id=["\']bylineInfo["\'][^>]*>(.*?)</a>', re.DOTALL
)
_TAG_RE = re.compile(r'<[^>]+>')


def _amazon_html_fallback(url: str, partial: dict) -> dict:
    """Fetch browser HTML and extract name/price/brand for Amazon pages when
    structured extraction returns no name (probability too low)."""
    try:
        html = fetch_browser_html(url)
    except Exception:
        return partial

    name_m = _AMAZON_TITLE_RE.search(html)
    price_m = _AMAZON_PRICE_RE.search(html)
    brand_m = _AMAZON_BRAND_RE.search(html)

    name = _TAG_RE.sub("", name_m.group(1)).strip() if name_m else ""
    raw_price = price_m.group(1).replace(",", "").strip() if price_m else ""
    brand_text = _TAG_RE.sub("", brand_m.group(1)).strip() if brand_m else ""
    # "Visit the Noise Store" → "Noise"
    brand = re.sub(r'^(visit\s+the\s+|brand[:\s]+)', '', brand_text, flags=re.IGNORECASE).replace("Store", "").strip()

    merged = dict(partial)
    if name:
        merged["name"] = name
    if raw_price:
        merged.setdefault("price", raw_price)
        merged.setdefault("currency", "INR")
    if brand:
        merged.setdefault("brand", {"name": brand})
    merged.setdefault("availability", "InStock")
    return merged


def extract_product(url: str) -> dict:
    """Call Zyte Extract API with Product data type. Returns the product dict.

    Response schema (flat, no 'offers' nesting):
      name, price (str), regularPrice (str), currency, sku, brand.name,
      mainImage.url, aggregateRating, metadata, ...

    Falls back to browserHtml parsing for Amazon pages when structured
    extraction returns no product name (probability too low).
    """
    url = _normalise_url(url)
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(ZYTE_API_URL, json={"url": url, "product": True}, auth=_auth())
        resp.raise_for_status()
    product = resp.json().get("product") or {}

    if not product.get("name") and "amazon.in" in url:
        print("  [Zyte] Structured extraction returned no name — falling back to browserHtml")
        product = _amazon_html_fallback(url, product)

    return product


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
