"""
discovery.py — Cross-merchant product discovery via SerpAPI Google Shopping
"""

import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from db.cache import get_cached, save_cache

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search.json"


def discover_merchants(query: str, max_results: int = 10) -> list[dict]:
    cached = get_cached(query)
    if cached is not None:
        print(f"[Cache] Returning cached results for '{query}'")
        return cached

    if not SERPAPI_KEY:
        print("[SerpAPI] SERPAPI_KEY not found in .env file")
        return []

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

    save_cache(query, results)
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

    stores = (data.get("product_results") or {}).get("stores", [])
    sellers = []
    for item in stores:
        sellers.append({
            "name": item.get("name", ""),
            "price": item.get("price", ""),
            "extracted_price": item.get("extracted_price", 0),
            "link": item.get("link", ""),
            "availability": item.get("availability", ""),
            "delivery": " | ".join(item.get("details_and_offers", [])),
        })

    return sellers


_OUT_OF_STOCK_PHRASES = ("out of stock", "unavailable", "sold out")


def _is_out_of_stock(seller: dict) -> bool:
    """Check a seller's availability/details_and_offers text for stock-out phrases."""
    text = f"{seller.get('availability', '')} {seller.get('delivery', '')}".lower()
    return any(phrase in text for phrase in _OUT_OF_STOCK_PHRASES)


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


# Foreign marketplace domains filtered out of individual seller URLs returned
# by the SerpAPI immersive endpoint. Mirrors _FOREIGN_SOURCES in matcher.py
# which filters top-level discovery results.
_FOREIGN_DOMAINS = frozenset({
    "farfetch", "ssense", "net-a-porter", "mytheresa",
    "stockx", "kickscrew", "kicksonfire", "desertcart",
    "ebay", "aliexpress", "amazon.com", "walmart", "asos", "zalando", "etsy",
})


def _is_foreign_seller(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(name in domain for name in _FOREIGN_DOMAINS)


# Well-known brand slugs used to detect mismatched product URLs in seller
# listings (e.g. a JioMart URL pointing to a Garnier product for a Lakme query).
# Only brands with 4+ character slugs are listed to avoid false positives.
_BRAND_SLUGS = frozenset({
    "garnier", "loreal", "maybelline", "revlon", "mamaearth", "biotique",
    "himalaya", "patanjali", "dove", "nivea", "gillette", "pantene",
    "tresemme", "adidas", "puma", "reebok", "asics", "skechers", "fila",
    "boat", "noise", "apple", "samsung", "sony", "lenovo", "asus", "acer",
    "oneplus", "realme", "xiaomi", "oppo", "vivo", "motorola", "nokia",
    "bose", "lakme", "nike", "philips", "fastrack", "titan", "casio",
})


def _seller_url_conflicts(url: str, source_brand: str) -> bool:
    """Return True if the seller URL path contains a brand other than source_brand.

    Used to drop mis-linked sellers (e.g. a JioMart URL for a Garnier product
    returned under a Lakme result).
    """
    if not source_brand or not url:
        return False
    source_slug = re.sub(r'[^a-z0-9]', '', source_brand.lower())
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    for brand in _BRAND_SLUGS:
        if brand == source_slug:
            continue
        if brand in path:
            return True
    return False


def get_direct_urls(results: list[dict], source_brand: str = "") -> list[dict]:
    enriched = []
    excluded_oos = 0
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

        before = len(sellers)
        sellers = [s for s in sellers if not _is_out_of_stock(s)]
        excluded_oos += before - len(sellers)

        if source_brand:
            sellers = [s for s in sellers if not _seller_url_conflicts(s.get("link", ""), source_brand)]
        sellers = [s for s in sellers if not _is_foreign_seller(s.get("link", ""))]
        enriched.append({**result, "sellers": sellers})

    print(f"  Excluded {excluded_oos} out-of-stock seller(s)")
    return enriched


_QUERY_STOP_RE = re.compile(r'\s*[,(]|\s+with\b', re.IGNORECASE)

# Generic category/descriptor words that vary by merchant and dilute search
# results when included in queries. Stripped before word-slicing so that
# "Nike Women Waffle Debut Leather Sneakers" → "Nike Waffle Debut" rather
# than "Nike Women Waffle Debut Leather" (which only matches Myntra's title).
_QUERY_SKIP_WORDS = frozenset({
    "women", "men", "boys", "girls", "casual", "running", "formal",
    "leather", "wireless", "bluetooth", "truly", "tws", "in-ear",
    "earbuds", "headphones", "sneakers", "shoes", "sandals",
})


def build_search_query(brand: str, name: str, model: str = "") -> str:
    if model:
        return f"{brand} {model}".strip()

    # Strip feature-description suffixes (comma, parenthesis, " with ").
    m = _QUERY_STOP_RE.search(name)
    core = name[:m.start()].strip() if m else name.strip()

    # Drop generic category/descriptor words so the query targets the model
    # identity rather than merchant-specific category labels.
    words = [w for w in core.split() if w.lower() not in _QUERY_SKIP_WORDS]
    if not words:
        words = core.split()  # fall back to full core if everything was stripped

    short_name = " ".join(words[:4])

    if brand.lower() in short_name.lower():
        return short_name
    return f"{brand} {short_name}".strip()
