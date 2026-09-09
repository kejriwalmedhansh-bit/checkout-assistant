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
    answer = voucher_check(domain="subway.co.in", price=12000)
    assert answer.get("has_voucher"), "subway.co.in still finds nothing"
    assert answer["brand_name"].lower() == "subway"


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
