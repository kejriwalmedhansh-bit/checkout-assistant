"""
discovery.py — Cross-merchant product discovery via SerpAPI Google Shopping
"""

import os
import re

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search.json"


def discover_merchants(query: str, max_results: int = 10) -> list[dict]:
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not found in .env file")

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "in",
        "hl": "en",
        "api_key": SERPAPI_KEY,
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[SerpAPI] Request failed: {e}")
        return []

    if "error" in data:
        print(f"[SerpAPI] API error: {data['error']}")
        return []

    raw_results = data.get("shopping_results", [])

    results = []
    for item in raw_results[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "price": item.get("price", ""),
            "extracted_price": item.get("extracted_price", 0),
            "product_link": item.get("product_link", ""),
            "serpapi_immersive_product_api": item.get("serpapi_immersive_product_api", ""),
            "multiple_sources": item.get("multiple_sources", False),
            "rating": item.get("rating"),
            "reviews": item.get("reviews"),
            "delivery": item.get("delivery", ""),
        })

    return results


def get_merchant_sellers(immersive_api_url: str) -> list[dict]:
    if not immersive_api_url:
        return []

    try:
        separator = "&" if "?" in immersive_api_url else "?"
        url = f"{immersive_api_url}{separator}api_key={SERPAPI_KEY}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[SerpAPI Immersive] Request failed: {e}")
        return []

    stores = data.get("product_results", {}).get("stores", [])
    sellers = []
    for item in stores:
        sellers.append({
            "name": item.get("name", ""),
            "price": item.get("price", ""),
            "extracted_price": item.get("extracted_price", 0),
            "link": item.get("link", ""),
            "delivery": " | ".join(item.get("details_and_offers", [])),
        })

    return sellers


_GOOGLE_RE = re.compile(r'(google\.com|gstatic\.com|googleapis\.com)', re.IGNORECASE)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def resolve_single_source_url(product_link: str, immersive_api_url: str = "") -> str:
    """Resolve a Google Shopping product_link to a direct merchant URL.

    Step 1 — SerpAPI google_immersive_product (preferred): works for all
    single-source results because they still carry a serpapi_immersive_product_api
    URL; pass it via immersive_api_url when available.

    Step 2 — HTTP fallback: fetch product_link and extract the first href
    that points outside Google's domains.
    """
    # Step 1: SerpAPI immersive endpoint (stores[0].link is always the direct URL)
    if immersive_api_url:
        sellers = get_merchant_sellers(immersive_api_url)
        if sellers and sellers[0].get("link"):
            return sellers[0]["link"]

    # Step 2: HTTP fallback — follow the link and parse non-Google hrefs
    try:
        resp = requests.get(product_link, headers=_HEADERS, timeout=15, allow_redirects=True)
        if not _GOOGLE_RE.search(resp.url):
            return resp.url
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("https://") and not _GOOGLE_RE.search(href):
                return href
    except requests.RequestException as e:
        print(f"[resolve_url] {e}")

    return ""


def get_direct_urls(results: list[dict]) -> list[dict]:
    enriched = []
    for result in results:
        immersive = result.get("serpapi_immersive_product_api", "")
        if result.get("multiple_sources"):
            sellers = get_merchant_sellers(immersive)
        else:
            url = resolve_single_source_url(result.get("product_link", ""), immersive)
            sellers = [{
                "name": result.get("source", ""),
                "price": result.get("price", ""),
                "extracted_price": result.get("extracted_price", 0),
                "link": url,
            }] if url else []
        enriched.append({**result, "sellers": sellers})
    return enriched


_QUERY_STOP_RE = re.compile(r'\s*[,(]|\s+with\b', re.IGNORECASE)


def build_search_query(brand: str, name: str, model: str = "") -> str:
    if model:
        return f"{brand} {model}".strip()

    # Strip feature-description suffixes (everything from the first comma,
    # parenthesis, or " with ") before word-slicing, so a name like
    # "Noise Master Buds 2 with Sound by Bose (2026),51dB Adaptive ANC..."
    # produces the query "Noise Master Buds 2" rather than "Noise Master Buds 2 with".
    m = _QUERY_STOP_RE.search(name)
    core = name[:m.start()].strip() if m else name.strip()

    words = core.split()
    short_name = " ".join(words[:5])

    if brand.lower() in short_name.lower():
        return short_name
    return f"{brand} {short_name}".strip()
