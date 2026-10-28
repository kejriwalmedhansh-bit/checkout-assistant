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
    ("Swiggy Instamart", False),   # not the same voucher as Swiggy food
    ("Apollo Pharmacy", False),    # Hubble's "Apollo" isn't confirmed to be the pharmacy
    ("", False),
])
def test_no_guessing(merchant, in_store):
    assert _name(merchant, in_store) is None


def test_shop_key_strips_domains_and_suffixes():
    assert hs.shop_key("https://www.Amazon.in/dp/123") == "amazon"
    assert hs.shop_key("Westside (in-store)") == "westside"
    assert hs.shop_key("Hamleys India") == "hamleys"
