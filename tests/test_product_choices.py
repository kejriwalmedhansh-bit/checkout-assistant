"""Shops that sell a different voucher for each kind of product.

The extension sees the shop and the order total, not the cart. Where a shop's
vouchers each pay for different things, Dealo asks the shopper what they are
buying instead of guessing (product decision 2026-09-17). Found when giva.co
offered its silver-coin card to anyone, and makemytrip.com could offer a 14%
hotels-only card at a flight checkout.

Run:  .venv/bin/python -m pytest tests/test_product_choices.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.routers.voucher_check import voucher_check  # noqa: E402


def _labels(answer):
    return [c["choice_label"].lower() for c in answer.get("product_choices") or []]


def test_giva_asks_which_kind_of_jewellery():
    answer = voucher_check(domain="giva.co", price=4000)
    labels = _labels(answer)
    assert len(labels) >= 3, labels
    assert any("silver jewellery" in l for l in labels), labels
    assert any("coin" in l for l in labels), labels


def test_makemytrip_separates_hotels_from_everything_else():
    labels = _labels(voucher_check(domain="makemytrip.com", price=12500))
    assert any("hotel" in l for l in labels), labels
    # The general card is named for what it mostly buys ("Flights & anything else").
    assert any("anything else" in l for l in labels), labels


def test_every_choice_is_a_real_offer_with_its_terms():
    for choice in voucher_check(domain="giva.co", price=4000)["product_choices"]:
        assert choice["has_voucher"] and choice["pct"] > 0, choice
        assert choice["voucher_url"], choice


def test_a_shop_with_one_kind_of_voucher_is_not_asked():
    for address in ("myntra.com", "pizzahut.co.in", "lifestylestores.com"):
        assert not voucher_check(domain=address, price=4000).get("product_choices"), address


def test_choices_come_without_a_price_too():
    assert len(_labels(voucher_check(domain="giva.co"))) >= 3


def test_yatra_picks_the_flight_card_that_saves_most_on_this_fare():
    """Yatra's flight card comes at ₹500 (85%), ₹1,500 (35%) and ₹2,000 (25%),
    one per bill. On a ₹4,000 fare the ₹1,500 card saves most, not the 85%."""
    choices = voucher_check(domain="yatra.com", price=4000)["product_choices"]
    flights = next(c for c in choices if "flight" in c["choice_label"].lower())
    assert flights["brand_name"] == "Yatra - 1500" and flights["saving"] == 525, flights
    assert "anything else" in _labels({"product_choices": choices})


def test_air_india_add_ons_count_because_their_terms_say_airindia_com():
    """Gyftr labels the Add-ons card offline; its terms say airindia.com."""
    import json
    import pytest
    offers = json.loads((Path(__file__).resolve().parents[1] / "data" / "voucher_offers.json").read_text())
    if not offers.get("gyftr:air-india-add-ons", {}).get("recommendable"):
        # Out of stock on Gyftr (no cards listed at the 2026-09-18 refresh) —
        # nothing to offer, so nothing to check until it is back on sale.
        pytest.skip("Air India Add-ons has no cards on sale at the last refresh")
    assert any("add-on" in l for l in _labels(voucher_check(domain="airindia.com", price=4000)))


def test_a_card_whose_dates_have_passed_is_never_a_choice():
    """Fly Rajasthan only covers journeys from May to July 2026."""
    names = [c["brand_name"].lower() for c in voucher_check(domain="airindia.com", price=4000)["product_choices"]]
    assert not any("rajasthan" in n for n in names), names


def test_goibibo_still_asks_when_the_general_card_cannot_price_this_order():
    labels = _labels(voucher_check(domain="goibibo.com", price=4000))
    assert any("hotel" in l for l in labels) and any("anything else" in l for l in labels), labels
