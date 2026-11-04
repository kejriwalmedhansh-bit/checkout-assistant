"""A jeweller's card is picked for what the shopper is buying.

Found 2026-11-04 on Kartik's demo: a ₹15,503 Tanishq gold coin was offered
Maximize's "Tanishq Diamond" card (4%, "studded jewellery only", terms exclude
gold coins) because it has the shortest name of the family, while the 1%
"Tanishq Gold Coin" card that actually pays for a coin was never looked at.

Run:  .venv/bin/python -m pytest tests/test_jewellery_cards.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import voucher_service as vs  # noqa: E402

_COIN = "Tanishq 1 gram 24 Karat Gold Coin with Lakshmi Ganesha Motif"


def _card(product_name: str, merchant: str = "Tanishq", price: float = 15503.0) -> str:
    deals = vs.build_deals([{"merchant": merchant, "price": price, "title": product_name, "match_type": "Listed"}],
                           product_name=product_name)
    assert deals, f"no card at all for {product_name!r}"
    return deals[0]["brand_name"]


def test_plural_and_singular_are_one_word_in_an_exclusion():
    assert vs._excluded_by_rules({"excludes": {"value": ["gold coins"]}}, None, _COIN) == "gold coins"


def test_a_gold_coin_gets_the_gold_coin_card_not_the_diamond_one():
    assert "Gold Coin" in _card(_COIN)


def test_plain_gold_jewellery_gets_neither_the_coin_nor_the_diamond_card():
    name = _card("Tanishq 22KT Gold Necklace with Ruby Drops")
    assert "Coin" not in name and "Diamond" not in name and "Studded" not in name


def test_studded_jewellery_keeps_the_diamond_card():
    assert "Diamond" in _card("Tanishq Diamond Solitaire Ring")


def test_with_no_product_in_hand_the_usual_best_match_stands():
    """The extension sees a shop and a total, not the cart; it asks the
    shopper instead (product_choices), so the lookup must not change."""
    assert vs._card_for_product("maximize", vs.maximize_repository.all_brands(), "Tanishq", "") is \
        vs.maximize_repository.get_by_merchant("Tanishq")
