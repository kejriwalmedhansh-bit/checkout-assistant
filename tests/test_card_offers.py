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


# --- Croma and Vijay Sales (2026-10-28): offers written as sentences --------

CROMA = Path(__file__).parent / "fixtures" / "croma_bank_offers_iphone17pro.html"
VIJAY = Path(__file__).parent / "fixtures" / "vijaysales_bank_offers_iphone17pro.html"
IPHONE = 134900.0


def test_reads_croma_full_swipe_offers_only():
    # The strip also has three "No-cost EMI" offers, an AU Bank one (not a
    # picker bank) and two Tata Neu NeuCoins lines: none of those count.
    assert bor.croma_bank_offers(CROMA.read_text(), IPHONE) == [
        {"bank": "ICICI", "card": "Credit Card", "saving": 4000, "cashback": False},
        {"bank": "IDFC FIRST", "card": "Credit Card", "saving": 4000, "cashback": False},
        {"bank": "HDFC", "card": "Credit Card", "saving": 4000, "cashback": False},
    ]


def test_croma_minimum_transaction_is_respected():
    # "on minimum transaction amount of Rs 54000": a cheaper item gets nothing.
    assert bor.croma_bank_offers(CROMA.read_text(), 40000.0) == []


def test_vijay_sales_iphone_offers_are_all_emi_or_one_particular_card():
    # 11 EMI-only lines plus "20% Upto Rs.10000 ... HSBC TAJ Bank Credit Card
    # NON-EMI", which is one particular HSBC card, not any HSBC card.
    assert bor.vijay_sales_bank_offers(VIJAY.read_text(), IPHONE) == []


def test_vijay_sales_sentence_shapes():
    page = (
        '<ul><li class="instant-discount-offer">Flat Rs.2000 Instant Discount on HDFC Bank Credit Card/Debit Card<span>View Details</span></li>'
        '<li class="best-offer instant-discount-offer">10% Instant Discount upto Rs.3,000 on BOB Credit Card Full Swipe<span>x</span></li>'
        '<li class="instant-discount-offer">10% Instant Discount on Axis Bank Credit Card<span>x</span></li>'  # no cap: never guessed
        '<li class="instant-discount-offer">Flat Rs.750 Instant Discount on ICICI Bank Credit Card EMI<span>x</span></li>'
        '<li class="instant-discount-offer">Flat Rs.2000 Instant Discount on HDFC Bank Credit Card/Debit Card<span>dup</span></li></ul>'
    )
    assert bor.vijay_sales_bank_offers(page, 40000.0) == [
        {"bank": "BOBCARD", "card": "Credit Card", "saving": 3000, "cashback": False},
        {"bank": "HDFC", "card": "Credit Card", "saving": 2000, "cashback": False},
        {"bank": "HDFC", "card": "Debit Card", "saving": 2000, "cashback": False},
    ]


def test_sentence_rules():
    one = bor.offer_from_sentence
    assert one("5% cashback up to Rs 1,500 on Kotak Bank Credit Card", 40000.0) == [
        {"bank": "Kotak", "card": "Credit Card", "saving": 1500, "cashback": True}]
    assert one("5% cashback up to Rs 1,500 on Kotak Bank Credit Card", 20000.0)[0]["saving"] == 1000
    assert one("Instant discount of Rs.4000 for 6 months No-cost EMI on HDFC Bank Credit Card", IPHONE) == []
    assert one("Get up to 10% NeuCoins on select Apple products on Tata Neu SBI Bank Credit Card", IPHONE) == []
    assert one("Flat Rs.4000 Instant Discount on RBL Bank Credit Card", IPHONE) == []  # not a picker bank
    assert one("", IPHONE) == []
    # Vijay Sales spells it "BOB CARD Bank" on the Galaxy S25 Ultra (2026-10-29).
    assert one("Flat Rs.19,000 Instant Discount on BOB CARD Bank Credit Card Full Swipe.", 138490.0) == [
        {"bank": "BOBCARD", "card": "Credit Card", "saving": 19000, "cashback": False}]


def test_reader_for_links():
    assert bor.reader_for("https://www.croma.com/apple-iphone-17-pro-256gb-cosmic-orange-/p/317417")[0] == "Croma"
    assert bor.reader_for("https://www.vijaysales.com/p/P245195/245195/apple-iphone-17-pro-256gb-cosmic-orange")[0] == "Vijay Sales"
    assert bor.reader_for("https://www.flipkart.com/apple-iphone-17-pro/p/itm76fe37ca9ea8c")[0] == "Flipkart"
    assert bor.reader_for("https://www.croma.com/searchB?q=iphone") is None
    assert bor.reader_for("https://www.amazon.in/dp/B0FQG1LPVF") is None


def test_three_stores_read_one_after_another_flipkart_first(monkeypatch):
    pages = {
        "https://www.flipkart.com/apple-iphone-17-pro/p/itm76fe37ca9ea8c": FIXTURE.read_text(),
        "https://www.croma.com/apple-iphone-17-pro-256gb-cosmic-orange-/p/317417": CROMA.read_text(),
        "https://www.vijaysales.com/p/P245195/245195/apple-iphone-17-pro-256gb-cosmic-orange": VIJAY.read_text(),
    }
    read = []
    monkeypatch.setattr(ss.context_dev_repository, "fetch_rendered_html", lambda url: read.append(url) or pages[url])
    candidates = [
        _store("Vijay Sales", "https://www.vijaysales.com/p/P245195/245195/apple-iphone-17-pro-256gb-cosmic-orange", 126900.0),
        _store("Croma", "https://www.croma.com/apple-iphone-17-pro-256gb-cosmic-orange-/p/317417", 128089.0),
        _store("Flipkart", "https://www.flipkart.com/apple-iphone-17-pro/p/itm76fe37ca9ea8c", IPHONE),
        _store("Croma", "https://www.croma.com/another/p/1"),  # a second Croma listing is not read again
    ]
    found = ss._read_card_offers(candidates)
    assert read[0].startswith("https://www.flipkart.com") and sorted(read) == sorted(pages)
    assert [(f["store"], f["offers"][0]["saving"]) for f in found] == [("Flipkart", 6000.0), ("Croma", 4000)]
