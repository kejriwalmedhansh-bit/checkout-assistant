"""Maximize as the second seller behind Dealo's Buy button (offline).

Shapes copied from Maximize's sandbox on 30 Oct 2026 (gift-cards-list and
gift-cards-details). A wrong match sells a voucher for the wrong shop, so
matching is exact-or-nothing; a wrong kind (in-store card for an online
order) is refused the same way.

Run:  .venv/bin/python -m pytest tests/test_maximize_service.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import maximize_service as mx  # noqa: E402

CARDS = [
    {"id": "AJIO9IUC0NMGE", "giftCardName": "Ajio", "discount": 7.65, "stock": True},
    {"id": "5BE9F3D3600AB502", "giftCardName": "Bata", "discount": 4.65, "stock": True},
    {"id": "DOM3CCBX90X1V", "giftCardName": "Domino's Pizza", "discount": 9.65, "stock": True},
    {"id": "DOM3CCBX90X1V", "giftCardName": "Domino's Pizza", "discount": 9.65, "stock": True},  # listed twice
    {"id": "NYK1", "giftCardName": "Nykaa E Gift Card", "discount": 4.65, "stock": True},
    {"id": "NYKF", "giftCardName": "Nykaa Fashion E-Gift Card", "discount": 4.65, "stock": True},
    {"id": "ZEP", "giftCardName": "Zepto E Gift Card", "discount": 4.65, "stock": False},
]

AJIO = {
    "denominationType": "range", "fixedDenomination": "100,200,250,500,1000", "minAmount": 100, "maxAmount": 1000,
    "maxAllowedQuantity": 4, "discount": 8,
    "paymentMethods": [{"name": "UPI", "instrument": "default", "discount": 7.65, "surcharge": 0},
                       {"name": "Credit Card", "instrument": "credit_card", "discount": 5.4, "surcharge": 0}],
    "importantInfo": [{"title": "Where to Redeem?", "subtext": "Works on Ajio website and app"}],
}
DOMINOS = {
    "denominationType": "fixed", "fixedDenomination": "150,300,1000", "maxAllowedQuantity": 4, "discount": 10,
    "paymentMethods": [{"name": "UPI", "instrument": "default", "discount": 9.65, "surcharge": 0}],
    "importantInfo": [{"title": "Where to Redeem?", "subtext": "Redeem Online on website / app"}],
}
BATA = {"denominationType": "fixed", "fixedDenomination": "150,300,1000", "maxAllowedQuantity": 4, "discount": 5,
        "paymentMethods": [{"name": "UPI", "instrument": "default", "discount": 4.65, "surcharge": 0}], "importantInfo": []}


def test_card_titles_reduce_to_the_shop():
    assert mx.card_key("Nykaa Fashion E-Gift Card") == "nykaafashion"
    assert mx.card_key("Nykaa E Gift Card") == "nykaa"
    assert mx.card_key("Zepto E Gift Card") == "zepto"
    assert mx.card_key("Ajio") == "ajio"


def test_results_page_names_find_one_card():
    assert mx.card_for("AJIO.com", CARDS)["id"] == "AJIO9IUC0NMGE"
    assert mx.card_for("Nykaa", CARDS)["id"] == "NYK1"            # never Nykaa Fashion
    assert mx.card_for("Nykaa Fashion", CARDS)["id"] == "NYKF"
    assert mx.card_for("Domino's", CARDS)["id"] == "DOM3CCBX90X1V"  # alias; the duplicate listing is one card
    assert mx.card_for("Zepto", CARDS) is None                     # out of stock
    assert mx.card_for("Myntra", CARDS) is None


def test_the_rate_is_the_upi_rate_not_the_headline():
    assert mx.upi_pct(CARDS[0], AJIO) == 7.65      # details say 8, UPI pays 7.65
    assert mx.upi_pct(CARDS[1], None) == 4.65      # no details: the list's figure


def test_where_it_works_comes_from_the_card_or_dealos_own_scrape():
    assert mx.works(CARDS[0], AJIO) == {"ONLINE"}
    assert mx.works(CARDS[2], DOMINOS) == {"ONLINE"}
    # Bata's card says nothing; Dealo's Maximize scrape knows it is in-store only
    assert mx.works(CARDS[1], BATA) == {"OFFLINE"}


def test_splits_follow_their_frame_rules():
    # range card: one voucher for the bill, or several of the top amount
    assert mx._split(AJIO, 650, 7.65) == [(650, 1)]
    assert mx._split(AJIO, 2799, 7.65, 4) == [(1000, 2)]
    assert mx._split(AJIO, 2799, 7.65, 1) == [(1000, 1)]
    assert mx._split(AJIO, 60, 7.65) is None                      # below the minimum
    # fixed cards: one denomination, as many as the shop takes on one bill
    assert mx._split(DOMINOS, 600, 9.65, 4) == [(150, 4)]
    assert mx._split(DOMINOS, 1250, 9.65, 4) == [(300, 4)]
    assert mx._split(DOMINOS, 1250, 9.65, 1) == [(1000, 1)]
    assert mx._split(DOMINOS, 100, 9.65, 4) is None


def test_a_shop_that_wont_club_cards_gets_one_voucher():
    # Domino's card says "Multiple cards can't be clubbed": one voucher only
    dominos = {**DOMINOS, "importantInfo": DOMINOS["importantInfo"] + [
        {"title": "Can the cards be clubbed?", "subtext": "Multiple cards can''t be clubbed"}]}
    assert mx.vouchers_per_bill(CARDS[2], dominos) == 1
    # AJIO's card says several cards in one purchase: their frame's limit
    ajio = {**AJIO, "importantInfo": AJIO["importantInfo"] + [
        {"title": "Can the cards be clubbed?", "subtext": "Use several gift cards in one purchase"}]}
    assert mx.vouchers_per_bill(CARDS[0], ajio) == 4
    # Bata's card says nothing; Dealo's scrape says four per bill
    assert mx.vouchers_per_bill(CARDS[1], BATA) == 4
    # a card nobody knows about: one voucher, the safe answer
    assert mx.vouchers_per_bill({"giftCardName": "Unknown Shop"}, {"maxAllowedQuantity": 4}) == 1


def test_offer_shape_matches_hubbles():
    offer = mx._offer(CARDS[0], AJIO, [(1000, 2)], 7.65, 2799, False)
    assert offer["seller"] == "maximize"
    assert offer["voucher_total"] == 2000 and offer["rest_at_shop"] == 799
    assert offer["you_pay"] == 1847.0 and offer["you_save"] == 153.0
    assert offer["brand_name"] == "Ajio"
    for key in ("brand_id", "denominations", "orders", "discount_pct", "in_store", "add_voucher_url"):
        assert key in offer
