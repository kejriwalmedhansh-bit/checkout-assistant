"""The owner's voucher-by-voucher review (data/voucher_choice_review.json).

Reviewed 2026-09-26 for every shop that asks "What are you buying?". The
extension (/voucher-check), website and WhatsApp bot (search) all read it,
so each rule is checked on both paths.

Run:  .venv/bin/python -m pytest tests/test_voucher_choice_review.py -q
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.routers.voucher_check import voucher_check  # noqa: E402
from src.services import search_service, voucher_service  # noqa: E402


def _labels(choices):
    return [c["choice_label"] for c in choices]


def test_every_reviewed_name_is_a_live_voucher():
    """A renamed or delisted voucher silently drops its review — catch it."""
    names = {c["name"] for c in voucher_service._online_cards()}
    reviewed = json.loads((ROOT / "data/voucher_choice_review.json").read_text())["cards"]
    assert not [n for n in reviewed if n not in names]


def test_the_same_voucher_on_two_sites_is_one_choice():
    # Porter on Gyftr and on Maximize: one kind, so nothing to ask.
    for domain in ("porter.in", "valorant.com", "nintendo.com"):
        assert not voucher_check(domain=domain, price=4000).get("product_choices"), domain


def test_no_shop_ever_shows_the_same_button_twice():
    keys = set()
    for card in voucher_service._online_cards():
        words = re.findall(r"[a-z0-9]+", card["name"].lower())
        keys.update(" ".join(words[:n]) for n in (1, 2) if len(words) >= n)
    for key in keys:
        labels = _labels(search_service._brand_voucher_choices(key))
        assert len(labels) == len(set(labels)), (key, labels)


def test_malabar_gold_coin_card_is_coins_only_and_the_weaker_jewellery_card_is_hidden():
    choices = search_service._brand_voucher_choices("malabar")
    assert _labels(choices) == ["Diamond & platinum", "Any jewellery", "Gold coins"]


def test_apollo_healing_is_not_offered_beside_the_pharmacy_card():
    assert _labels(search_service._brand_voucher_choices("apollo")) == ["Lab tests", "Medicines"]


def test_typing_a_shop_with_only_product_named_vouchers_finds_them():
    for shop in ("giva", "malabar", "candere"):
        assert len(search_service._brand_voucher_choices(shop)) >= 2, shop
    # ...but a product search that names the shop is still a product search.
    assert search_service._brand_voucher_choices("giva silver ring") == []


def test_a_shop_name_never_pulls_in_a_different_brand():
    assert "Timezone" not in [c["brand_name"] for c in search_service._brand_voucher_choices("times")]


def test_amazon_pay_finds_the_amazon_pay_card():
    voucher = search_service._match_brand_voucher("amazon pay")
    assert voucher and voucher["voucher_source"] == "maximize"


def test_each_ajio_site_gets_its_own_voucher_without_asking():
    luxe = voucher_check(domain="luxe.ajio.com", price=4000)
    plain = voucher_check(domain="www.ajio.com", price=4000)
    assert not luxe.get("product_choices") and "luxe" in luxe["brand_name"].lower()
    assert not plain.get("product_choices") and "luxe" not in plain["brand_name"].lower()


def test_times_prime_website_asks_which_membership():
    labels = _labels(voucher_check(domain="timesprime.com", price=1000).get("product_choices") or [])
    assert {"Power membership", "Lite membership"} <= set(labels), labels


def test_amazon_pay_card_is_not_limited_to_one_voucher_per_bill():
    """data/voucher_corrections.json: several Amazon Pay vouchers pay one bill,
    up to Rs 50,000 a month — survives a data refresh because it's applied on load."""
    from src.repositories import maximize_repository
    for product in maximize_repository.get_by_slug("amazon")["products"]:
        assert product["stack_limit"] is None and product["value_cap"] == 50000
