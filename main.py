"""
Checkout Assistant — Indian e-commerce price comparison engine.
Usage:  python main.py <product_url>
        python main.py "<product name>"
"""

import re
import sys

from dotenv import load_dotenv

from db.cache import init_cache
from db.voucher_lookup import calculate_effective_price, get_best_voucher_deal, get_gyftr_voucher
from engine.matcher import filter_discovery_results
from extractor.discovery import build_search_query, discover_merchants, get_direct_urls
from extractor.zyte_client import extract_product

load_dotenv()


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_price(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"₹{float(value):>10,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _sep(char="─", width=115):
    return char * width


def _is_url(text: str) -> bool:
    return text.strip().lower().startswith(("http://", "https://"))


_KNOWN_BRANDS = [
    "boat", "noise", "apple", "samsung", "sony", "lg", "hp", "dell", "lenovo",
    "asus", "acer", "microsoft", "google", "oneplus", "realme", "xiaomi",
    "oppo", "vivo", "motorola", "nokia", "jbl", "bose",
    "nike", "adidas", "puma", "reebok", "skechers", "fila", "asics",
    "lakme", "mamaearth", "himalaya", "nivea", "dove", "loreal", "garnier",
    "titan", "fastrack", "casio", "philips",
]


def _brand(product: dict) -> str:
    b = product.get("brand") or {}
    raw = (b.get("name") or "") if isinstance(b, dict) else str(b)
    noise = {"amazon prime", "amazon", "prime"}
    if raw.lower() in noise or "logo" in raw.lower():
        raw = ""

    if raw:
        raw_slug = raw.lower().replace(" ", "")
        # Accept if it's a clean multi-word brand name
        if " " in raw:
            return raw.strip()
        # Reject website handles (e.g. "boAtlifestylein") — check if a known
        # brand is a prefix of the slug and the slug has extra suffix chars
        for known in _KNOWN_BRANDS:
            if raw_slug == known:
                return raw.strip()
            if raw_slug.startswith(known) and len(raw_slug) > len(known):
                # Handle is the brand domain — fall through to name extraction
                raw = ""
                break
        else:
            if raw:
                return raw.strip()

    # Name-based fallback: find known brand in product name
    name = (product.get("name") or "").lower()
    for known in _KNOWN_BRANDS:
        if known in name:
            # Preserve original casing from the name
            for word in (product.get("name") or "").split():
                if word.lower() == known:
                    return word
            return known
    return ""


_REFURB_RE = re.compile(
    r"\b(refurb(?:ished)?|renewed|open[- ]?box|pre[- ]?owned|second[- ]?hand)\b",
    re.IGNORECASE,
)

_ERROR_PAGE_RE = re.compile(
    r"\b(oops|something went wrong|404|page not found|not found|access denied|forbidden)\b",
    re.IGNORECASE,
)


def _condition(product: dict) -> str:
    if _REFURB_RE.search(product.get("name") or ""):
        return "refurbished"
    for prop in (product.get("additionalProperties") or []):
        if "condition" in (prop.get("name") or "").lower():
            if _REFURB_RE.search(prop.get("value") or ""):
                return "refurbished"
    if _REFURB_RE.search(product.get("description") or ""):
        return "refurbished"
    return "new"


# ── step 1 — extract source product ──────────────────────────────────────────

def step1_extract(url: str) -> dict:
    print(f"\n{_sep('═')}")
    print("STEP 1  Extract product from source URL")
    print(_sep("═"))
    print(f"  URL: {url}\n")

    product = extract_product(url)

    name = (product.get("name") or "").strip()

    if not name:
        print("  ✗  Could not extract product from this URL.")
        print("     Try the clean product URL without tracking parameters,")
        print("     or paste the product name directly.")
        sys.exit(0)

    if _ERROR_PAGE_RE.search(name):
        print(f"  ✗  Extraction returned an error page: '{name[:80]}'")
        print("     The merchant's URL may require a login or blocks automated access.")
        print("     Try the clean product URL without tracking parameters.")
        sys.exit(0)

    price_raw = product.get("price")
    try:
        price = float(price_raw) if price_raw else None
    except (ValueError, TypeError):
        price = None

    print(f"  Name      : {name}")
    print(f"  Brand     : {_brand(product) or '—'}")
    print(f"  Price     : {_fmt_price(price)}")
    print(f"  Condition : {_condition(product).title()}")
    print(f"  In stock  : {product.get('availability', '—')}")

    return product


# ── step 2 — discover + match ─────────────────────────────────────────────────

def step2_discover_and_match(source_product: dict) -> list[dict]:
    print(f"\n{_sep('═')}")
    print("STEP 2  Discover & match via SerpAPI Google Shopping")
    print(_sep("═"))

    brand_str = _brand(source_product)

    query = build_search_query(
        brand=brand_str,
        name=source_product.get("name", ""),
    )
    print(f"\n[Discovery] Searching: '{query}'")

    raw_results = discover_merchants(query, max_results=15)
    print(f"[Discovery] Got {len(raw_results)} results from Google Shopping")

    matched = filter_discovery_results(
        raw_results,
        source_name=source_product.get("name", ""),
        source_brand=brand_str,
        include_similar=True,
    )
    print(f"[Matcher] {len(matched)} results after filtering")

    return matched


# ── step 2b — discover only (text query, no source product) ──────────────────

def step2_discover_only(query: str) -> list[dict]:
    print(f"\n{_sep('═')}")
    print("STEP 2  Discover via SerpAPI Google Shopping (text query)")
    print(_sep("═"))
    print(f"\n[Discovery] Searching: '{query}'")

    raw_results = discover_merchants(query, max_results=15)
    print(f"[Discovery] Got {len(raw_results)} results from Google Shopping")
    print("[Matcher] Skipped — no source product to compare against; showing all results")

    for r in raw_results:
        r["match_type"] = "Exact Match"

    return sorted(raw_results, key=lambda r: r.get("extracted_price") or float("inf"))


# ── step 3 — resolve direct URLs ─────────────────────────────────────────────

def step3_resolve(matched: list[dict], source_brand: str = "") -> list[dict]:
    print(f"\n{_sep('═')}")
    print("STEP 3  Resolve direct merchant URLs via SerpAPI immersive")
    print(_sep("═"))
    enriched = get_direct_urls(matched, source_brand=source_brand)
    total_urls = sum(len(r.get("sellers", [])) for r in enriched)
    print(f"  Resolved {total_urls} direct URL(s) across {len(enriched)} result(s)")
    return enriched


# ── step 4 — ranked output table ─────────────────────────────────────────────

def step4_output(enriched: list[dict]) -> None:
    print(f"\n{_sep('═')}")
    print("STEP 4  Ranked results  (Exact first, then Similar — sorted by price)")
    print(_sep("═"))

    if not enriched:
        print("\n  No matching results found.")
        return

    hdr = (
        f"  {'#':<3} {'Merchant':<25} {'Price':>12} {'Match':<16}"
        f" {'Sub?':<5} {'Title'}"
    )
    print(f"\n{hdr}")
    print(f"  {_sep('-', 112)}")

    for i, r in enumerate(enriched, 1):
        extracted = r.get("extracted_price") or 0
        price_str = _fmt_price(extracted).strip() if extracted else (r.get("price") or "N/A")
        merchant = (r.get("source") or "—")[:24]
        match_type = (r.get("match_type") or "")[:15]
        sub = "✓" if r.get("submodel_conflict") else ""
        title = (r.get("title") or "")[:60]
        notes = r.get("match_notes", "")

        print(
            f"  {i:<3} {merchant:<25} {price_str:>12} {match_type:<16}"
            f" {sub:<5} {title}"
        )
        if notes:
            print(f"       ↳ {notes}")

        for s in r.get("sellers", []):
            link = s.get("link", "")
            s_price = s.get("price") or ""
            s_name = (s.get("name") or "")[:22]
            print(f"       → {s_name:<23} {s_price:<10} {link}")


# ── step 5 — Gyftr voucher opportunities ──────────────────────────────────────

def step5_vouchers(enriched: list[dict]) -> None:
    print(f"\n{_sep('═')}")
    print("STEP 5  Gyftr Voucher Opportunities")
    print(_sep("═"))

    any_found = False
    seen_merchants = set()
    for r in enriched:
        if r.get("match_type") != "Exact Match":
            continue
        merchant = r.get("source", "")
        price = r.get("extracted_price") or 0
        merchant_key = merchant.lower()
        if not merchant or not price or merchant_key in seen_merchants:
            continue
        seen_merchants.add(merchant_key)

        deal = get_best_voucher_deal(merchant, price)
        if deal is None:
            continue

        voucher = get_gyftr_voucher(merchant)
        card_deal = calculate_effective_price(price, voucher, "card")

        upi_saving = deal["voucher_discount_amount"]
        card_saving = card_deal["voucher_discount_amount"]
        upi_pct = deal["voucher_discount_pct"]
        card_pct = card_deal["voucher_discount_pct"]
        pct_diff = round(upi_pct - card_pct, 1)
        saving_diff = round(upi_saving - card_saving, 2)

        any_found = True
        print(f"\n  💡 {merchant} — Buy via Gyftr voucher")
        print(f"     Buy voucher at: {deal['voucher_url']}")

        print(f"\n     Recommended: UPI ({upi_pct}%)")
        voucher_line = f"Buy ₹{deal['voucher_amount']:,.0f} in vouchers"
        if deal["remainder_at_checkout"]:
            voucher_line += f" + pay ₹{deal['remainder_at_checkout']:,.0f} at checkout"
        print(f"     {voucher_line}")
        print(f"     You save ₹{upi_saving:,.0f}")
        print(f"     Effective price: ₹{deal['effective_price']:,.0f}")

        print(f"\n     Alternative: Credit Card ({card_pct}%)")
        print(f"     You save ₹{card_saving:,.0f} — that's ₹{saving_diff:,.0f} less than UPI ({pct_diff}% difference)")
        print(f"     💳 Credit card optimisation coming soon")

        print(f"\n     Redemption: {deal['redemption_type']}")
        print(f"     Denominations: {deal['denominations']}")

    if not any_found:
        print("\n  No Gyftr vouchers found for Exact Match merchants in this run.")


# ── entry point ───────────────────────────────────────────────────────────────

def run(input_str: str) -> None:
    init_cache()
    try:
        if _is_url(input_str):
            source_product = step1_extract(input_str)
            matched = step2_discover_and_match(source_product)
            source_brand = _brand(source_product)
        else:
            query = input_str.strip()
            source_brand = _brand({"name": query})

            print(f"\n{_sep('═')}")
            print("STEP 1  Skipped — input is a search query, not a URL")
            print(_sep("═"))
            print(f"  Query : {query}")
            print(f"  Brand : {source_brand or '—'}")

            matched = step2_discover_only(query)

        enriched = step3_resolve(matched, source_brand=source_brand)
        step4_output(enriched)
        step5_vouchers(enriched)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\n{_sep('═')}")
        print("  ✗  Something went wrong while processing this request.")
        print(f"     ({type(e).__name__}: {e})")
        print(_sep("═"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <product_url_or_name>")
        sys.exit(1)
    run(sys.argv[1])
