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
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "amazon.in" in host:
        # Force English locale — Amazon India defaults to Hindi for Zyte IPs.
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if "language" not in qs:
            qs["language"] = ["en_IN"]
            new_query = urlencode({k: v[0] for k, v in qs.items()})
            parsed = parsed._replace(query=new_query)
            url = urlunparse(parsed)

    if "myntra.com" in host:
        # Tracking params on Myntra /buy URLs trigger bot detection; strip them.
        url = urlunparse(parsed._replace(query=""))

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
_DEVICE_URL_RE = re.compile(r'\b(macbook|iphone|ipad|laptop|macmini|imac)\b', re.IGNORECASE)

# Short acronyms that should be uppercased in slug-derived names.
_ACRONYMS = {"cc", "bb", "spf", "uv", "hd", "sd", "aa", "usb", "led", "lcd"}


def _slug_to_name(slug: str) -> str:
    """Convert a URL slug to a display name.

    Strips trailing 5+-digit IDs (e.g. '-37836'), uppercases known acronyms,
    title-cases everything else.
    """
    slug = re.sub(r'-\d{5,}$', '', slug)
    words = []
    for w in slug.split("-"):
        if not w:
            continue
        words.append(w.upper() if w.lower() in _ACRONYMS else w.title())
    return " ".join(words)


def _slug_fallback_nykaa(url: str) -> dict:
    """Derive a product name from the Nykaa URL slug when Zyte extraction fails.

    URL shape:  /slug/p/id  or  /brand/slug/p/id
    We take the segment immediately before '/p/'.
    """
    parts = urlparse(url).path.strip("/").split("/")
    try:
        p_idx = parts.index("p")
        slug = parts[p_idx - 1] if p_idx > 0 else parts[0]
    except ValueError:
        slug = parts[0]
    name = _slug_to_name(slug)
    return {"name": name} if name else {}


def _slug_fallback_myntra(url: str) -> dict:
    """Derive brand + product name from the Myntra URL slug when Zyte fails.

    URL shape:  /category/brand/product-slug/id[/buy]
    """
    parts = urlparse(url).path.strip("/").split("/")
    # Drop trailing 'buy' and numeric ID segments to reach the product slug.
    clean = [p for p in parts if p and not p.isdigit() and p != "buy"]
    # clean[0] = category, clean[1] = brand, clean[2] = product slug
    if len(clean) < 3:
        return {}
    brand = _slug_to_name(clean[1])
    name = _slug_to_name(clean[2])
    return {"name": name, "brand": {"name": brand}} if name else {}


def _amazon_html_fallback(url: str, partial: dict) -> dict:
    """Fetch browser HTML and extract name/price/brand for Amazon pages when
    structured extraction returns no name (probability too low)."""
    try:
        html = fetch_browser_html(url)
    except Exception:
        return partial

    name_m = _AMAZON_TITLE_RE.search(html)
    brand_m = _AMAZON_BRAND_RE.search(html)

    name = _TAG_RE.sub("", name_m.group(1)).strip() if name_m else ""
    brand_text = _TAG_RE.sub("", brand_m.group(1)).strip() if brand_m else ""
    brand = re.sub(r'^(visit\s+the\s+|brand[:\s]+)', '', brand_text, flags=re.IGNORECASE).replace("Store", "").strip()

    # Price: search within corePriceDisplay_desktop_feature_div first — this
    # avoids matching discount-badge elements ("₹179 off") that also use the
    # a-price-whole class earlier in the page.
    raw_price = ""
    core_idx = html.find("corePriceDisplay_desktop_feature_div")
    if core_idx != -1:
        snippet = html[core_idx:core_idx + 3000]
        core_m = _AMAZON_PRICE_RE.search(snippet)
        if core_m:
            candidate = core_m.group(1).replace(",", "")
            if candidate.isdigit() and int(candidate) >= 1000:
                raw_price = candidate
    if not raw_price:
        price_m = _AMAZON_PRICE_RE.search(html)
        if price_m:
            raw_price = price_m.group(1).replace(",", "").strip()
    # For device URLs (MacBook, iPhone, iPad …) discard prices that look like
    # discount amounts (< ₹1000) rather than actual retail prices.
    if raw_price and _DEVICE_URL_RE.search(url):
        if raw_price.isdigit() and int(raw_price) < 1000:
            raw_price = ""

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


def _zyte_product(url: str) -> dict:
    """POST to Zyte Extract with product:True. Returns {} on timeout or HTTP error."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(ZYTE_API_URL, json={"url": url, "product": True}, auth=_auth())
            resp.raise_for_status()
        return resp.json().get("product") or {}
    except (httpx.ReadTimeout, httpx.HTTPError) as e:
        print(f"  [Zyte] Request failed ({type(e).__name__}) — {e}")
        return {}


def extract_product(url: str) -> dict:
    """Call Zyte Extract API with Product data type. Returns the product dict.

    Response schema (flat, no 'offers' nesting):
      name, price (str), regularPrice (str), currency, sku, brand.name,
      mainImage.url, aggregateRating, metadata, ...

    Falls back to browserHtml parsing for Amazon pages when structured
    extraction returns no product name (probability too low).
    """
    url = _normalise_url(url)
    product = _zyte_product(url)

    # Myntra retry: /buy URL (even without params) can time out or return no
    # name; drop /buy from the path and try the canonical product URL.
    if not product.get("name") and "myntra.com" in url:
        path = urlparse(url).path.rstrip("/")
        if path.endswith("/buy"):
            retry_url = urlunparse(urlparse(url)._replace(path=path[:-4], query=""))
            print("  [Zyte] Myntra /buy returned no name — retrying without /buy")
            product = _zyte_product(retry_url)

    # Slug-based fallbacks when Zyte returns no name at all.
    if not product.get("name") and "myntra.com" in url:
        print("  [Zyte] Using Myntra URL slug as product name")
        product = {**product, **_slug_fallback_myntra(url)}

    if not product.get("name") and "nykaa.com" in url:
        print("  [Zyte] Using Nykaa URL slug as product name")
        product = {**product, **_slug_fallback_nykaa(url)}

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
