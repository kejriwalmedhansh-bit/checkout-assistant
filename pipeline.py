"""
pipeline.py — pure-compute layer for Checkout Assistant.

Each function returns structured data. No printing happens here.
main.py (CLI) calls these and formats output itself.
api.py (FastAPI) calls these and returns JSON.
"""

import re
import sys

from db.voucher_lookup import calculate_effective_price, get_best_voucher_deal, get_gyftr_voucher
from engine.matcher import _extract_size, filter_discovery_results
from extractor.discovery import build_search_query, discover_merchants, get_direct_urls
from extractor.zyte_client import extract_product


# ── shared helpers ────────────────────────────────────────────────────────────

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

_PRIORITY_MERCHANTS = [
    "croma", "vijay sales", "reliance digital", "tata cliq", "flipkart", "amazon"
]

_REFURB_RE = re.compile(
    r"\b(refurb(?:ished)?|renewed|open[- ]?box|pre[- ]?owned|second[- ]?hand)\b",
    re.IGNORECASE,
)

_ERROR_PAGE_RE = re.compile(
    r"\b(oops|something went wrong|404|page not found|not found|access denied|forbidden)\b",
    re.IGNORECASE,
)

_SIZE_TOKEN_RE = re.compile(r'^(\d+(?:\.\d+)?)(kg|mg|ml|l|g)$')


def _outlier_filter(results: list[dict]) -> tuple[list[dict], int]:
    """Remove results priced below 40% of median. Returns (filtered, removed_count)."""
    prices = [r.get("extracted_price") for r in results if r.get("extracted_price")]
    if len(prices) < 4:
        return results, 0
    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    mid = n // 2
    median = sorted_prices[mid] if n % 2 else (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    threshold = 0.4 * median
    filtered = [
        r for r in results
        if (r.get("extracted_price") or 0) >= threshold or not r.get("extracted_price")
    ]
    return filtered, len(results) - len(filtered)


def _dedup_by_merchant(results: list[dict]) -> list[dict]:
    """Per merchant, keep only the lowest-priced result."""
    seen: dict[str, dict] = {}
    for r in results:
        key = (r.get("source") or "").lower()
        if not key:
            continue
        price = r.get("extracted_price") or float("inf")
        if key not in seen or price < (seen[key].get("extracted_price") or float("inf")):
            seen[key] = r
    return list(seen.values())


def _priority_sort(results: list[dict]) -> list[dict]:
    """Priority merchants first (in declared order), then rest sorted by price."""
    def _key(r: dict) -> tuple:
        src = (r.get("source") or "").lower()
        for i, m in enumerate(_PRIORITY_MERCHANTS):
            if m.lower() in src:
                return (i, 0.0)
        return (len(_PRIORITY_MERCHANTS), r.get("extracted_price") or float("inf"))
    return sorted(results, key=_key)


def get_brand(product: dict) -> str:
    b = product.get("brand") or {}
    raw = (b.get("name") or "") if isinstance(b, dict) else str(b)
    noise = {"amazon prime", "amazon", "prime"}
    if raw.lower() in noise or "logo" in raw.lower():
        raw = ""

    if raw:
        raw_slug = raw.lower().replace(" ", "")
        if " " in raw:
            return raw.strip()
        for known in _KNOWN_BRANDS:
            if raw_slug == known:
                return raw.strip()
            if raw_slug.startswith(known) and len(raw_slug) > len(known):
                raw = ""
                break
        else:
            if raw:
                return raw.strip()

    name = (product.get("name") or "").lower()
    for known in _KNOWN_BRANDS:
        if known in name:
            for word in (product.get("name") or "").split():
                if word.lower() == known:
                    return word
            return known
    return ""


def get_condition(product: dict) -> str:
    if _REFURB_RE.search(product.get("name") or ""):
        return "refurbished"
    for prop in (product.get("additionalProperties") or []):
        if "condition" in (prop.get("name") or "").lower():
            if _REFURB_RE.search(prop.get("value") or ""):
                return "refurbished"
    if _REFURB_RE.search(product.get("description") or ""):
        return "refurbished"
    return "new"


def _normalize_size(qty: float, unit: str) -> tuple[float, str]:
    if unit == "kg":
        return qty * 1000, "g"
    if unit == "l":
        return qty * 1000, "ml"
    if unit == "mg":
        return qty / 1000, "g"
    return qty, unit


_ACCESSORY_WORDS = {
    "case", "cover", "silicone", "skin", "pouch", "strap",
    "protector", "customized", "custom", "personalized", "engraved",
}

_MODEL_NUMBER_RE = re.compile(r'\b(\d{2,4})\b')


def _product_relevance_filter(results: list[dict], query: str) -> list[dict]:
    words = query.split()
    model_number = None
    product_line = None
    for i, word in enumerate(words):
        m = _MODEL_NUMBER_RE.fullmatch(word)
        if m:
            model_number = m.group(1)
            if i > 0:
                product_line = words[i - 1]
            break

    if model_number is None:
        return results

    model_re = re.compile(r'\b' + re.escape(model_number) + r'\b', re.IGNORECASE)

    kept = []
    for r in results:
        title = r.get("title") or ""
        title_lower = title.lower()
        if not model_re.search(title):
            continue
        if product_line and product_line.lower() not in title_lower:
            continue
        if any(word in title_lower for word in _ACCESSORY_WORDS):
            continue
        kept.append(r)
    return kept


# ── step 1 — extract source product ──────────────────────────────────────────

def step1_extract(url: str) -> dict:
    product = extract_product(url)
    name = (product.get("name") or "").strip()

    if not name:
        return {"error": "Could not extract product from this URL."}

    if _ERROR_PAGE_RE.search(name):
        return {"error": f"Extraction returned an error page: '{name[:80]}'"}

    price_raw = product.get("price")
    try:
        price = float(price_raw) if price_raw else None
    except (ValueError, TypeError):
        price = None

    return {
        "product": product,
        "name": name,
        "brand": get_brand(product),
        "price": price,
        "condition": get_condition(product),
        "availability": product.get("availability", ""),
        "error": None,
    }


# ── step 2 — discover + match ─────────────────────────────────────────────────

def step2_discover_and_match(source_product: dict) -> dict:
    brand_str = get_brand(source_product)
    query = build_search_query(brand=brand_str, name=source_product.get("name", ""))
    raw_results = discover_merchants(query, max_results=50)
    raw_results = _product_relevance_filter(raw_results, source_product.get("name", ""))
    matched = filter_discovery_results(
        raw_results,
        source_name=source_product.get("name", ""),
        source_brand=brand_str,
        include_similar=True,
    )
    filtered, removed = _outlier_filter(matched)
    filtered = _dedup_by_merchant(filtered)
    filtered = _priority_sort(filtered)
    return {
        "query": query,
        "raw_count": len(raw_results),
        "matched_count": len(filtered),
        "removed_outliers": removed,
        "results": filtered,
    }


def step2_discover_only(query: str) -> dict:
    raw_results = discover_merchants(query, max_results=50)
    raw_results = _product_relevance_filter(raw_results, query)

    for r in raw_results:
        r["match_type"] = "Listed"

    filtered, removed = _outlier_filter(raw_results)
    filtered = _dedup_by_merchant(filtered)
    filtered = _priority_sort(filtered)

    return {
        "query": query,
        "raw_count": len(raw_results) + removed,
        "removed_outliers": removed,
        "results": filtered,
    }


# ── step 3 — resolve direct URLs ─────────────────────────────────────────────

def step3_resolve(matched: list[dict], source_brand: str = "") -> dict:
    enriched = get_direct_urls(matched, source_brand=source_brand)
    total_urls = sum(len(r.get("sellers", [])) for r in enriched)
    return {
        "results": enriched,
        "total_urls": total_urls,
    }


# ── step 4 — ranked results ───────────────────────────────────────────────────

def step4_output(enriched: list[dict]) -> list[dict]:
    rows = []
    for i, r in enumerate(enriched, 1):
        extracted = r.get("extracted_price") or 0
        rows.append({
            "rank": i,
            "merchant": r.get("source") or "",
            "price": extracted if extracted else None,
            "price_raw": r.get("price") or "",
            "match_type": r.get("match_type") or "",
            "submodel_conflict": bool(r.get("submodel_conflict")),
            "title": r.get("title") or "",
            "match_notes": r.get("match_notes") or "",
            "sellers": r.get("sellers") or [],
        })
    return rows


# ── step 4b — size/quantity comparison ───────────────────────────────────────

def step4b_size_comparison(enriched: list[dict]) -> dict | None:
    groups: dict[tuple[float, str], list[dict]] = {}
    for r in enriched:
        title = r.get("title") or ""
        for raw_size in _extract_size(title):
            m = _SIZE_TOKEN_RE.match(raw_size)
            if not m:
                continue
            qty, unit = _normalize_size(float(m.group(1)), m.group(2))
            groups.setdefault((qty, unit), []).append(r)
            break

    if len(groups) < 2:
        return None

    best_key = None
    best_unit_price = None

    output_groups = []
    for key in sorted(groups.keys()):
        qty, unit = key
        items = []
        for r in groups[key]:
            price = r.get("extracted_price") or 0
            if not price:
                continue
            unit_price = price / qty
            items.append({
                "merchant": r.get("source") or "",
                "price": price,
                "unit_price": round(unit_price, 2),
            })
            if best_unit_price is None or unit_price < best_unit_price:
                best_unit_price = unit_price
                best_key = key

        output_groups.append({
            "label": f"{qty:g}{unit}",
            "qty": qty,
            "unit": unit,
            "is_best": False,
            "items": items,
        })

    if best_key is None:
        return None

    best_label = f"{best_key[0]:g}{best_key[1]}"
    for g in output_groups:
        g["is_best"] = g["label"] == best_label

    return {
        "best_unit": best_key[1],
        "best_label": best_label,
        "groups": output_groups,
    }


# ── step 5 — Gyftr voucher opportunities ─────────────────────────────────────

def step5_vouchers(enriched: list[dict]) -> list[dict]:
    results = []
    seen_merchants = set()

    for r in enriched:
        if r.get("match_type") not in ("Exact Match", "Listed"):
            continue
        merchant = r.get("source", "")
        price = r.get("extracted_price") or 0
        merchant_key = merchant.lower()
        if not merchant or not price or merchant_key in seen_merchants:
            continue
        seen_merchants.add(merchant_key)

        voucher = get_gyftr_voucher(merchant)
        if voucher is None:
            continue

        redemption_type_raw = voucher.get("redemption_type", "")
        offline_only = redemption_type_raw == "OFF"

        # For offline vouchers, still include but flag them
        deal = get_best_voucher_deal(merchant, price)
        if deal is None:
            continue

        card_deal = calculate_effective_price(price, voucher, "card")

        results.append({
            "merchant": merchant,
            "product_price": price,
            "voucher_url": deal["voucher_url"],
            "offline_only": offline_only,
            "upi": {
                "pct": deal["voucher_discount_pct"],
                "voucher_amount": deal["voucher_amount"],
                "remainder": deal.get("remainder_at_checkout") or 0,
                "saving": deal["voucher_discount_amount"],
                "effective_price": deal["effective_price"],
            },
            "card": {
                "pct": card_deal["voucher_discount_pct"],
                "saving": card_deal["voucher_discount_amount"],
                "effective_price": card_deal["effective_price"],
            },
            "redemption_type": deal["redemption_type"],
            "denominations": deal["denominations"],
            "redemption_instructions": deal.get("redemption_instructions", []),
        })

    return results


# ── main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(input_str: str) -> dict:
    from db.cache import init_cache
    init_cache()

    output = {
        "input": input_str,
        "mode": "url" if _is_url(input_str) else "text",
        "source": None,
        "discovery": {},
        "resolve": {},
        "results": [],
        "size_comparison": None,
        "vouchers": [],
        "error": None,
    }

    try:
        if _is_url(input_str):
            s1 = step1_extract(input_str)
            if s1.get("error"):
                output["error"] = s1["error"]
                return output
            output["source"] = s1
            source_product = s1["product"]
            source_brand = s1["brand"]
            s2 = step2_discover_and_match(source_product)
        else:
            query = input_str.strip()
            pseudo_product = {"name": query}
            source_brand = get_brand(pseudo_product)
            output["source"] = {"name": query, "brand": source_brand, "price": None, "condition": None}
            s2 = step2_discover_only(query)

        output["discovery"] = s2
        s3 = step3_resolve(s2["results"], source_brand=source_brand)
        output["resolve"] = s3
        enriched = s3["results"]
        output["results"] = step4_output(enriched)
        output["size_comparison"] = step4b_size_comparison(enriched)
        output["vouchers"] = step5_vouchers(enriched)

    except SystemExit:
        raise
    except Exception as e:
        output["error"] = f"{type(e).__name__}: {e}"

    return output
