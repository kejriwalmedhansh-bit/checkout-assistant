"""/voucher-check carries Dealo's own voucher (Hubble) when its rate is
within 2 points of the partner's, so the extension can send the shopper to
getdealo.in/buy/<shop> instead of the partner site.

Run:  .venv/bin/python -m pytest tests/test_voucher_check_dealo.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.routers import voucher_check as vc  # noqa: E402
from src.services import hubble_service  # noqa: E402

PARTNER = {"has_voucher": True, "brand_name": "Myntra", "voucher_source": "buyhatke", "pct": 3.5,
           "saving": 70, "priced": True, "voucher_url": "https://buyhatke.com/x"}
OFFER = {"brand_name": "Myntra", "discount_pct": 4.0, "voucher_total": 2000, "you_pay": 1920,
         "you_save": 80, "rest_at_shop": 0, "denominations": [{"amount": 2000, "count": 1}]}


def _with(monkeypatch, offer):
    async def fake(merchant, price, in_store=False, link=None):
        return offer
    monkeypatch.setattr(hubble_service, "offer_for", fake)
    monkeypatch.setattr(vc, "voucher_check", lambda domain, price=None: dict(PARTNER))
    return asyncio.run(vc.voucher_check_with_dealo("myntra.com", 2000))


def test_dealo_block_when_hubble_is_close(monkeypatch):
    out = _with(monkeypatch, OFFER)
    d = out["dealo"]
    assert d["buy_url"].endswith("/buy/myntra?amount=2000&src=ext")
    assert d["discount_pct"] == 4.0 and d["you_save"] == 80
    assert d["denomination_breakdown"] == [{"denom": 2000, "count": 1}]
    # The partner deal itself is untouched: the extension still has it.
    assert out["voucher_source"] == "buyhatke"


def test_dealo_block_even_when_hubble_is_behind(monkeypatch):
    """Owner's call, 3 Nov 2026: Dealo sells wherever Hubble has it."""
    out = _with(monkeypatch, {**OFFER, "discount_pct": 1.0})
    assert out["dealo"]["discount_pct"] == 1.0


def test_no_dealo_block_without_hubble(monkeypatch):
    out = _with(monkeypatch, None)
    assert "dealo" not in out


def test_hubble_error_is_swallowed(monkeypatch):
    async def boom(merchant, price, in_store=False):
        raise RuntimeError("hubble down")
    monkeypatch.setattr(hubble_service, "offer_for", boom)
    monkeypatch.setattr(vc, "voucher_check", lambda domain, price=None: dict(PARTNER))
    out = asyncio.run(vc.voucher_check_with_dealo("myntra.com", 2000))
    assert out["has_voucher"] and "dealo" not in out


def test_hubble_only_shop_becomes_a_dealo_deal(monkeypatch):
    """18 Nov 2026: a shop with no partner deal used to show nothing in the
    extension even when Hubble sells it. Now the whole answer is Dealo's,
    shaped so the extension's existing screens draw it."""
    asked = []

    async def fake(merchant, price, in_store=False, link=None):
        asked.append((merchant, link))
        return OFFER
    monkeypatch.setattr(hubble_service, "offer_for", fake)
    monkeypatch.setattr(vc, "voucher_check", lambda domain, price=None: {"has_voucher": False})
    out = asyncio.run(vc.voucher_check_with_dealo("www.myntra.com", 2000))
    assert out["has_voucher"] and out["voucher_source"] == "dealo" and out["priced"]
    assert out["pct"] == 4.0 and out["saving"] == 80 and out["effective_price"] == 1920
    assert out["voucher_url"].endswith("/buy/myntra?amount=2000&src=ext")
    assert asked == [("myntra.com", "myntra.com")]  # found by the website itself


def test_partner_name_misses_then_website_finds_it(monkeypatch):
    async def fake(merchant, price, in_store=False, link=None):
        return OFFER if merchant == "myntra.com" else None
    monkeypatch.setattr(hubble_service, "offer_for", fake)
    monkeypatch.setattr(vc, "voucher_check", lambda domain, price=None: {**PARTNER, "brand_name": "Myntra Odd Name"})
    out = asyncio.run(vc.voucher_check_with_dealo("myntra.com", 2000))
    assert out["dealo"]["brand_name"] == "Myntra" and out["voucher_source"] == "buyhatke"


def test_no_price_leaves_the_answer_alone(monkeypatch):
    async def fake(*a, **k):
        raise AssertionError("Hubble must not be asked without an amount")
    monkeypatch.setattr(hubble_service, "offer_for", fake)
    monkeypatch.setattr(vc, "voucher_check", lambda domain, price=None: {"has_voucher": False})
    assert asyncio.run(vc.voucher_check_with_dealo("myntra.com", None)) == {"has_voucher": False}
