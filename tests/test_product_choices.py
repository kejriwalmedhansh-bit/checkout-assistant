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
    assert "anything else" in labels, labels


def test_every_choice_is_a_real_offer_with_its_terms():
    for choice in voucher_check(domain="giva.co", price=4000)["product_choices"]:
        assert choice["has_voucher"] and choice["pct"] > 0, choice
        assert choice["voucher_url"], choice


def test_a_shop_with_one_kind_of_voucher_is_not_asked():
    for address in ("myntra.com", "pizzahut.co.in", "lifestylestores.com"):
        assert not voucher_check(domain=address, price=4000).get("product_choices"), address


def test_choices_come_without_a_price_too():
    assert len(_labels(voucher_check(domain="giva.co"))) >= 3
