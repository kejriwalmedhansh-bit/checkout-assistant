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
        elif len(norm_brand) < 4:
            continue
        elif norm_merchant.startswith(norm_brand) or norm_brand.startswith(norm_merchant):
            rank = 1
        elif norm_brand in norm_merchant or norm_merchant in norm_brand:
            rank = 2
        else:
            continue

        if rank >= 1:
            brand_name_lower = voucher.get("brand_name", "").lower()
            if any(w in brand_name_lower for w in (
                "reseller", "authorised", "authorized", "premium",
                "future world", "store", "electronics", "mobile",
            )):
                continue
        candidates.append((rank, len(norm_brand), voucher))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]


def _parse_denominations(voucher: dict) -> tuple[bool, list[int]]:
    """Returns (is_custom, sorted_fixed_denoms).

    is_custom=True only when every product is a custom range (max_value > 0
    and != mrp) and there are no fixed-denomination products at all — i.e.
    the only way to buy is to load an arbitrary amount onto the voucher.
    When a voucher mixes fixed and custom-range products, the fixed
    denominations are real purchase options and take priority over treating
    the whole voucher as custom.
    """
    fixed = []
    has_custom = False
    for p in voucher.get("products", []):
        mrp = p.get("mrp")
        max_value = p.get("max_value") or 0
        if mrp is None:
            continue
        if max_value and max_value != mrp:
            has_custom = True
            continue
        fixed.append(int(mrp))
    if fixed:
        return False, sorted(set(fixed))
    return has_custom, []


def _greedy_voucher_amount(price: float, fixed_denoms: list[int]) -> int:
    """Largest sum of denominations (with repetition) not exceeding price."""
    remaining = int(price)
    total = 0
    for d in sorted(fixed_denoms, reverse=True):
        count = remaining // d
        total += count * d
        remaining -= count * d
    return total


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


_INSTRUCTION_EXCLUDE = [
    "also works at",
    "also be used on",
    "also accepted at",
    "can also be used online on",
    "can also be used at",
]


def _clean_instructions(html: str) -> list[str]:
    text = re.sub(r'<[^>]+>', '', html)
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if any(phrase in lower for phrase in _INSTRUCTION_EXCLUDE):
            continue
        result.append(line)
    return result


def calculate_effective_price(price: float, voucher: dict, payment_method: str = "upi") -> dict:
    discount_pct = _discount_pct(voucher, payment_method)

    is_custom, fixed_denoms = _parse_denominations(voucher)
    if is_custom or not fixed_denoms:
        voucher_amount = price
        remainder = 0.0
        is_custom = True
    else:
        voucher_amount = float(_greedy_voucher_amount(price, fixed_denoms))
        remainder = round(price - voucher_amount, 2)

    discount_amount = round(voucher_amount * discount_pct / 100, 2)
    effective_price = round(price - discount_amount, 2)
    redemption_type = voucher.get("redemption_type", "")

    return {
        "original_price": price,
        "voucher_amount": voucher_amount,
        "remainder_at_checkout": remainder,
        "is_custom": is_custom,
        "voucher_discount_pct": discount_pct,
        "voucher_discount_amount": discount_amount,
        "effective_price": effective_price,
        "payment_method": payment_method,
        "voucher_platform": "Gyftr",
        "voucher_url": f"https://www.gyftr.com/{voucher['slug']}",
        "redemption_type": REDEMPTION_LABELS.get(redemption_type, redemption_type),
        "denominations": _denominations(voucher),
        "redemption_instructions": _clean_instructions(voucher.get("important_instruction") or ""),
    }


def get_best_voucher_deal(merchant_name: str, price: float) -> dict | None:
    """Return the UPI-rate voucher deal for merchant_name, or None if no
    voucher exists, its UPI discount is 0, or price is below minimum denomination."""
    voucher = get_gyftr_voucher(merchant_name)
    if voucher is None:
        return None
    deal = calculate_effective_price(price, voucher, payment_method="upi")
    if not deal["voucher_discount_pct"]:
        return None
    if deal["voucher_amount"] == 0:
        return None
    return deal
