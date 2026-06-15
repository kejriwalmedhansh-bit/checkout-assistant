"""
Merchant discovery via Google Shopping (price signals) + direct merchant search (verifiable URLs).

Google Shopping's productList API gives us price intelligence but no merchant URLs
(Google embeds aclk JS-redirect URLs that can't be resolved without a real click).
We therefore use Google Shopping for *showing what's in the market* and rely on
direct merchant searches on the major Indian e-commerce sites for verifiable URLs
that Zyte can extract product data from in Step 3.
"""

import re
import json
import urllib.parse
from urllib.parse import urlparse, parse_qs, unquote

from bs4 import BeautifulSoup

from .zyte_client import extract_product_list, fetch_browser_html

# Map of known Indian e-commerce domains → display names
MERCHANT_DOMAINS: dict[str, str] = {
    "amazon.in": "Amazon India",
    "flipkart.com": "Flipkart",
    "myntra.com": "Myntra",
    "ajio.com": "Ajio",
    "croma.com": "Croma",
    "reliancedigital.in": "Reliance Digital",
    "vijaysales.com": "Vijay Sales",
    "snapdeal.com": "Snapdeal",
    "meesho.com": "Meesho",
    "tatacliq.com": "TataCLiQ",
    "nykaa.com": "Nykaa",
    "jiomart.com": "JioMart",
    "paytmmall.com": "Paytm Mall",
    "shopclues.com": "ShopClues",
    "pepperfry.com": "Pepperfry",
    "apple.com": "Apple Store",
    "samsung.com": "Samsung India",
    "lg.com": "LG India",
    "infibeam.com": "Infibeam",
    "indiamart.com": "IndiaMart",
}

# Merchant search URL templates — {q} is replaced with the encoded query
MERCHANT_SEARCH_TEMPLATES: list[tuple[str, str]] = [
    ("Flipkart",         "https://www.flipkart.com/search?q={q}&otracker=search"),
    ("Croma",            "https://www.croma.com/searchB?q={q}&text={q}"),
    ("Reliance Digital", "https://www.reliancedigital.in/search?q={q}"),
    ("TataCLiQ",         "https://www.tatacliq.com/search/?searchCategory=all&text={q}"),
    ("Vijay Sales",      "https://www.vijaysales.com/search/{q}"),
]


# ── query / URL builders ──────────────────────────────────────────────────────

_SPEC_TOKEN_RE = re.compile(
    r"^\d+(?:GB|TB)$"          # storage/RAM: 128GB, 8GB, 1TB
    r"|^(?:RAM|Memory)$"       # generic spec words
    r"|^\d+\.?\d*-?inch$",     # screen size: 13.6inch
    re.IGNORECASE,
)

_QUERY_STRIP_COLORS = {
    "black", "white", "silver", "gold", "blue", "red", "green", "pink",
    "grey", "gray", "yellow", "purple", "orange", "starlight", "midnight",
    "sky", "coral", "teal", "lavender", "obsidian", "titanium", "natural",
    "desert", "graphite", "rose", "sage", "mint", "alpine", "sierra",
    "porcelain", "aloe", "hazel", "bay", "charcoal", "cream", "sand",
}


def build_search_query(product: dict) -> str:
    """
    Build a merchant search query using brand + model name only.
    Specs (storage, RAM, screen size) and colors are stripped — they
    over-constrain merchant search engines and reduce result counts.
    Spec matching is handled downstream in Step 4.
    """
    brand = product.get("brand") or {}
    brand_name = (brand.get("name") or "").strip() if isinstance(brand, dict) else str(brand).strip()
    _noise = {"amazon", "amazon prime", "prime"}
    if brand_name.lower() in _noise or "logo" in brand_name.lower():
        brand_name = ""

    raw_name = (product.get("name") or "").strip()

    # Extract ASCII tokens, drop specs and colors
    model_tokens: list[str] = []
    for token in re.split(r"[\s,;:\"'()\[\]]+", raw_name):
        clean = re.sub(r"[^A-Za-z0-9.+/-]", "", token)
        if len(clean) < 2:
            continue
        if _SPEC_TOKEN_RE.match(clean):
            continue
        if clean.lower() in _QUERY_STRIP_COLORS:
            continue
        model_tokens.append(clean)

    # Drop leading token if it duplicates the brand
    if brand_name and model_tokens:
        if model_tokens[0].lower() == brand_name.lower().split()[0]:
            model_tokens = model_tokens[1:]

    # Cap at 3 model tokens (brand + 3 = 4 total max)
    chosen = model_tokens[:3]

    if brand_name:
        brand_lower = brand_name.lower()
        if not any(brand_lower in t.lower() for t in chosen):
            chosen = [brand_name] + chosen

    query = " ".join(chosen).strip()

    if not query:
        sku = (product.get("sku") or "").upper()
        query = f"{brand_name} {sku}".strip() if brand_name else sku

    return query


def shopping_url(query: str) -> str:
    """Construct a Google Shopping URL targeting India with English results."""
    return (
        "https://www.google.com/search?"
        + urllib.parse.urlencode({"q": query, "tbm": "shop", "gl": "in", "hl": "en"})
    )


def merchant_from_url(url: str) -> str:
    """Return a display merchant name derived from a URL."""
    if not url:
        return "Unknown"
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        for domain, name in MERCHANT_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                return name
        parts = host.split(".")
        return parts[0].title() if parts else host
    except Exception:
        return "Unknown"


def parse_price(text: str) -> float | None:
    """Extract a numeric price from a string like '₹1,29,900' or '119900.0'."""
    cleaned = re.sub(r"[^\d.]", "", str(text))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# ── Google Shopping discovery (price signals) ─────────────────────────────────

def _fetch_google_shopping_signals(query: str) -> list[dict]:
    """
    Fetch Google Shopping productList — returns names + prices but no merchant URLs
    (Google uses JS-resolved aclk ad-click links that can't be statically resolved).
    We display these as price intelligence but cannot use them for Step 3 verification.
    """
    url = shopping_url(query)
    try:
        items = extract_product_list(url)
    except Exception as e:
        print(f"[Discovery] productList error: {e.__class__.__name__}: {e}")
        return []

    results = []
    for p in items:
        price = parse_price(p.get("price") or "")
        currency = (p.get("currency") or "INR").upper()
        # Only keep INR results — English queries can pull USD results from Google
        if currency != "INR":
            continue
        name = p.get("name") or ""
        results.append({
            "merchant": "Google Shopping",
            "price": price,
            "price_raw": f"₹{price:,.0f}" if price else "",
            "name": name,
            "url": "",          # no usable URL from Google Shopping productList
            "source": "google-shopping-signal",
        })
    return results


# ── direct merchant search (verifiable URLs) ─────────────────────────────────

def _search_one_merchant(merchant_name: str, search_url: str) -> list[dict]:
    """
    Run Zyte productList on a merchant's search-results page.
    Returns up to 3 candidate products with real merchant URLs.
    """
    try:
        items = extract_product_list(search_url)
    except Exception as e:
        print(f"  [{merchant_name}] productList error: {e.__class__.__name__}: {e}")
        return []

    results = []
    for p in (items or [])[:3]:
        url = p.get("url") or ""
        price = parse_price(p.get("price") or "")
        if not url or not url.startswith("http"):
            continue
        results.append({
            "merchant": merchant_from_url(url) or merchant_name,
            "price": price,
            "price_raw": f"₹{price:,.0f}" if price else "",
            "name": p.get("name") or "",
            "url": url,
            "source": "direct-merchant",
        })
    return results


def _search_indian_merchants(query: str) -> list[dict]:
    """
    Search all configured Indian e-commerce merchants for the query.
    Returns results with real product URLs suitable for Step 3 verification.
    Drops a merchant's results entirely if fewer than 50% of returned
    names contain any query token — catches search engines that fall back
    to unrelated categories.
    """
    encoded_q = urllib.parse.quote_plus(query)
    query_tokens = [t for t in query.lower().split() if len(t) >= 2]
    results: list[dict] = []

    for merchant_name, template in MERCHANT_SEARCH_TEMPLATES:
        search_url = template.replace("{q}", encoded_q)
        print(f"  [Direct] {merchant_name}: {search_url[:80]}")
        merchant_results = _search_one_merchant(merchant_name, search_url)
        if not merchant_results:
            print(f"           → no results")
            continue

        relevant = [
            r for r in merchant_results
            if any(t in (r.get("name") or "").lower() for t in query_tokens)
        ]
        relevance = len(relevant) / len(merchant_results)
        if relevance < 0.5:
            print(
                f"           → skipping {len(merchant_results)} results "
                f"({relevance:.0%} on-topic — search returned wrong category)"
            )
            continue

        print(f"           → {len(merchant_results)} results found")
        results.extend(merchant_results)

    return results


# ── main entry point ──────────────────────────────────────────────────────────

def discover_merchants(product: dict) -> tuple[list[dict], list[dict]]:
    """
    Discover merchants for *product*.

    Returns:
        (google_signals, merchant_candidates)

        google_signals     — list of {name, price} from Google Shopping (no URLs);
                             displayed in Step 2 as raw price intelligence.
        merchant_candidates — list of {merchant, price, url, name} with real URLs
                             from direct merchant searches; fed into Step 3 for
                             Zyte product verification.
    """
    query = build_search_query(product)
    gshop_url = shopping_url(query)

    print(f"\n[Discovery] Query  : {query}")
    print(f"[Discovery] Google Shopping URL: {gshop_url}\n")

    # 1. Google Shopping — price signals only
    print("[Discovery] Step A: Fetching Google Shopping price signals (productList)...")
    google_signals = _fetch_google_shopping_signals(query)
    print(f"           → {len(google_signals)} price signals returned\n")

    # 2. Direct merchant search — gives us real URLs
    print("[Discovery] Step B: Searching Indian merchants directly for verifiable URLs...")
    merchant_candidates = _search_indian_merchants(query)
    print(f"\n           → {len(merchant_candidates)} verifiable merchant results total\n")

    return google_signals, merchant_candidates


def _normalise_product_list_item(p: dict) -> dict:
    """Normalise a Zyte productList item to the shared result schema."""
    price_raw = p.get("price") or ""
    if not price_raw:
        offers = p.get("offers") or [{}]
        price_raw = (offers[0].get("price") or "") if offers else ""
    try:
        price = float(price_raw) if price_raw else None
    except (ValueError, TypeError):
        price = None

    brand = p.get("brand") or {}
    merchant = (brand.get("name") or "") if isinstance(brand, dict) else str(brand or "")

    return {
        "merchant": merchant or merchant_from_url(p.get("url", "")),
        "price": price,
        "price_raw": f"₹{price:,.0f}" if price else price_raw,
        "name": p.get("name") or "",
        "url": p.get("url") or "",
        "source": "product-list",
    }
