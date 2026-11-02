"""A store's display name must find its voucher brand even when the store
names itself by its web address.

Found 2026-11-02: an igp.com product link read the store as "IGP.com", and
no voucher matched although IGP is on Gyftr, Maximize and BuyHatke — the
shopper was sent to pay full price. Three-letter brands (IGP, KFC, PVR, Lee,
MAX…) are never partial-matched, so the ".com" had to come off first.

Run:  .venv/bin/python -m pytest tests/test_brand_matching.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.repositories._brand_matching import _strip_generic_suffix_words, find_best_match  # noqa: E402
from src.repositories import voucher_repository, maximize_repository, buyhatke_repository  # noqa: E402

_RECORDS = [{"brand_name": n} for n in ("IGP", "KFC", "Amazon", "Hamleys-Luxe Gift Card", "Booking.com")]


def test_a_web_address_ending_comes_off_the_store_name():
    assert _strip_generic_suffix_words("IGP.com") == "IGP"
    assert _strip_generic_suffix_words("KFC.in") == "KFC"
    assert _strip_generic_suffix_words("Hamleys India") == "Hamleys"
    # Only a trailing ending: a dot inside the name is left alone.
    assert _strip_generic_suffix_words("Dr. Oetker") == "Dr. Oetker"


def test_a_short_brand_is_found_from_its_web_address_name():
    assert find_best_match("IGP.com", _RECORDS)["brand_name"] == "IGP"
    assert find_best_match("KFC.in", _RECORDS)["brand_name"] == "KFC"
    assert find_best_match("amazon.in", _RECORDS)["brand_name"] == "Amazon"
    # A brand whose real name is a web address still matches itself.
    assert find_best_match("Booking.com", _RECORDS)["brand_name"] == "Booking.com"


def test_igp_dot_com_finds_igp_on_every_voucher_source():
    assert (voucher_repository.get_by_merchant("IGP.com") or {}).get("brand_name") == "IGP"
    assert (maximize_repository.get_by_merchant("IGP.com") or {}).get("brand_name") == "IGP"
    assert (buyhatke_repository.get_by_merchant("IGP.com") or {}).get("brand_name") == "IGP"
