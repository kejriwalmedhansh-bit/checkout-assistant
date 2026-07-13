"""Gyftr voucher business logic (ported from db/voucher_lookup.py).

Computes the effective price after applying a voucher's payment-method discount
and builds per-merchant voucher deals for a set of route candidates, honouring
category redemption restrictions.
"""
from __future__ import annotations

import math
import re

from ..category_classifier import classify_product, restriction_mentions_category
from ..repositories import voucher_repository

# Maps the caller-facing payment_method argument to the keys used in the
# discounts dict of gyftr_master.json.
PAYMENT_METHOD_TO_DISCOUNT_KEYS = {
    "card": ["Credit Card", "Debit Card"],
    "netbanking": ["Net Banking"],
    "upi": ["UPI"],
    "paytm_upi": ["UPI"],
    "amazon_pay": ["UPI"],
}


def _parse_denominations(voucher: dict) -> tuple[bool, list[int]]:
    """Returns (is_custom, sorted_fixed_denoms). is_custom=True when empty."""
    denoms = sorted(set(int(d) for d in (voucher.get("denominations") or []) if d is not None))
    if denoms:
        return False, denoms
    return True, []


def _greedy_voucher_amount(
    price: float,
    fixed_denoms: list[int],
    stack_limit: int | None = None,
    value_cap: float | None = None,
) -> int:
    """Largest sum of denominations (with repetition) within price, stack_limit, and value_cap."""
    remaining = int(price)
    total = 0
    count_used = 0
    for d in sorted(fixed_denoms, reverse=True):
        if stack_limit is not None:
            room_by_count = stack_limit - count_used
            if room_by_count <= 0:
                break
        else:
            room_by_count = float("inf")
        if value_cap is not None:
            room_by_value = value_cap - total
            if room_by_value <= 0:
                break
            room_by_value_count = room_by_value // d
        else:
            room_by_value_count = float("inf")
        count = min(remaining // d, room_by_count, room_by_value_count)
        total += count * d
        remaining -= count * d
        count_used += count
    return total


def _denominations_str(voucher: dict) -> str:
    if voucher.get("is_custom_denom"):
        lo, hi = voucher.get("custom_min"), voucher.get("custom_max")
        if lo and hi:
            return f"Custom (₹{lo}–₹{hi})"
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


_ALL_CAPS_HEADER_RE = re.compile(r"^[A-Z][A-Z\s&/-]+$")
_TRAILING_IMPORTANT_INSTRUCTIONS_RE = re.compile(r"important instructions\s*$", re.IGNORECASE)


def _clean_instructions(html: str) -> list[str]:
    """Strip HTML tags, cross-redemption mentions, and Gyftr page-navigation
    noise (all-caps tab labels like "TERMS & CONDITIONS" / "HOW TO USE", and
    "{Brand} Important Instructions" section headers) — the single source of
    truth for both web and WhatsApp, which both display this list as-is."""
    text = re.sub(r"<[^>]+>", "", html)
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _TRAILING_IMPORTANT_INSTRUCTIONS_RE.search(line) or _ALL_CAPS_HEADER_RE.match(line):
            continue
        lower = line.lower()
        if any(phrase in lower for phrase in _INSTRUCTION_EXCLUDE):
            continue
        result.append(line)
    return result


def calculate_effective_price(price: float, voucher: dict, payment_method: str = "upi") -> dict:
    discount_pct = _discount_pct(voucher, payment_method)
    custom_txns_needed = None

    if voucher.get("is_custom_denom"):
        # Real custom-amount range (e.g. Titan: any exact amount ₹100-10,000).
        # Always preferred over any fixed denominations the brand also lists —
        # it covers the purchase price more precisely. max_value is a per-voucher
        # cap; up to stack_limit vouchers can be combined in one bill.
        custom_max = voucher.get("custom_max") or 0
        stack_limit = voucher.get("stack_limit")
        if stack_limit is not None:
            total_cap = custom_max * stack_limit
        elif voucher.get("stack_limit_confidence") == "unlimited_stated":
            # No stated per-bill count cap — bounded by the purchase price
            # itself (or a real value_cap, if the brand's terms separately
            # state one), not an arbitrary vouchers-per-bill number.
            value_cap = voucher.get("value_cap")
            total_cap = min(price, value_cap) if value_cap else price
        else:
            # Unknown — conservative default of a single voucher.
            total_cap = custom_max
        voucher_amount = min(price, total_cap) if custom_max else 0.0
        remainder = round(price - voucher_amount, 2)
        is_custom = True
        custom_txns_needed = math.ceil(voucher_amount / custom_max) if custom_max and voucher_amount else 0
    else:
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

    if voucher.get("purchase_cap_per_txn"):
        txns_needed = math.ceil(voucher_amount / voucher["purchase_cap_per_txn"])
    elif custom_txns_needed is not None:
        txns_needed = custom_txns_needed
    else:
        txns_needed = 1

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
        "denominations": _denominations_str(voucher),
        "redemption_instructions": _clean_instructions(voucher.get("important_instructions_raw") or ""),
    }


def get_best_voucher_deal(merchant_name: str, price: float) -> dict | None:
    """UPI-rate voucher deal for merchant_name, or None if no voucher, 0% UPI
    discount, or price below the minimum denomination."""
    voucher = voucher_repository.get_by_merchant(merchant_name)
    if voucher is None:
        return None
    deal = calculate_effective_price(price, voucher, payment_method="upi")
    if not deal["voucher_discount_pct"]:
        return None
    if deal["voucher_amount"] == 0:
        return None
    return deal


def build_deals(results: list[dict], product_name: str = "") -> list[dict]:
    """Build per-merchant Gyftr voucher deals for the given route candidates.

    Ported from pipeline.step5_vouchers. Skips vouchers whose redemption
    restrictions exclude the product's category. UPI is the recommendation rate.
    """
    deals: list[dict] = []
    seen_merchants: set[str] = set()

    try:
        category = classify_product(product_name)
    except Exception:
        category = None

    for r in results:
        if r.get("match_type") not in ("Exact Match", "Listed"):
            continue
        merchant = r.get("merchant") or r.get("source") or ""
        price = r.get("price") or r.get("extracted_price") or 0
        merchant_key = merchant.lower()
        if not merchant or not price or merchant_key in seen_merchants:
            continue
        seen_merchants.add(merchant_key)

        voucher = voucher_repository.get_by_merchant(merchant)
        if voucher is None:
            continue

        try:
            if category is not None and restriction_mentions_category(
                voucher.get("redemption_restrictions", []), category
            ):
                continue
        except Exception:
            pass

        redemption_type_raw = voucher.get("redemption_type", "")
        offline_only = redemption_type_raw == "Offline"

        deal = get_best_voucher_deal(merchant, price)
        if deal is None:
            continue

        card_deal = calculate_effective_price(price, voucher, "card")

        deals.append({
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
                "txns_needed": deal.get("txns_needed", 1),
                "purchase_cap_per_txn": voucher.get("purchase_cap_per_txn"),
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

    return deals
