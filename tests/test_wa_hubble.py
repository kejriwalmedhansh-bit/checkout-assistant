"""WhatsApp sends shoppers to Dealo's own buy page when Hubble's rate is
close enough to today's best; otherwise the partner step is unchanged.

Run:  .venv/bin/python -m pytest tests/test_wa_hubble.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import hubble_service, whatsapp_service  # noqa: E402

ROUTE = {
    "merchant": "Myntra",
    "listed_price": 2000,
    "sellers": [],
    "voucher": {
        "brand_name": "Myntra",
        "voucher_source": "buyhatke",
        "voucher_url": "https://buyhatke.com/gift-cards/myntra",
        "how_to_redeem_short": "Add it under Gift Cards at checkout.",
        "upi": {
            "pct": 3.5, "voucher_amount": 2000, "purchase_breakdown": "₹2,000",
            "denomination_breakdown": [{"denom": 2000, "count": 1}], "txns_needed": 1, "remainder": 0,
        },
    },
}

OFFER = {
    "brand_name": "Myntra", "discount_pct": 4.0, "voucher_total": 2000,
    "denominations": [{"amount": 2000, "count": 1}], "you_pay": 1920, "you_save": 80, "rest_at_shop": 0,
}

BRAND = {
    "brand_name": "Zomato", "discount_pct": 4.0, "works": ["ONLINE"], "in_store": False,
    "min_amount": 1001, "max_amount": 10000, "cards": [], "typed": True,
}


def _harness(monkeypatch, *, offer=None, brand=None):
    calls = {"cta": [], "texts": [], "events": []}

    async def noop(*a, **k):
        return None

    async def fake_cta(phone, body, button, url):
        calls["cta"].append((body, button, url))
        return True

    async def fake_text(phone, body):
        calls["texts"].append(body)

    async def fake_offer(merchant, price, in_store=False):
        return offer

    async def fake_brand(merchant=None, slug=None):
        return brand

    monkeypatch.setattr(whatsapp_service.asyncio, "sleep", noop)
    monkeypatch.setattr(whatsapp_service, "send_cta_url", fake_cta)
    monkeypatch.setattr(whatsapp_service, "send_text", fake_text)
    monkeypatch.setattr(whatsapp_service, "_track", lambda event, *a, **k: calls["events"].append((event, k)))
    monkeypatch.setattr(hubble_service, "offer_for", fake_offer)
    monkeypatch.setattr(hubble_service, "brand_info", fake_brand)
    monkeypatch.setattr(whatsapp_service.session_store, "get_session", lambda phone: {})
    monkeypatch.setattr(whatsapp_service.session_store, "set_session", lambda phone, s: None)
    return calls


def test_product_route_buys_on_dealo_when_hubble_is_close(monkeypatch):
    calls = _harness(monkeypatch, offer=OFFER)
    asyncio.run(whatsapp_service._send_voucher_steps("919999999999", ROUTE))
    body, button, url = calls["cta"][0]
    assert button == "Buy on Dealo"
    assert url.endswith("/buy/myntra?amount=2000&src=wa")
    assert "on Dealo" in body and "4% off" in body and "Pay by UPI" in body
    assert "Step 1 of 2" in body
    assert any("Step 2 of 2" in t and "Open *Myntra*" in t for t in calls["texts"])
    assert ("WhatsApp Buy Step Shown", {"step": "voucher", "platform": "Dealo", "merchant": "Myntra", "discount_pct": 4.0}) in calls["events"]


def test_product_route_keeps_partner_when_hubble_is_far_behind(monkeypatch):
    calls = _harness(monkeypatch, offer={**OFFER, "discount_pct": 1.0})
    asyncio.run(whatsapp_service._send_voucher_steps("919999999999", ROUTE))
    body, button, url = calls["cta"][0]
    assert button == "Buy Gift Voucher Now"
    assert "BuyHatke" in body and "/out?url=" in url


def test_product_route_keeps_partner_when_hubble_has_nothing(monkeypatch):
    calls = _harness(monkeypatch, offer=None)
    asyncio.run(whatsapp_service._send_voucher_steps("919999999999", ROUTE))
    assert calls["cta"][0][1] == "Buy Gift Voucher Now"


def test_shop_name_search_buys_on_dealo(monkeypatch):
    calls = _harness(monkeypatch, brand=BRAND)
    voucher = {"brand_name": "Zomato", "voucher_source": "maximize", "best_discount_pct": 3.5,
               "voucher_url": "https://www.maximize.money/gift-cards/Zomato/1"}
    asyncio.run(whatsapp_service._send_brand_voucher("919999999999", "zomato", voucher))
    body, button, url = calls["cta"][0]
    assert button == "Buy on Dealo"
    assert url.endswith("/buy/zomato?src=wa")
    assert "*4% off* on Dealo" in body and "₹1,001" in body and "₹10,000" in body


def test_shop_name_search_keeps_partner_when_hubble_is_behind(monkeypatch):
    calls = _harness(monkeypatch, brand={**BRAND, "discount_pct": 1.0})
    voucher = {"brand_name": "Zomato", "voucher_source": "maximize", "best_discount_pct": 3.5,
               "voucher_url": "https://www.maximize.money/gift-cards/Zomato/1"}
    asyncio.run(whatsapp_service._send_brand_voucher("919999999999", "zomato", voucher))
    assert calls["cta"][0][1] == "Buy Gift Voucher Now"
    assert "Maximize" in calls["cta"][0][0]
