"""Bank card offers read from a store's own product page (Flipkart).

The fixture is the bank offer block of Flipkart's iPhone 17 Pro (256 GB,
₹1,34,900) page as Context.dev rendered it on 2026-10-26.

Run:  .venv/bin/python -m pytest tests/test_card_offers.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.repositories import bank_offer_repository as bor  # noqa: E402
from src.services import search_service as ss  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "flipkart_bank_offers_iphone17pro.html"


def test_reads_flipkart_bank_offers_best_first():
    offers = bor.flipkart_bank_offers(FIXTURE.read_text())
    assert offers == [
        {"bank": "HDFC", "card": "Credit Card", "saving": 6000.0, "cashback": False},
        {"bank": "Flipkart Axis", "card": "Credit Card", "saving": 4000.0, "cashback": True},
        {"bank": "Flipkart SBI", "card": "Credit Card", "saving": 4000.0, "cashback": True},
    ]


def test_page_without_bank_offers_gives_none():
    assert bor.flipkart_bank_offers("<div>Buy at ₹799</div><div>Delivery details</div>") == []
    assert bor.flipkart_bank_offers("") == []


def test_stops_at_the_emi_block():
    page = (
        "<div>Bank offers</div><div>₹500 off</div><div>Apply</div><div>HDFC</div><div>Debit Card</div>"
        "<div>Bank offers</div><div>₹9,999 off</div><div>Apply</div><div>Kotak</div><div>Credit Card</div>"
    )
    assert bor.flipkart_bank_offers(page) == [
        {"bank": "HDFC", "card": "Debit Card", "saving": 500.0, "cashback": False},
    ]


def _store(name, link, price=100.0):
    return {"merchant": name, "price": price, "sellers": [{"link": link}]}


def test_only_a_flipkart_product_page_is_read(monkeypatch):
    read = []
    monkeypatch.setattr(ss.context_dev_repository, "fetch_rendered_html", lambda url: read.append(url) or FIXTURE.read_text())
    candidates = [
        _store("Amazon", "https://www.amazon.in/dp/B0FQG1LPVF"),
        _store("Flipkart", "https://www.flipkart.com/search?q=iphone"),
        _store("Flipkart", "https://www.flipkart.com/apple-iphone-17-pro/p/itm76fe37ca9ea8c", 134900.0),
    ]
    found = ss._read_card_offers(candidates)
    assert read == ["https://www.flipkart.com/apple-iphone-17-pro/p/itm76fe37ca9ea8c"]
    assert found[0]["store"] == "Flipkart" and found[0]["price"] == 134900.0
    assert found[0]["offers"][0]["saving"] == 6000.0


def test_no_flipkart_no_read(monkeypatch):
    monkeypatch.setattr(ss.context_dev_repository, "fetch_rendered_html", lambda url: (_ for _ in ()).throw(AssertionError("read")))
    assert ss._read_card_offers([_store("Amazon", "https://www.amazon.in/dp/B0FQG1LPVF")]) == []
