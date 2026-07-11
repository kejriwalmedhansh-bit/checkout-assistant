"""Cashback-card business logic (ported from the ROOT card_lookup.py).

Picks the single best direct-cashback card by actual saving after cap, honouring
the ₹200 / 3% minimum-saving floor and an annual-fee tiebreaker.

Bug #2 fix: when the route already includes a Gyftr voucher, only cards that
earn on Gyftr (earns_on_gyftr == True) qualify, and they earn at gyftr_rate.
"""
from __future__ import annotations

from ..repositories import card_repository

_MIN_SAVING_FLOOR = 200
_MIN_SAVING_PCT = 0.03

# CLAUDE.md rule #4: on an exact saving tie, SBI Cashback wins outright — it's
# the safer/preferred recommendation, not a fee-driven choice. Cards outside
# this named rule fall back to the lower-annual-fee tiebreak.
_TIE_BREAK_PRIORITY = ("SBI Cashback", "BOB Cashback")


def _tie_break_rank(card_name: str) -> int:
    return (
        _TIE_BREAK_PRIORITY.index(card_name)
        if card_name in _TIE_BREAK_PRIORITY
        else len(_TIE_BREAK_PRIORITY)
    )


def get_card_rate(card_name: str, merchant: str, has_voucher: bool = False) -> float:
    """Applicable cashback rate for a card at a given merchant.

    When the route has a Gyftr voucher, the earn rate is the card's gyftr_rate
    (0 for cards that don't earn on Gyftr), not the merchant/online rate.
    """
    card = card_repository.get(card_name)
    if not card:
        return 0.0
    if has_voucher:
        # Only cards that earn on Gyftr contribute on a voucher route.
        if not card.get("earns_on_gyftr"):
            return 0.0
        return card.get("gyftr_rate", 0.0)
    merchant_lower = merchant.lower()
    overrides = card.get("merchant_overrides", {})
    for key, rate in overrides.items():
        if key in merchant_lower:
            return rate
    return card.get("rate_online", 0.0)


def get_actual_saving(
    card_name: str, merchant: str, purchase_amount: float, has_voucher: bool = False
) -> float:
    """Actual saving after applying the cap."""
    card = card_repository.get(card_name)
    if not card:
        return 0.0
    rate = get_card_rate(card_name, merchant, has_voucher=has_voucher)
    raw_saving = purchase_amount * rate
    cap = card.get("cap_amount", 0)
    # TODO(bug #4): cap_amount periods are not normalized — a monthly cap is
    # compared raw against a quarterly cap when selecting the best card.
    return min(raw_saving, cap)


def best_card_for_purchase(
    merchant: str, purchase_amount: float, has_voucher: bool = False
) -> dict | None:
    """Best cashback card for the purchase, or None if none clears the minimum
    saving threshold. Tiebreaker: named priority (SBI Cashback beats BOB
    Cashback), else lower annual fee wins."""
    min_threshold = max(_MIN_SAVING_FLOOR, purchase_amount * _MIN_SAVING_PCT)

    best = None
    for card_name, card_data in card_repository.all_cards().items():
        saving = round(get_actual_saving(card_name, merchant, purchase_amount, has_voucher=has_voucher), 2)
        if saving < min_threshold:
            continue
        candidate = {
            "card_name": card_name,
            "rate": get_card_rate(card_name, merchant, has_voucher=has_voucher),
            "actual_saving": saving,
            "cap_amount": card_data["cap_amount"],
            "cap_period": card_data["cap_period"],
            "annual_fee": card_data["annual_fee"],
            "apply_url": card_data.get("apply_url"),
        }
        if best is None or saving > best["actual_saving"]:
            best = candidate
        elif saving == best["actual_saving"]:
            if _tie_break_rank(card_name) < _tie_break_rank(best["card_name"]):
                best = candidate
            elif (
                _tie_break_rank(card_name) == _tie_break_rank(best["card_name"])
                and card_data["annual_fee"] < best["annual_fee"]
            ):
                best = candidate

    return best
