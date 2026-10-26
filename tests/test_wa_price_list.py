"""WhatsApp price list: same rule as the website, and every carousel Meta
gets fits Meta's limits (2-10 cards, card text <= 160 chars and <= 2 line
breaks, button <= 20 chars, one link button per card).

Run:  .venv/bin/python -m pytest tests/test_wa_price_list.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services import price_list, whatsapp_service  # noqa: E402


def _listing(merchant, price, link, delivery="Free delivery"):
    return {"merchant": merchant, "price": price, "title": "Google Pixel 11 5G (12GB RAM, 256GB Storage)",
            "sellers": [{"link": link, "delivery": delivery}]}


def _voucher(merchant, pay, offline=False):
    return {"merchant": merchant, "offline_only": offline, "upi": {"effective_price": pay}}


# Prices from the 23 Oct live screenshot.
PIXEL = {
    "results": [
        _listing("Vijay Sales", 89999, "https://www.vijaysales.com/p/1", "Free next-day delivery"),
        _listing("Amazon.in", 78100, "https://www.amazon.in/dp/1"),
        _listing("Reliance Digital", 82999, "https://www.reliancedigital.in/p/1", "Free delivery between Sun–Mon"),
        _listing("Amazon.in", 79000, "https://www.amazon.in/dp/2"),
    ],
    "vouchers": [_voucher("Amazon.in", 77850), _voucher("Reliance Digital", 82584, True), _voucher("Vijay Sales", 87749, True)],
}
REC = {"merchant": "Amazon.in", "voucher": {"merchant": "Amazon.in"}, "final_cost": 77850, "listed_price": 78100}


def test_cheapest_first_one_row_per_shop():
    shops = price_list.build_price_list(PIXEL)
    assert [s["merchant"] for s in shops] == ["Amazon.in", "Reliance Digital", "Vijay Sales"]
    assert shops[0]["price"] == 78100
    assert price_list.gift_card_saving(shops[0]) == 250


def test_rule_matches_website():
    shops = price_list.build_price_list(PIXEL)
    assert price_list.should_show_price_list(shops, REC)  # ₹250 is under 2%
    big = {**REC, "final_cost": 70000}  # ₹8,100 off, 10%: gift card steps lead
    assert not price_list.should_show_price_list(shops, big)
    assert not price_list.should_show_price_list(shops[:1], REC)  # one shop, nothing to compare


def test_short_delivery_and_rupees():
    assert price_list.short_delivery("Free delivery between Sun–Mon") == "Free, Sun–Mon"
    assert price_list.short_delivery("Free next-day delivery") == "Free, next day"
    assert price_list.short_delivery("Delivery ₹49") == "+₹49 delivery"
    assert price_list.inr(123456) == "₹1,23,456" and price_list.inr(78100) == "₹78,100"


def _sent_carousel(shops, monkeypatch):
    sent = {}

    async def fake_carousel(phone, body, cards):
        sent["body"], sent["cards"] = body, cards
        return True

    async def noop(*a, **k):
        return None

    monkeypatch.setattr(whatsapp_service, "send_carousel", fake_carousel)
    monkeypatch.setattr(whatsapp_service, "send_reply_buttons", noop)
    monkeypatch.setattr(whatsapp_service, "_MESSAGE_PACE_SECONDS", 0)
    monkeypatch.setattr(whatsapp_service, "_track", lambda *a, **k: None)
    ok = asyncio.run(whatsapp_service._send_price_list("919999999999", "Google Pixel 11 5G", shops))
    return ok, sent


def test_carousel_fits_meta_limits(monkeypatch):
    many = {"results": [_listing(f"Shop Number {i} With A Long Name", 50000 + i * 900, f"https://s{i}.in/p")
                        for i in range(14)], "vouchers": []}
    for result in (PIXEL, many):
        ok, sent = _sent_carousel(price_list.build_price_list(result), monkeypatch)
        assert ok
        cards = sent["cards"]
        assert 2 <= len(cards) <= 10
        assert len(sent["body"]) <= 1024
        for i, c in enumerate(cards):
            assert c["card_index"] == i and c["type"] == "cta_url"
            assert c["header"]["image"]["link"].startswith("http")
            text = c["body"]["text"]
            assert len(text) <= 160 and text.count("\n") <= 2
            assert len(c["action"]["parameters"]["display_text"]) <= 20


def test_pixel_cards_read_right(monkeypatch):
    ok, sent = _sent_carousel(price_list.build_price_list(PIXEL), monkeypatch)
    assert "Cheapest first · 3 shops checked" in sent["body"]
    assert "₹11,899 less than Vijay Sales" in sent["body"]
    first = sent["cards"][0]
    assert first["body"]["text"] == "*Amazon.in*\nFree delivery\n−₹250 with Gift Voucher"
    assert first["action"]["parameters"]["display_text"] == "Buy on Amazon.in"
    assert "ctx=price_list" in first["action"]["parameters"]["url"]
    assert sent["cards"][1]["body"]["text"].endswith("−₹415 with in-store Gift Voucher")


def test_shops_without_a_link_are_left_out(monkeypatch):
    shops = price_list.build_price_list(PIXEL)
    shops[1]["link"] = None
    ok, sent = _sent_carousel(shops, monkeypatch)
    assert ok and [c["body"]["text"].split("\n")[0] for c in sent["cards"]] == ["*Amazon.in*", "*Vijay Sales*"]


def test_card_picture_draws():
    jpeg = price_list.render_price_card("Croma", "", 84990, 78100, 89999, 2)
    assert jpeg[:3] == b"\xff\xd8\xff" and len(jpeg) < 200_000
