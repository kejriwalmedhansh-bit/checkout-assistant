"""Which Hubble voucher a results-page shop name buys (production catalogue).

A wrong match here sells a voucher for the wrong shop, so the rule is
strict: exact title, hand-checked alias, or the shop's own "-Luxe Gift
Card" title. Anything else is "not sold by Hubble" and the shopper keeps
today's Gyftr/Maximize/BuyHatke route.

Run:  .venv/bin/python -m pytest tests/test_hubble_brands.py -q
"""
from __future__ import annotations

import json
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
    ("Decathlon Sports India", "Decathlon"),  # Google Shopping's name for decathlon.in
    ("Apollo Pharmacy", "Apollo"),            # Hubble terms: Apollo Pharmacy + Apollo 24|7
    ("JioMart Electronics", "Jio Mart"),
    ("The Body Shop", "The Body Shop"),       # "Shop" is part of the name here
    ("apollopharmacy.in", "Apollo"),          # website -> "Apollo Pharmacy" -> alias
    ("luzo.app", "Luzo"),
    ("resonate.store", "Resonate"),
    ("Uber", "Uber."),
    ("firstcry.com", "Firstcry"),
    ("Liberty", "Liberty Online"),          # alias lists two; only one works online
    ("Steam", "Steam wallet"),              # Maximize/BuyHatke call it "Steam" (18 Nov 2026: sent to Maximize)
    ("Steam Wallet INR 500", "Steam wallet"),
    ("Nintendo eShop Voucher", "Nintendo"),
    ("Unipin- BGMI Voucher", "BGMI UniPin"),
])
def test_online_matches(merchant, expected):
    assert _name(merchant) == expected


def test_every_alias_reaches_a_hubble_card():
    """A link to a title Hubble has renamed or dropped would quietly hand the
    shop back to the partners. Every alias must still find a card."""
    aliases = json.loads((PROD.parent / "hubble_aliases.json").read_text())
    titles = {hs.normalize(b["name"]) for b in json.loads(PROD.read_text())}
    dead = {k: v for k, v in aliases.items()
            if not k.startswith("_") and not any(hs.normalize(n) in titles for n in v)}
    assert not dead, dead


@pytest.mark.parametrize("merchant,expected", [
    ("Westside (in-store)", "Westside"),
    ("Absolute Barbeque", "Absolute Barbecues"),  # partner spelling
    ("Marks &amp; Spencer", "Marks & Spencer"),   # Maximize's name arrives with "&amp;"
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
    # "Apollo Pharmacy" was here until 17 Nov 2026, when Hubble's own terms
    # confirmed its "Apollo" card is the pharmacy one (now in the alias list).
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
    # 13 Nov 2026: searching "MakeMyTrip Hotel" sold Gyftr's card, not Dealo's.
    ("MakeMyTrip Hotel e-Pay", "MakeMyTrip Hotel"),  # Gyftr
    ("MakeMyTrip Hotel E Pay", "MakeMyTrip Hotel"),  # Maximize
    ("MakeMyTrip e-Pay", "MakeMyTrip"),
    ("MakeMyTrip E-Pay", "MakeMyTrip"),
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
    brands = json.loads(PROD.read_text())
    broken = []
    for b in brands:
        found = hs.brand_by_slug(hs.buy_slug(b["name"]))
        if not found or hs.normalize(found["name"]) != hs.normalize(b["name"]):
            broken.append(b["name"])
    # Titles that collide once punctuation is dropped resolve to the online
    # one; a tie with no online entry answers nothing rather than guessing.
    assert broken == [], broken


# Google Shopping's shop names don't always match Hubble's ("Decathlon Sports
# India" for decathlon.in, fishing rod search 17 Nov 2026). The result's buy
# link — or a shop name that is itself a web address — is read through the
# hand-checked website list (data/domain_brand_map.json) instead.
@pytest.mark.parametrize("merchant,link,expected", [
    ("Lifestyle Stores", "https://www.lifestylestores.com/in/en/p/123", "Lifestyle"),
    ("Some Odd Shop Name", "https://www.decathlon.in/p/8739959/lure-rod", "Decathlon"),
    ("zeptonow.com", None, "Zepto"),
    ("lifestylestores.com", None, "Lifestyle"),
])
def test_the_store_website_finds_the_shop(merchant, link, expected):
    found = hs.brand_for(merchant, False, link)
    assert found and found["name"] == expected


def test_a_website_off_the_list_finds_nothing():
    assert hs.brand_for("Some Odd Shop Name", False, "https://www.example-unknown-shop.in/p/1") is None


def test_a_subdomain_is_never_read_as_its_parent_site():
    # luxe.ajio.com is AJIO Luxe, not AJIO: only "www." comes off the host.
    assert "ajio.com" not in hs._hosts("Some Shop", "https://luxe.ajio.com/p/1")
    assert hs._hosts("x", "https://www.decathlon.in/p/1?a=b") == ["decathlon.in"]


def test_the_shop_name_still_wins_over_the_website():
    # A name that matches is never second-guessed by its link.
    assert _name("Nykaa") == "Nykaa"
    assert hs.brand_for("Nykaa", False, "https://www.decathlon.in/p/1")["name"] == "Nykaa"


@pytest.mark.parametrize("domain", ["candere.com", "timesprime.com", "xbox.com", "ketandiamonds.com", "apollo247.com"])
def test_a_website_never_picks_one_kind_of_several(domain):
    # Hubble sells several kinds of these shops' vouchers (coin / gold /
    # diamond, Lite / Power / Prive...); the website can't say which one the
    # cart needs, so it finds none.
    assert hs.brand_for("Some Odd Shop Name", False, f"https://www.{domain}/p/1") is None


def test_every_hubble_card_is_found_by_its_own_name():
    # "The Body Shop" / "The Raymond Shop" / "Organic India" were unreachable:
    # their last word was dropped as a generic "Shop"/"India" (17 Nov 2026).
    for b in json.loads(PROD.read_text()):
        for in_store in (False, True):
            if ("OFFLINE" if in_store else "ONLINE") not in b["works"]:
                continue
            found = hs.brand_for(b["name"], in_store)
            assert found and found["id"] == b["id"], (b["name"], in_store)
