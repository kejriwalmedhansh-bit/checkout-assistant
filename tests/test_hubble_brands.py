"""Which Hubble voucher a results-page shop name buys (production catalogue).

A wrong match here sells a voucher for the wrong shop, so the rule is
strict: exact title, hand-checked alias, or the shop's own "-Luxe Gift
Card" title. Anything else is "not sold by Hubble" and the shopper keeps
today's Gyftr/Maximize/BuyHatke route.

Run:  .venv/bin/python -m pytest tests/test_hubble_brands.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import hubble_service as hs  # noqa: E402

PROD = Path(__file__).resolve().parents[1] / "data" / "hubble_catalogue.json"


@pytest.fixture(autouse=True)
def _production_catalogue(monkeypatch):
    monkeypatch.setattr(hs, "_catalogue_path", lambda: PROD)


def _name(merchant, in_store=False):
    found = hs.brand_for(merchant, in_store)
    return found["name"] if found else None


@pytest.mark.parametrize("merchant,expected", [
    ("Amazon", "Amazon shopping"),          # alias: the shopping voucher beats Amazon Pay
    ("Amazon.in", "Amazon shopping"),       # domain
    ("AJIO.com", "AJIO"),
    ("luxe.ajio.com", "AJIO LUXE"),
    ("Nykaa", "Nykaa"),                     # never "Nykaa LUXE"
    ("Nykaa Luxe", "Nykaa LUXE"),
    ("PVR Cinemas", "PVR"),
    ("Domino's Pizza", "Dominos"),          # never "Dominos Fixed"
    ("Uber", "Uber."),
    ("firstcry.com", "Firstcry"),
    ("Liberty", "Liberty Online"),          # alias lists two; only one works online
])
def test_online_matches(merchant, expected):
    assert _name(merchant) == expected


@pytest.mark.parametrize("merchant,expected", [
    ("Westside (in-store)", "Westside"),
    ("Liberty", "Liberty Shoes"),
    ("Hugo Boss", "Hugo Boss-Luxe Gift Card"),
    ("Hamleys India", "Hamleys-Luxe Gift Card"),  # generic suffix + Luxe title
    ("Titan Eye+", "Titan Eye+"),
])
def test_in_store_matches(merchant, expected):
    assert _name(merchant, in_store=True) == expected


@pytest.mark.parametrize("merchant,in_store", [
    ("Hugo Boss", False),          # Hubble's card is in-store only
    ("Hamleys India", False),      # same: Luxe card is in-store only
    ("Reliance Digital", False),   # Hubble's voucher is in-store only (asked Yash for online)
    ("Tata CLiQ Jewellery", False),  # sub-brand with its own terms: no guess
    ("Lee", False),                # must not become "Moments by The Leela"
    ("Apollo Pharmacy", False),    # Hubble's "Apollo" isn't confirmed to be the pharmacy
    ("", False),
])
def test_no_guessing(merchant, in_store):
    assert _name(merchant, in_store) is None


def test_shop_key_strips_domains_and_suffixes():
    assert hs.shop_key("https://www.Amazon.in/dp/123") == "amazon"
    assert hs.shop_key("Westside (in-store)") == "westside"
    assert hs.shop_key("Hamleys India") == "hamleys"


# A partner listing's name often carries words about the listing, not the
# shop. Found 4 Nov 2026: PVR showed no Dealo voucher because the cheapest
# listing was "PVR Cinemas - GYFTR". 23 listings across the three partners
# missed the same way.
@pytest.mark.parametrize("listing,expected", [
    ("PVR Cinemas - GYFTR", "PVR"),
    ("Zomato Gift Card", "Zomato"),
    ("Swiggy Money Voucher", "Swiggy"),
    ("Swiggy Money", "Swiggy"),
    ("Swiggy Instamart", "Swiggy"),  # owner 2026-11-12: Instamart vouchers are Swiggy credit too
    ("Amazon Shopping Voucher", "Amazon shopping"),
    ("Bigbasket (Custom)", "BigBasket"),
    ("Decathlon - Fixed", "Decathlon"),
    ("Yatra Hotel Gift Card", "Yatra Hotels & Holidays"),
    ("Adventra", "Adventra Sports"),      # alias: adventrasports.com
    ("Naturals", "Naturals Salons"),      # alias
])
def test_listing_decoration_is_ignored(listing, expected):
    assert _name(listing) == expected


@pytest.mark.parametrize("listing,expected", [
    ("Pantaloons (In Store, 4 Hr Wait)", "Pantaloons"),
    ("Liberty (In Store, 3 Day Wait)", "Liberty Shoes"),
    ("Max Fashion (Offline)", "Max Fashion"),
])
def test_listing_decoration_is_ignored_in_store(listing, expected):
    assert _name(listing, in_store=True) == expected


def test_decoration_never_breaks_a_title_that_matches_as_given():
    # "Hugo Boss-Luxe Gift Card" is a Hubble title of its own; stripping
    # "Gift Card" first would leave "hugobossluxe" and lose it.
    assert _name("Hugo Boss-Luxe Gift Card", in_store=True) == "Hugo Boss-Luxe Gift Card"
    assert _name("BGMI UC Official Voucher") == "BGMI UC OFFICIAL VOUCHER"


# --- Buy links -------------------------------------------------------------
# Every surface hands the shopper to getdealo.in/buy/<slug>. The slug must
# name exactly one catalogue voucher, for every voucher Hubble sells.


def test_buy_slug_shape():
    assert hs.buy_slug("AJIO Luxe") == "ajio-luxe"
    assert hs.buy_slug("DOMINO'S") == "domino-s"
    assert hs.buy_slug("  Myntra ") == "myntra"


def test_buy_link_carries_amount_and_source(monkeypatch):
    link = hs.buy_link("Myntra", 2000, "wa")
    assert link.endswith("/buy/myntra?amount=2000&src=wa")
    assert hs.buy_link("Myntra").endswith("/buy/myntra")


def test_every_catalogue_voucher_has_a_working_slug():
    import json
    brands = json.loads(PROD.read_text())
    broken = []
    for b in brands:
        found = hs.brand_by_slug(hs.buy_slug(b["name"]))
        if not found or hs.normalize(found["name"]) != hs.normalize(b["name"]):
            broken.append(b["name"])
    # Titles that collide once punctuation is dropped resolve to the online
    # one; a tie with no online entry answers nothing rather than guessing.
    assert broken == [], broken
