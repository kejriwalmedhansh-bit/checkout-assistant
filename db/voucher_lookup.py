"""
voucher_lookup.py — Match merchants to Gyftr gift-card vouchers and compute
the effective price after applying the voucher's payment-method discount.
"""

import json
import math
import re
from pathlib import Path

VOUCHERS_PATH = Path(__file__).resolve().parent / "gyftr_master.json"

# Maps the caller-facing payment_method argument to the keys used in the
# discounts dict of gyftr_master.json.
PAYMENT_METHOD_TO_DISCOUNT_KEYS = {
    "card": ["Credit Card", "Debit Card"],
    "netbanking": ["Net Banking"],
    "upi": ["UPI"],
    "paytm_upi": ["UPI"],
    "amazon_pay": ["UPI"],
}

_vouchers_cache: list[dict] | None = None


def _load_vouchers() -> list[dict]:
    global _vouchers_cache
    if _vouchers_cache is None:
        with open(VOUCHERS_PATH) as f:
            _vouchers_cache = list(json.load(f).values())
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

    is_custom=True when denominations is empty — the voucher has no fixed
    face values and accepts an arbitrary load amount.
    """
    denoms = sorted(set(int(d) for d in (voucher.get("denominations") or []) if d is not None))
    if denoms:
        return False, denoms
    return True, []


def _greedy_voucher_amount(price: float, fixed_denoms: list[int], stack_limit: int | None = None, value_cap: float | None = None) -> int:
    """Largest sum of denominations (with repetition) not exceeding price, stack_limit, and value_cap."""
    remaining = int(price)
    total = 0
    count_used = 0
    for d in sorted(fixed_denoms, reverse=True):
        if stack_limit is not None:
            room_by_count = stack_limit - count_used
            if room_by_count <= 0:
                break
        else:
            room_by_count = float('inf')
        if value_cap is not None:
            room_by_value = value_cap - total
            if room_by_value <= 0:
                break
            room_by_value_count = room_by_value // d
        else:
            room_by_value_count = float('inf')
        count = min(remaining // d, room_by_count, room_by_value_count)
        total += count * d
        remaining -= count * d
        count_used += count
    return total


def _denominations(voucher: dict) -> str:
    denoms = sorted(set(int(d) for d in (voucher.get("denominations") or []) if d is not None))
    return " / ".join(str(d) for d in denoms)


def _discount_pct(voucher: dict, payment_method: str) -> float:
    keys = PAYMENT_METHOD_TO_DISCOUNT_KEYS.get(payment_method.lower(), [])
    discounts = voucher.get("discounts") or {}
    found = [discounts[k] for k in keys if discounts.get(k) is not None]
    if found:
        return max(found)
    return 0


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
        voucher_amount = float(_greedy_voucher_amount(
            price, fixed_denoms,
            stack_limit=voucher.get("stack_limit"),
            value_cap=voucher.get("value_cap"),
        ))
        remainder = round(price - voucher_amount, 2)

    txns_needed = math.ceil(voucher_amount / voucher["purchase_cap_per_txn"]) if voucher.get("purchase_cap_per_txn") else 1

    discount_amount = round(voucher_amount * discount_pct / 100, 2)
    effective_price = round(price - discount_amount, 2)
    return {
        "original_price": price,
        "voucher_amount": voucher_amount,
        "remainder_at_checkout": remainder,
        "is_custom": is_custom,
        "voucher_discount_pct": discount_pct,
        "voucher_discount_amount": discount_amount,
        "effective_price": effective_price,
        "payment_method": payment_method,
        "txns_needed": txns_needed,
        "voucher_platform": "Gyftr",
        "voucher_url": f"https://www.gyftr.com/{voucher['slug']}",
        "redemption_type": voucher.get("redemption_type", ""),
        "denominations": _denominations(voucher),
        "redemption_instructions": _clean_instructions(voucher.get("important_instructions_raw") or ""),
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
