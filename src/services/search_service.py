"""Search orchestration — the decomposed run_pipeline for the SearchApi.io engine.

Two-call flow:
  1. search_products(query)      -> pick the best product_token
  2. get_product(product_token)  -> build route candidates from its offers

Then apply the ported L1 guards, build Gyftr voucher deals, assemble routes, and
attach the best cashback card to the recommended route only.

The output dict preserves the exact contract the frontend + WhatsApp depend on.
URL mode is gone, so mode is always "text".
"""
from __future__ import annotations

import re

from ..constants import KNOWN_BRANDS, MANUAL_TRUSTED_MERCHANTS, PRIORITY_MERCHANTS
from ..repositories import searchapi_repository, voucher_repository
from . import card_service, voucher_service

# ── price parsing ──────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(r"[\d][\d,]*(?:\.\d+)?")


def parse_price(value) -> float | None:
    """Parse a SearchApi price into a float. Accepts numbers or display strings
    like "₹1,299" / "$1,299.00". Returns None when no number is present."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = _PRICE_RE.search(str(value))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


# ── L1 guards (ported from pipeline.py) ─────────────────────────────────────────

def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_trusted_merchants_cache: set[str] | None = None


def _load_trusted_merchants() -> set[str]:
    global _trusted_merchants_cache
    if _trusted_merchants_cache is not None:
        return _trusted_merchants_cache
    whitelist = {_norm(n) for n in MANUAL_TRUSTED_MERCHANTS}
    for brand in voucher_repository.brand_names():
        whitelist.add(_norm(brand))
    _trusted_merchants_cache = whitelist
    return whitelist


def _is_trusted_merchant(merchant_name: str, whitelist: set[str]) -> bool:
    norm = _norm(merchant_name)
    if not norm:
        return False
    if norm in whitelist:
        return True
    for entry in whitelist:
        if len(entry) < 4:
            continue
        if norm.startswith(entry) or entry.startswith(norm) or entry in norm or norm in entry:
            return True
    return False


def _filter_trusted_only(results: list[dict]) -> tuple[list[dict], bool]:
    """Keep only whitelisted merchants. Returns (filtered, untrusted_warning).

    If nothing survives, returns the originals with untrusted_warning=True.
    """
    whitelist = _load_trusted_merchants()
    filtered = [r for r in results if _is_trusted_merchant(r.get("merchant") or "", whitelist)]
    if not filtered:
        return results, True
    return filtered, False


def _outlier_filter(results: list[dict]) -> tuple[list[dict], int]:
    """Remove results priced below 40% of median. Returns (filtered, removed_count)."""
    prices = [r.get("price") for r in results if r.get("price")]
    if len(prices) < 4:
        return results, 0
    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    mid = n // 2
    median = sorted_prices[mid] if n % 2 else (sorted_prices[mid - 1] + sorted_prices[mid]) / 2
    threshold = 0.4 * median
    filtered = [
        r for r in results
        if (r.get("price") or 0) >= threshold or not r.get("price")
    ]
    return filtered, len(results) - len(filtered)


def _dedup_by_merchant(results: list[dict]) -> list[dict]:
    """Per merchant, keep only the lowest-priced result."""
    seen: dict[str, dict] = {}
    for r in results:
        key = (r.get("merchant") or "").lower()
        if not key:
            continue
        price = r.get("price") or float("inf")
        if key not in seen or price < (seen[key].get("price") or float("inf")):
            seen[key] = r
    return list(seen.values())


def _priority_sort(results: list[dict]) -> list[dict]:
    """Priority merchants first (in declared order), then rest sorted by price."""
    def _key(r: dict) -> tuple:
        src = (r.get("merchant") or "").lower()
        for i, m in enumerate(PRIORITY_MERCHANTS):
            if m.lower() in src:
                return (i, 0.0)
        return (len(PRIORITY_MERCHANTS), r.get("price") or float("inf"))
    return sorted(results, key=_key)


# ── offer normalization ─────────────────────────────────────────────────────────

def _merchant_name(offer: dict) -> str:
    """Extract a merchant display name defensively — the SearchApi offer shape
    exposes merchant either as {"name": ...} or as a bare string."""
    merchant = offer.get("merchant")
    if isinstance(merchant, dict):
        return merchant.get("name") or ""
    if isinstance(merchant, str):
        return merchant
    # Fallbacks seen across engines.
    return offer.get("seller") or offer.get("store_name") or offer.get("seller_name") or ""


def _offer_price(offer: dict) -> float | None:
    """Prefer a numeric extracted_price field, else parse the display price."""
    for numeric_key in ("extracted_price", "price_extracted", "extracted_total_price"):
        val = offer.get(numeric_key)
        if isinstance(val, (int, float)):
            return float(val)
    return parse_price(offer.get("price") or offer.get("total_price"))


def _build_candidates(detail: dict) -> list[dict]:
    product = detail.get("product") or {}
    title = product.get("title") or detail.get("title") or ""
    candidates = []
    for offer in detail.get("offers") or []:
        merchant = _merchant_name(offer)
        price = _offer_price(offer)
        candidates.append({
            "merchant": merchant,
            "price": price,
            "title": title,
            "sellers": [{
                "link": offer.get("link"),
                "delivery": offer.get("delivery_price") or offer.get("delivery"),
            }],
            "match_type": "Listed",
        })
    return candidates


# ── route builder (ported from pipeline._build_routes) ──────────────────────────

def _build_routes(results: list[dict], vouchers: list[dict]) -> dict:
    """Merge results + vouchers into route objects sorted by final_cost.

    final_cost = voucher UPI effective price when a voucher exists, else the
    listed price (skip if neither). Dedups on (merchant, round(final_cost, 2)).
    Attaches the best cashback card to the recommended route only.
    """
    voucher_map = {v["merchant"].lower(): v for v in vouchers}
    routes = []
    seen: set[tuple] = set()

    for r in results:
        merchant = r.get("merchant") or ""
        listed_price = r.get("price")
        v = voucher_map.get(merchant.lower())

        if v:
            final_cost = v["upi"]["effective_price"]
        elif listed_price:
            final_cost = listed_price
        else:
            continue  # no price, no voucher — unrankable

        key = (merchant.lower(), round(final_cost, 2))
        if key in seen:
            continue
        seen.add(key)

        routes.append({
            "merchant": merchant,
            "listed_price": listed_price,
            "final_cost": final_cost,
            "sellers": r.get("sellers") or [],
            "match_type": r.get("match_type") or "",
            "title": r.get("title") or "",
            "voucher": v,
            "card_fomo": None,
        })

    routes.sort(key=lambda x: x["final_cost"])

    if not routes:
        return {"recommended": None, "alternatives": []}

    recommended = routes[0]

    card_fomo = card_service.best_card_for_purchase(
        merchant=recommended["merchant"],
        purchase_amount=recommended["final_cost"],
        has_voucher=recommended.get("voucher") is not None,
    )
    if card_fomo:
        recommended["card_fomo"] = {
            "card_name": card_fomo["card_name"],
            "actual_saving": card_fomo["actual_saving"],
            "final_cost_with_card": round(recommended["final_cost"] - card_fomo["actual_saving"], 2),
            "cap_amount": card_fomo["cap_amount"],
            "cap_period": card_fomo["cap_period"],
        }

    return {"recommended": recommended, "alternatives": routes[1:4]}


# ── source brand inference (best-effort, for the identity box) ───────────────────

def _infer_brand(name: str) -> str:
    lowered = (name or "").lower()
    for known in KNOWN_BRANDS:
        if re.search(r"\b" + re.escape(known) + r"\b", lowered):
            for word in name.split():
                if word.lower() == known:
                    return word
            return known
    return ""


# ── public orchestrator ──────────────────────────────────────────────────────────

def _product_candidate(p: dict) -> dict:
    """Shape a google_shopping result into a product the user can pick from."""
    price = None
    for numeric_key in ("extracted_price", "price_extracted"):
        val = p.get(numeric_key)
        if isinstance(val, (int, float)):
            price = float(val)
            break
    if price is None:
        price = parse_price(p.get("price"))
    return {
        "product_token": p.get("product_token"),
        "title": p.get("title") or "",
        "price": price,
        "price_raw": p.get("price"),
        "thumbnail": p.get("thumbnail") or p.get("image"),
        "source": p.get("seller") or p.get("source") or p.get("store") or "",
        "rating": p.get("rating"),
        "reviews": p.get("reviews"),
    }


def search_candidates(query: str) -> dict:
    """Step 1 of the two-step flow: google_shopping search only.

    Returns the list of candidate products the user picks from — does NOT run
    the (slow) google_product call. Never raises."""
    query = (query or "").strip()
    out = {"query": query, "products": [], "error": None}
    if not query:
        out["error"] = "Empty query."
        return out
    try:
        raw = searchapi_repository.search_products(query)
        if raw.get("error"):
            out["error"] = raw["error"]
            return out
        products = [
            _product_candidate(p)
            for p in raw.get("shopping_results", [])
            if p.get("product_token")
        ]
        if not products:
            out["error"] = "No products found for that search."
            return out
        out["products"] = products
    except Exception as e:  # never leak a stack trace
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def build_routes_for_token(product_token: str, query: str = "") -> dict:
    """Step 2 of the two-step flow: google_product on a chosen token → routes.

    Also the shared core used by the single-call ``search`` (WhatsApp). Never
    raises — errors come back in the ``error`` field."""
    query = (query or "").strip()
    output = {
        "input": query,
        "mode": "text",
        "source": {"name": query, "brand": _infer_brand(query), "price": None, "condition": None},
        "results": [],
        "size_comparison": None,
        "vouchers": [],
        "routes": {"recommended": None, "alternatives": []},
        "untrusted_sellers_warning": False,
        "error": None,
    }
    if not product_token:
        output["error"] = "No product selected."
        return output

    try:
        detail = searchapi_repository.get_product(product_token)
        if detail.get("error"):
            output["error"] = detail["error"]
            return output

        # Prefer the picked product's real title over the raw query.
        product = detail.get("product") or {}
        title = product.get("title") or detail.get("title") or ""
        if title:
            output["source"]["name"] = title
            output["source"]["brand"] = _infer_brand(title) or output["source"]["brand"]

        candidates = _build_candidates(detail)

        # L1 guards.
        candidates, untrusted_warning = _filter_trusted_only(candidates)
        candidates, _removed = _outlier_filter(candidates)
        candidates = _dedup_by_merchant(candidates)
        candidates = _priority_sort(candidates)

        output["untrusted_sellers_warning"] = untrusted_warning
        output["results"] = candidates
        output["vouchers"] = voucher_service.build_deals(candidates, product_name=query or title)
        output["routes"] = _build_routes(candidates, output["vouchers"])

    except Exception as e:  # never leak a stack trace to the router
        output["error"] = f"{type(e).__name__}: {e}"

    return output


def search(query: str) -> dict:
    """Single-call flow (used by WhatsApp): auto-pick the first product, then
    build routes. The web UI uses the two-step search_candidates + build_routes_for_token."""
    query = (query or "").strip()
    if not query:
        return {**build_routes_for_token("", query), "error": "Empty query."}

    listing = search_candidates(query)
    if listing.get("error"):
        base = build_routes_for_token("", query)
        base["error"] = listing["error"]
        return base

    token = listing["products"][0]["product_token"]
    return build_routes_for_token(token, query)


def get_product_detail(product_token: str) -> dict:
    """Raw google_product detail for a token, with offer prices normalized.

    Returns {"error": ...} on failure (no exceptions leak)."""
    detail = searchapi_repository.get_product(product_token)
    if detail.get("error"):
        return {"error": detail["error"], "product": None, "offers": []}
    product = detail.get("product") or {}
    offers = []
    for offer in detail.get("offers") or []:
        offers.append({
            "merchant": _merchant_name(offer),
            "price": _offer_price(offer),
            "price_raw": offer.get("price"),
            "total_price": offer.get("total_price"),
            "delivery_price": offer.get("delivery_price"),
            "link": offer.get("link"),
            "tag": offer.get("tag"),
        })
    return {
        "error": None,
        "product": product,
        "title": product.get("title") or detail.get("title") or "",
        "offers": offers,
        "typical_prices": detail.get("typical_prices"),
        "specifications": detail.get("specifications", []),
    }
