"""The Dealo voucher card's icon row, 'can't pay for' box and how-to steps,
all read from Hubble's own terms (hubble_service.card_details)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import hubble_service as h  # noqa: E402


def product(conditions, ways=(("ONLINE", ["Open the app", "Add the card"]),)):
    return {"voucherProductMetadata": {
        "conditions": list(conditions),
        "howToUseSteps": [{"retailMode": m, "howToUseHints": {"hints": hints}} for m, hints in ways],
    }}


MYNTRA = [
    "Comes with 1 year validity",
    "All brand funded offers can be clubbed during purchase",
    "If the order value exceeds the Gift Card amount, the balance must be paid by Credit Card/Debit Card/Internet Banking/. "
    "The Cash on Delivery payment option cannot be used to pay the balance amount",
    "Gift Cards are not applicable on the purchase of items from restricted categories including Gold & Silver, "
    "Gold & Silver coins, and Fine Jewellery",
    "Gift cards are multi-use. So you can use a gift card multiple times as long as it carries a balance.",
]


def titles(card):
    return [(f["title"], f["tone"]) for f in card["facts"]]


def test_myntra_reads_like_the_mockup():
    card = h.card_details(product(MYNTRA), "Myntra", in_store=False)
    assert titles(card) == [("Online", "info"), ("Reuse", "yes"), ("Offers", "yes"), ("1 year", "info")]
    assert [c["label"] for c in card["cant"]] == ["Jewellery", "Gold & silver", "Cash on delivery"]
    assert card["steps"] == ["Open the app", "Add the card"]


def test_a_pick_whose_sentence_hubble_dropped_is_not_shown():
    card = h.card_details(product(MYNTRA[:2]), "Myntra", in_store=False)
    assert card["cant"] == []


def test_no_other_offers_is_a_no_even_though_it_reads_like_a_yes():
    card = h.card_details(product(["No other offers can be clubbed while purchasing with this virtual card"]), "X", False)
    assert ("No offers", "no") in titles(card)


def test_a_mixed_reuse_sentence_says_nothing():
    card = h.card_details(product(["Can only be used once offline; can be used multiple times online"]), "X", False)
    assert [t for t, _ in titles(card)] == ["Online"]


def test_one_use_and_no_refund():
    card = h.card_details(product(["Comes with 6 months validity", "This is a one-time use gift card",
                                   "Gift cards, once purchased, cannot be cancelled or refunded"]), "X", False)
    assert titles(card) == [("Online", "info"), ("One use", "no"), ("6 months", "info"), ("No refund", "no")]


def test_in_store_card_uses_in_store_steps():
    p = product(["Comes with 1 year validity"], ways=(("ONLINE", ["web step"]), ("OFFLINE", ["Show the code at the till"])))
    card = h.card_details(p, "X", in_store=True)
    assert card["facts"][0]["title"] == "In store"
    assert card["steps"] == ["Show the code at the till"]
