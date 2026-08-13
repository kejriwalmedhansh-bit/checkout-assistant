"""Cashback-card business logic (ported from the ROOT card_lookup.py).

Picks the single best direct-cashback card by actual saving after cap, honouring
the ₹200 / 3% minimum-saving floor and an annual-fee tiebreaker.

Bug #2 fix: when the route already includes a Gyftr voucher, only cards that
earn on Gyftr (earns_on_gyftr == True) qualify, and they earn at gyftr_rate.
"""
from __future__ import annotations

from ..repositories import card_repository

_MIN_SAVING_FLOOR = 0
_MIN_SAVING_PCT = 0

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


def _merchant_override(card: dict, merchant: str) -> dict | None:
    """The merchant_overrides entry matching this merchant, or None. Each
    entry is a dict with at least a "rate" key and, for categories with their
    own real cap (e.g. Flipkart Axis's Flipkart/ClearTrip/Myntra rates),
    "cap_amount"/"cap_period" too."""
    merchant_lower = merchant.lower()
    for key, entry in card.get("merchant_overrides", {}).items():
        if key in merchant_lower:
            return entry
    return None


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
    override = _merchant_override(card, merchant)
    if override is not None:
        return override["rate"]
    return card.get("rate_online", 0.0)


def get_card_cap(card_name: str, merchant: str, has_voucher: bool = False) -> tuple[float | None, str | None]:
    """The (cap_amount, cap_period) that applies to this card's earning at this
    merchant, or (None, None) if that earning is genuinely uncapped. A
    merchant category with its own cap (e.g. Flipkart Axis's Flipkart/
    ClearTrip/Myntra rates) takes priority over the card-level cap; cards
    without any per-category caps (SBI, BOB) always fall back to the
    card-level cap_amount/cap_period."""
    card = card_repository.get(card_name)
    if not card:
        return (None, None)
    if not has_voucher:
        override = _merchant_override(card, merchant)
        if override is not None and "cap_amount" in override:
            return (override["cap_amount"], override.get("cap_period"))
    return (card.get("cap_amount"), card.get("cap_period"))


def get_actual_saving(
    card_name: str, merchant: str, purchase_amount: float, has_voucher: bool = False
) -> float:
    """Actual saving after applying the cap (uncapped if the applicable cap is None)."""
    card = card_repository.get(card_name)
    if not card:
        return 0.0
    rate = get_card_rate(card_name, merchant, has_voucher=has_voucher)
    raw_saving = purchase_amount * rate
    cap, _ = get_card_cap(card_name, merchant, has_voucher=has_voucher)
    if cap is None:
        return raw_saving
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
        cap_amount, cap_period = get_card_cap(card_name, merchant, has_voucher=has_voucher)
        candidate = {
            "card_name": card_name,
            "rate": get_card_rate(card_name, merchant, has_voucher=has_voucher),
            "actual_saving": saving,
            "cap_amount": cap_amount,
            "cap_period": cap_period,
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


def get_voucher_cashback_rate(card_name: str, voucher_source: str) -> float:
    """Cashback rate this card earns when funding a voucher purchase from the
    given source ("gyftr" or "maximize"), or 0 if the card doesn't earn on
    that source at all."""
    card = card_repository.get(card_name)
    if not card:
        return 0.0
    if voucher_source == "maximize":
        if not card.get("earns_on_maximize"):
            return 0.0
        return card.get("maximize_rate", 0.0)
    if not card.get("earns_on_gyftr"):
        return 0.0
    return card.get("gyftr_rate", 0.0)


def best_card_for_voucher_purchase(
    merchant: str, card_rate_price: float, recommended_price: float, voucher_source: str
) -> dict | None:
    """Best cashback card for funding this voucher purchase directly with the
    card (instead of Dealo's recommended, card-free route), comparing the
    whole alternative honestly.

    `card_rate_price` is what the voucher actually costs at this card's own
    payment-method rate (already lower than the recommended UPI rate — see
    calculate_effective_price's "card" path) — cashback is earned on top of
    that price, never on the UPI-rate price the customer wouldn't actually
    have paid by using a card. Only qualifies if the combined total (card-rate
    price minus cashback) genuinely beats `recommended_price` by the usual
    ₹200/3% floor; otherwise returns None, same as the no-voucher path — no
    card is ever shown as a reason to abandon the card-free recommendation."""
    min_threshold = max(_MIN_SAVING_FLOOR, recommended_price * _MIN_SAVING_PCT)

    best = None
    for card_name, card_data in card_repository.all_cards().items():
        rate = get_voucher_cashback_rate(card_name, voucher_source)
        if not rate:
            continue
        raw_cashback = round(card_rate_price * rate, 2)
        cap_amount = card_data.get("cap_amount")
        cashback = raw_cashback if cap_amount is None else min(raw_cashback, cap_amount)
        card_path_total = round(card_rate_price - cashback, 2)
        saving = round(recommended_price - card_path_total, 2)
        if saving < min_threshold:
            continue
        candidate = {
            "card_name": card_name,
            "rate": rate,
            "actual_saving": saving,
            "cap_amount": cap_amount,
            "cap_period": card_data.get("cap_period"),
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


def _route_card_context(route) -> tuple[float, bool]:
    """(purchase_amount, has_voucher) for the price the shopper would actually
    pay by card on this route — the voucher's card-rate price when a voucher
    is involved (never the UPI-rate price nobody paying by card would get),
    otherwise the route's own final cost."""
    if route.voucher is not None:
        return route.voucher.card.effective_price, True
    return route.final_cost, False


def eligible_cards_for_route(route) -> list[str]:
    """Card names that earn something (cashback rate > 0) on this specific
    route — used to only offer cards in the picker that would actually pay
    out here, rather than always listing every card."""
    _, has_voucher = _route_card_context(route)
    return [
        card_name
        for card_name in card_repository.all_cards()
        if get_card_rate(card_name, route.merchant, has_voucher=has_voucher) > 0
    ]


def get_card_quote(route, card_name: str) -> dict | None:
    """Voucher discount + cashback for one user-picked card on this route —
    no "best card" comparison, no ranking, just this card's real numbers.
    Returns None if the card doesn't earn anything here (shouldn't normally
    be called for a card outside `eligible_cards_for_route`)."""
    purchase_amount, has_voucher = _route_card_context(route)
    rate = get_card_rate(card_name, route.merchant, has_voucher=has_voucher)
    if rate <= 0:
        return None
    cashback = round(get_actual_saving(card_name, route.merchant, purchase_amount, has_voucher=has_voucher), 2)
    card_data = card_repository.get(card_name) or {}
    voucher_discount = round(route.voucher.card.saving, 2) if route.voucher is not None else None
    return {
        "card_name": card_name,
        "voucher_discount": voucher_discount,
        "cashback": cashback,
        "apply_url": card_data.get("apply_url"),
    }
