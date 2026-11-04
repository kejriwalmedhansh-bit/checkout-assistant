"""A Dealo link to a Maximize card must open THAT card.

Owner's test, 2026-11-04: the Tanishq Gold Jewellery link (card 1278) opened
Maximize's default Tanishq card, the Studded one, because the catalogue link
redirects with the card number under a name the page ignores.

Run:  .venv/bin/python -m pytest tests/test_maximize_card_links.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.repositories import maximize_repository as mr  # noqa: E402
from src.services import voucher_service as vs  # noqa: E402


def test_a_catalogue_link_is_written_the_way_maximize_links_the_card():
    assert mr.card_link("https://www.maximize.money/gift-cards/Tanishq/1278") == \
        "https://www.maximize.money/savemax/Tanishq?flow=GIFTCARD&brandId=33&giftcardId=1278"
    # One slug, two Maximize brands: the number belongs to the card.
    assert "brandId=16&giftcardId=470" in mr.card_link("https://www.maximize.money/gift-cards/Yatra/470")
    assert "brandId=227&giftcardId=1317" in mr.card_link("https://www.maximize.money/gift-cards/Yatra/1317")


def test_other_links_pass_through_unchanged():
    assert mr.card_link("https://www.maximize.money/gift-cards/Nobody/999999") == "https://www.maximize.money/gift-cards/Nobody/999999"
    assert mr.card_link("https://buyhatke.com/gift-cards/ajio-gift-card") == "https://buyhatke.com/gift-cards/ajio-gift-card"
    assert mr.card_link(None) is None


def test_the_deal_carries_the_card_link():
    deals = vs.build_deals([{"merchant": "Tanishq", "price": 50000.0, "title": "x", "match_type": "Listed"}],
                           product_name="Tanishq 22KT Gold Necklace")
    assert deals and deals[0]["brand_name"] == "Tanishq Gold Jewellery"
    assert deals[0]["voucher_url"].endswith("brandId=33&giftcardId=1278")
