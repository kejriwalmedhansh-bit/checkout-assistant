"""
voucher_lookup.py — Match merchants to Gyftr gift-card vouchers and compute
the effective price after applying the voucher's payment-method discount.
"""

import json
import re
from pathlib import Path

VOUCHERS_PATH = Path(__file__).resolve().parent / "gyftr_vouchers.json"

REDEMPTION_LABELS = {"ON": "Online", "OFF": "Offline", "B": "Both"}

# Maps the caller-facing payment_method argument to the pg_name(s) used in
# the scraped pgdis[] data. "card" checks both Credit and Debit since Gyftr
# rarely differentiates between them (only 1 of 379 brands does).
PAYMENT_METHOD_TO_PG_NAMES = {
    "card": ["Credit Card", "Debit Card"],
    "netbanking": ["Net Banking"],
    "upi": ["UPI"],
    "paytm_upi": ["PAYTM UPI"],
    "amazon_pay": ["Amazon Pay"],
}

_vouchers_cache: list[dict] | None = None


def _load_vouchers() -> list[dict]:
    global _vouchers_cache
    if _vouchers_cache is None:
        with open(VOUCHERS_PATH) as f:
            _vouchers_cache = json.load(f)
    return _vouchers_cache


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def get_gyftr_voucher(merchant_name: str) -> dict | None:
    """Find the Gyftr voucher whose brand_name best matches merchant_name.

    Case-insensitive, partial match OK (e.g. "amazon.in" matches "Amazon").
    When multiple brands match (e.g. "Amazon", "Amazon Fresh", "Amazon Prime
    Membership"), prefers the closest/shortest match over more specific
    sub-brand vouchers.
    """
    norm_merchant = _normalize(merchant_name)
    if not norm_merchant:
        return None

    candidates = []
    for voucher in _load_vouchers():
        norm_brand = _normalize(voucher.get("brand_name", ""))
        if not norm_brand:
            continue
        if norm_brand == norm_merchant:
            rank = 0
        elif norm_merchant.startswith(norm_brand) or norm_brand.startswith(norm_merchant):
            rank = 1
        elif norm_brand in norm_merchant or norm_merchant in norm_brand:
            rank = 2
        else:
            continue
        candidates.append((rank, len(norm_brand), voucher))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]


def _denominations(voucher: dict) -> str:
    values = []
    for p in voucher.get("products", []):
        mrp, max_value = p.get("mrp"), p.get("max_value")
        if max_value and max_value != mrp:
            values.append(f"{mrp}-{max_value} (custom)")
        elif mrp is not None:
            values.append(str(mrp))
    fixed = sorted({v for v in values if v.isdigit()}, key=int)
    custom = list(dict.fromkeys(v for v in values if not v.replace(".", "", 1).isdigit()))
    return " / ".join(fixed + custom)


def _discount_pct(voucher: dict, payment_method: str) -> float:
    pg_names = PAYMENT_METHOD_TO_PG_NAMES.get(payment_method.lower(), [])
    pg_map = {pg.get("pg_name"): pg.get("brand_pg_discount") for pg in voucher.get("pgdis", [])}
    found = [pg_map[name] for name in pg_names if pg_map.get(name) is not None]
    if found:
        return max(found)
    return voucher.get("defaut_pg_dis") or 0


def calculate_effective_price(price: float, voucher: dict, payment_method: str = "upi") -> dict:
    discount_pct = _discount_pct(voucher, payment_method)
    discount_amount = round(price * discount_pct / 100, 2)
    effective_price = round(price - discount_amount, 2)
    redemption_type = voucher.get("redemption_type", "")

    return {
        "original_price": price,
        "voucher_discount_pct": discount_pct,
        "voucher_discount_amount": discount_amount,
        "effective_price": effective_price,
        "payment_method": payment_method,
        "voucher_platform": "Gyftr",
        "voucher_url": f"https://www.gyftr.com/{voucher['slug']}",
        "redemption_type": REDEMPTION_LABELS.get(redemption_type, redemption_type),
        "denominations": _denominations(voucher),
    }


def get_best_voucher_deal(merchant_name: str, price: float) -> dict | None:
    """Return the UPI-rate voucher deal for merchant_name, or None if no
    voucher exists or its UPI discount is 0."""
    voucher = get_gyftr_voucher(merchant_name)
    if voucher is None:
        return None
    deal = calculate_effective_price(price, voucher, payment_method="upi")
    if not deal["voucher_discount_pct"]:
        return None
    return deal
