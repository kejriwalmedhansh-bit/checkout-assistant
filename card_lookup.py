import json
import os

_CARDS_PATH = os.path.join(os.path.dirname(__file__), "cashback_cards.json")

with open(_CARDS_PATH) as f:
    CASHBACK_CARDS = json.load(f)

_MIN_SAVING_FLOOR = 200
_MIN_SAVING_PCT = 0.03


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
    """Return actual saving after applying cap."""
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
    Returns None if no card beats the minimum saving threshold.
    Tiebreaker: lower annual fee wins.
    """
    min_threshold = max(_MIN_SAVING_FLOOR, purchase_amount * _MIN_SAVING_PCT)

    best = None
    for card_name, card_data in CASHBACK_CARDS.items():
        saving = get_actual_saving(card_name, merchant, purchase_amount)
        if saving < min_threshold:
            continue
        if best is None or saving > best["actual_saving"]:
            best = {
                "card_name": card_name,
                "rate": get_card_rate(card_name, merchant),
                "actual_saving": round(saving, 2),
                "cap_amount": card_data["cap_amount"],
                "cap_period": card_data["cap_period"],
                "annual_fee": card_data["annual_fee"],
            }
        elif saving == best["actual_saving"] and card_data["annual_fee"] < best["annual_fee"]:
            best = {
                "card_name": card_name,
                "rate": get_card_rate(card_name, merchant),
                "actual_saving": round(saving, 2),
                "cap_amount": card_data["cap_amount"],
                "cap_period": card_data["cap_period"],
                "annual_fee": card_data["annual_fee"],
            }

    return best
