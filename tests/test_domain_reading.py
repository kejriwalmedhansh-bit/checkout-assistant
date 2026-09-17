"""Reading a shop's name out of the address bar.

The Chrome extension is the only surface that identifies a shop by its web
address — the website and WhatsApp bot search by product name — so everything
here is about what the extension sees on a checkout page.

Run:  .venv/bin/python -m pytest tests/test_domain_reading.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.routers.voucher_check import _domain_root, voucher_check  # noqa: E402


def test_indian_addresses_read_the_shops_name_not_co():
    """.co.in is India's ordinary shop address, and taking the second label
    from the right reads "co" out of every one of them. Found 2026-09-09:
    subway.co.in answered "no voucher" on the live site while the same shop
    priced fine by name."""
    for address, name in (
        ("subway.co.in", "subway"),
        ("tanishq.co.in", "tanishq"),
        ("www.pizzahut.co.in", "pizzahut"),
        ("shop.example.com.au", "example"),
        ("marks.co.uk", "marks"),
    ):
        assert _domain_root(address) == name, address


def test_ordinary_addresses_still_read_the_same():
    for address, name in (
        ("myfrido.com", "myfrido"),
        ("ajio.com", "ajio"),
        ("store.steampowered.com", "steampowered"),
        ("nykaa.com", "nykaa"),
        ("localhost", "localhost"),
    ):
        assert _domain_root(address) == name, address


def test_a_shop_that_says_its_own_name_needs_no_listing():
    """The hand-written domain map used to gate this: an address missing from
    its rows was answered "no voucher" without the shop's own name ever being
    tried. An exact brand-name match is its own evidence."""
    # Not in the map, and redeemable online. (subway.co.in, the address this
    # was found on, is the wrong example: Subway's voucher is in-store only on
    # every seller, so "no voucher" is the right answer there.)
    answer = voucher_check(domain="hammer.co.in", price=12000)
    assert answer.get("has_voucher"), "hammer.co.in still finds nothing"
    assert answer["brand_name"].lower() == "hammer"


def test_places_that_are_not_shops_stay_silent():
    """Asking the shop's own name before the map must not turn every address
    into a voucher — the exact-match rule is what holds that line."""
    for address in (
        "google.com", "mail.google.com", "github.com", "en.wikipedia.org",
        "claude.ai", "x.com", "instagram.com", "icicibank.com",
    ):
        assert not voucher_check(domain=address, price=5000).get("has_voucher"), address


def test_a_shop_whose_address_does_not_say_its_name_still_works():
    """What the domain map is actually for."""
    answer = voucher_check(domain="lifestylestores.com", price=12000)
    assert answer.get("has_voucher")


def test_a_store_only_voucher_never_answers_at_an_online_checkout():
    """These shops' vouchers work only at their tills. Reading the shop's
    name out of its address must not bring them back after the domain map
    dropped them — the two changes met 2026-09-17 and it did."""
    for address in ("reliancedigital.in", "vijaysales.com", "helios.co.in", "subway.co.in"):
        assert not voucher_check(domain=address, price=5000).get("has_voucher"), address
        assert not voucher_check(domain=address).get("has_voucher"), address


def test_a_card_whose_own_terms_say_stores_only_is_not_offered():
    """Gyftr and Maximize label Victoria's Secret for online use; both of
    their terms say listed stores only. Caught 2026-09-17."""
    for price in (3000, None):
        answer = voucher_check(domain="victoriassecret.in", price=price)
        assert not answer.get("has_voucher") or answer["voucher_source"] == "buyhatke", answer


def test_another_sellers_online_card_for_the_same_brand_still_counts():
    """Judged per card: Gyftr's Lifestyle card is stores only, BuyHatke's is
    online only. lifestylestores.com must still find the BuyHatke one."""
    answer = voucher_check(domain="lifestylestores.com", price=12000)
    assert answer.get("has_voucher")
    assert answer["voucher_source"] != "gyftr", answer


def test_a_card_labelled_in_store_loses_to_an_online_one():
    """Maximize's Starbucks card is labelled in-store and paid more than
    BuyHatke's online card, so it used to win at starbucks.in."""
    answer = voucher_check(domain="starbucks.in", price=2000)
    assert not answer.get("has_voucher") or answer["voucher_source"] != "maximize", answer


if __name__ == "__main__":
    checks = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for check in checks:
        try:
            check()
            print(f"  ok    {check.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {check.__name__}\n        {e}")
    print(f"\n{len(checks) - failed}/{len(checks)} passed")
    sys.exit(1 if failed else 0)
