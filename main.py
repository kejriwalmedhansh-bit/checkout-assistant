"""
Checkout Assistant — Indian e-commerce price comparison engine.
Usage:  python main.py <product_url>
"""

import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

from db.models import init_db
from db.queries import get_cached_comparisons, save_comparisons
from engine.matcher import (
    match_product,
    get_price,
    get_regular_price,
    get_availability,
    detect_condition,
    _brand,
    _mpn,
    _sku,
)
from extractor.shopping import discover_merchants, merchant_from_url
from extractor.zyte_client import extract_product

load_dotenv()

# ── formatting helpers ────────────────────────────────────────────────────────

def _fmt_price(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"₹{float(value):>10,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _avail_tag(availability: str) -> str:
    if not availability:
        return ""
    lower = availability.lower()
    if "instock" in lower or "in_stock" in lower or "in stock" in lower:
        return " ✓"
    if "out" in lower:
        return " ✗ OOS"
    return ""


def _sep(char: str = "─", width: int = 110) -> str:
    return char * width


# ── step 1 ────────────────────────────────────────────────────────────────────

def step1_extract(url: str) -> dict:
    print(f"\n{_sep('═')}")
    print("STEP 1  Extract product from source URL")
    print(_sep("═"))
    print(f"  URL: {url}\n")

    product = extract_product(url)

    if not product:
        print("  ✗  Zyte returned no product data for this URL.")
        sys.exit(1)

    print(f"  Name     : {product.get('name', '—')}")
    print(f"  Brand    : {_brand(product) or '—'}")
    print(f"  SKU      : {_sku(product) or '—'}")
    print(f"  MPN      : {_mpn(product) or '—'}")

    price = get_price(product)
    reg = get_regular_price(product)
    print(f"  Price    : {_fmt_price(price)}")
    if reg and price and reg != price:
        pct = (1 - price / reg) * 100
        print(f"  Regular  : {_fmt_price(reg)}  (you save {pct:.0f}%)")
    print(f"  Currency : {product.get('currency', 'INR')}")
    print(f"  In stock : {get_availability(product) or '—'}")
    product["_condition"] = detect_condition(product)
    print(f"  Condition: {product['_condition'].title()}")

    return product


# ── step 2 ────────────────────────────────────────────────────────────────────

def step2_discover(product: dict) -> tuple[list[dict], list[dict]]:
    """
    Returns (google_signals, merchant_candidates).

    google_signals     — raw Google Shopping listings (no URLs); shown as price intelligence.
    merchant_candidates — results from direct merchant search, with real URLs for Step 3.
    """
    print(f"\n{_sep('═')}")
    print("STEP 2  Discover merchants via Google Shopping + direct merchant search")
    print(_sep("═"))

    google_signals, merchant_candidates = discover_merchants(product)

    # Display Google Shopping price signals
    print(f"\n  --- Google Shopping raw results ({len(google_signals)} items) ---")
    print(f"  {'#':<3} {'Price':>12}   {'Name':<65}")
    print(f"  {_sep('-', 90)}")
    for i, r in enumerate(google_signals[:30], 1):
        price_disp = (r.get("price_raw") or _fmt_price(r.get("price"))).strip()
        name_disp = (r.get("name") or "")[:64]
        print(f"  {i:<3} {price_disp:>12}   {name_disp}")
    if len(google_signals) > 30:
        print(f"  ... and {len(google_signals) - 30} more")

    # Display direct merchant results
    print(f"\n  --- Direct merchant search results ({len(merchant_candidates)} items with URLs) ---")
    print(f"  {'#':<3} {'Merchant':<28} {'Price':>12}   {'Name':<45}")
    print(f"  {_sep('-', 95)}")
    for i, r in enumerate(merchant_candidates, 1):
        price_disp = (r.get("price_raw") or _fmt_price(r.get("price"))).strip()
        name_disp = (r.get("name") or "")[:44]
        merch = (r.get("merchant") or "Unknown")[:27]
        print(f"  {i:<3} {merch:<28} {price_disp:>12}   {name_disp}")

    if not google_signals and not merchant_candidates:
        print("  (no results found)")

    return google_signals, merchant_candidates


# ── step 3 ────────────────────────────────────────────────────────────────────

def step3_verify(shopping_results: list[dict]) -> list[dict]:
    print(f"\n{_sep('═')}")
    print("STEP 3  Verify top results with Zyte Product extraction")
    print(_sep("═"))

    # Take up to 8 results that have a real HTTP URL
    candidates = [
        r for r in shopping_results
        if (r.get("url") or "").startswith("http")
    ][:8]

    if not candidates:
        print("  No verifiable URLs found in shopping results.")
        return []

    verified: list[dict] = []

    for i, cand in enumerate(candidates, 1):
        url = cand["url"]
        merchant = cand.get("merchant") or merchant_from_url(url)
        print(f"\n  [{i}/{len(candidates)}] {merchant}  —  {url[:80]}")
        try:
            prod = extract_product(url)
            if prod and prod.get("name"):
                prod["_source_url"] = url
                prod["_merchant_hint"] = merchant
                prod["_condition"] = detect_condition(prod)
                price = get_price(prod)
                avail = get_availability(prod)
                print(f"         name  : {prod['name'][:80]}")
                print(f"         price : {_fmt_price(price)}   avail: {avail or '—'}   cond: {prod['_condition']}")
                verified.append(prod)
            else:
                print("         ↳ no structured data — using shopping card values")
                verified.append(_fallback_product(cand, merchant))
        except Exception as exc:
            print(f"         ✗ extraction error ({exc.__class__.__name__}: {exc})")
            print("         ↳ using shopping card values")
            verified.append(_fallback_product(cand, merchant))

    return verified


def _fallback_product(cand: dict, merchant: str) -> dict:
    """Wrap raw shopping card data in a product-shaped dict (flat Zyte schema)."""
    price = cand.get("price")
    return {
        "name": cand.get("name") or "",
        "price": str(price) if price is not None else None,
        "currency": "INR",
        "_source_url": cand.get("url") or "",
        "_merchant_hint": merchant,
        "_fallback": True,
        "_condition": cand.get("_condition", "new"),
    }


# ── step 4 ────────────────────────────────────────────────────────────────────

def step4_match(original: dict, verified: list[dict], source_url: str) -> list[dict]:
    print(f"\n{_sep('═')}")
    print("STEP 4  Match & classify each verified result")
    print(_sep("═"))

    final: list[dict] = []

    for prod in verified:
        result = match_product(original, prod)
        if result["match_type"] == "No Match":
            print(f"  ✗ SKIP   {(prod.get('name') or '')[:60]}  [{result['variant_notes']}]")
            continue

        price = get_price(prod)
        reg_price = get_regular_price(prod)
        avail = get_availability(prod)
        brand = _brand(prod)
        mpn = _mpn(prod)
        merch = (
            prod.get("_merchant_hint")
            or merchant_from_url(prod.get("_source_url", ""))
        )
        currency = prod.get("currency") or "INR"

        record = {
            "merchant": merch,
            "name": prod.get("name") or "",
            "price": price,
            "regular_price": reg_price,
            "currency": currency,
            "match_type": result["match_type"],
            "variant_notes": result["variant_notes"],
            "source_url": prod.get("_source_url") or "",
            "availability": avail,
            "brand": brand,
            "mpn": mpn,
            "condition": prod.get("_condition", "new"),
        }
        final.append(record)
        icon = "✓" if result["match_type"] == "Exact Match" else "~"
        print(
            f"  {icon} [{result['match_type']:<14}]  "
            f"{merch:<28} {_fmt_price(price)}   {result['variant_notes']}"
        )

    return final


# ── step 5 ────────────────────────────────────────────────────────────────────

def step5_output(product_url: str, original: dict, matches: list[dict]) -> None:
    print(f"\n{_sep('═')}")
    print("STEP 5  Final price comparison  (sorted: cheapest first)")
    print(_sep("═"))

    # Always include the original product at the top of the "truth" set
    orig_record = {
        "product_url": product_url,
        "merchant": merchant_from_url(product_url),
        "name": original.get("name") or "",
        "price": get_price(original),
        "regular_price": get_regular_price(original),
        "currency": original.get("currency") or "INR",
        "match_type": "Exact Match",
        "variant_notes": "original listing",
        "source_url": product_url,
        "availability": get_availability(original),
        "brand": _brand(original),
        "mpn": _mpn(original),
        "condition": original.get("_condition", "new"),
    }

    # Deduplicate by source_url; original takes precedence
    seen_urls: set[str] = {product_url}
    all_records: list[dict] = [orig_record]
    for m in matches:
        url = m.get("source_url") or ""
        if url and url not in seen_urls:
            seen_urls.add(url)
            all_records.append({**m, "product_url": product_url})

    # Save to DB
    save_comparisons(product_url, all_records)
    print(f"\n  Saved {len(all_records)} records to checkout_assistant.db\n")

    _print_table(all_records)


def _print_table(records: list[dict]) -> None:
    with_price = sorted(
        [r for r in records if r.get("price") is not None],
        key=lambda r: r["price"],
    )
    no_price = [r for r in records if r.get("price") is None]
    rows = with_price + no_price

    hdr = (
        f"  {'#':<3} {'Merchant':<28} {'Price':>12} {'Match':<16}"
        f" {'Condition':<12} {'Avail':<8} {'Name':<45}"
    )
    print(hdr)
    print(f"  {_sep('-', 129)}")

    for i, r in enumerate(rows, 1):
        price_str = _fmt_price(r.get("price")).strip()
        avail_str = _avail_tag(r.get("availability") or "")
        name_str = (r.get("name") or "")[:44]
        merch_str = (r.get("merchant") or "—")[:27]
        match_str = (r.get("match_type") or "")[:15]
        cond_str = (r.get("condition") or "new").title()[:11]
        reg = r.get("regular_price")
        discount = ""
        if reg and r.get("price") and float(reg) > float(r["price"]):
            pct = (1 - float(r["price"]) / float(reg)) * 100
            discount = f" (-{pct:.0f}%)"

        print(
            f"  {i:<3} {merch_str:<28} {price_str + discount:>14} {match_str:<16}"
            f" {cond_str:<12} {avail_str:<8} {name_str}"
        )

    if with_price:
        cheapest = with_price[0]
        print(f"\n  {_sep('─', 50)}")
        print(f"  ★  Cheapest: {cheapest['merchant']}  at  {_fmt_price(cheapest['price'])}")
        if cheapest.get("source_url"):
            print(f"     URL: {cheapest['source_url']}")
        if cheapest.get("variant_notes") and cheapest["variant_notes"] != "original listing":
            print(f"     Note: {cheapest['variant_notes']}")


# ── cache-hit display ─────────────────────────────────────────────────────────

def show_cached(records: list[dict]) -> None:
    print(f"\n{_sep('═')}")
    print("CACHED RESULTS  (< 30 min old — skipping re-fetch)")
    print(_sep("═"))
    _print_table(records)


# ── entry point ───────────────────────────────────────────────────────────────

def run(url: str) -> None:
    init_db()

    cached = get_cached_comparisons(url)
    if cached:
        show_cached(cached)
        return

    original = step1_extract(url)
    _google_signals, merchant_candidates = step2_discover(original)
    verified = step3_verify(merchant_candidates)
    matches = step4_match(original, verified, url)
    step5_output(url, original, matches)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <product_url>")
        sys.exit(1)
    run(sys.argv[1])
