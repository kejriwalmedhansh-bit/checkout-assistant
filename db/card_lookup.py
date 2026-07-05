import json
import os

_CARDS_PATH = os.path.join(os.path.dirname(__file__), "cashback_cards.json")

with open(_CARDS_PATH) as f:
    CASHBACK_CARDS = json.load(f)


def get_card_rate(card_name: str, merchant: str) -> float:
    """Return the applicable cashback rate for a card at a given merchant."""
    card = CASHBACK_CARDS.get(card_name)
    if not card:
        return 0.0
    merchant_lower = merchant.lower()
    overrides = card.get("merchant_overrides", {})
    for key, rate in overrides.items():
        if key in merchant_lower:
            return rate
    return card.get("rate_online", 0.0)


def get_actual_saving(card_name: str, merchant: str, purchase_amount: float) -> float:
    """
    Return actual saving after applying cap.
    For Gyftr-routed purchases, uses gyftr_rate if earns_on_gyftr is True.
    purchase_amount is the Gyftr voucher cost (already discounted by Gyftr).
    """
    card = CASHBACK_CARDS.get(card_name)
    if not card:
        return 0.0

    rate = get_card_rate(card_name, merchant)
    raw_saving = purchase_amount * rate
    cap = card.get("cap_amount", 0)
    return min(raw_saving, cap)


def best_card_for_purchase(merchant: str, purchase_amount: float) -> dict | None:
    """
    Return the best cashback card for a given merchant and purchase amount.
    Returns dict with card_name, rate, actual_saving, or None if no card adds value.
    """
    best = None
    for card_name in CASHBACK_CARDS:
        saving = get_actual_saving(card_name, merchant, purchase_amount)
        if saving > 0 and (best is None or saving > best["actual_saving"]):
            best = {
                "card_name": card_name,
                "rate": get_card_rate(card_name, merchant),
                "actual_saving": round(saving, 2),
                "cap_amount": CASHBACK_CARDS[card_name]["cap_amount"],
                "cap_period": CASHBACK_CARDS[card_name]["cap_period"],
            }
    return best
