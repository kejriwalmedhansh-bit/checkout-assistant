"""Which store pages Dealo re-reads for today's price after building routes.

The web price list (shown when a gift card saves too little) puts the
cheapest store on top, which is not always the recommended (gift card)
store. Both must get the live re-check, or the top of the list can show
Google's stale price.

Run:  .venv/bin/python -m pytest tests/test_live_price_check.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import search_service as ss  # noqa: E402


def _store(name, price, pinned=False):
    c = {"merchant": name, "price": price, "sellers": [{"link": f"https://{name.lower().replace(' ', '')}.in/p/1"}]}
    if pinned:
        c["_pinned"] = True
    return c


def _run(candidates, rec_merchant, live_prices, monkeypatch):
    read = []

    def fake_read(link):
        read.append(link)
        return live_prices.get(link)

    monkeypatch.setattr(ss, "_read_store_price", fake_read)
    output = {"routes": {"recommended": {"merchant": rec_merchant}}}
    updated = ss._check_winner_live(output, candidates, "Apple iPhone 16")
    return output, updated, read


def test_cheapest_store_is_checked_when_it_is_not_the_recommended_one(monkeypatch):
    # iPhone 16, 23 Oct: Reliance Digital recommended (in-store gift card),
    # Sathya Retail ₹1 cheaper and first in the price list.
    sathya, reliance, amazon = _store("Sathya Retail", 69899), _store("Reliance Digital", 69900), _store("Amazon.in", 76999)
    output, updated, read = _run(
        [sathya, reliance, amazon], "Reliance Digital (in-store)",
        {"https://sathyaretail.in/p/1": 71999.0}, monkeypatch,
    )
    assert sorted(read) == ["https://reliancedigital.in/p/1", "https://sathyaretail.in/p/1"]
    assert updated is not None and sathya["price"] == 71999.0
    assert [c["store"] for c in output["price_check"]] == ["Reliance Digital", "Sathya Retail"]


def test_one_read_when_the_recommended_store_is_also_the_cheapest(monkeypatch):
    # Philips mixer: same ₹3,299 at both; Flipkart recommended for its gift card.
    amazon, flipkart = _store("Amazon.in", 3299), _store("Flipkart", 3299)
    _, updated, read = _run([amazon, flipkart], "Flipkart", {}, monkeypatch)
    assert read == ["https://flipkart.in/p/1"]
    assert updated is None


def test_quick_commerce_is_never_the_cheapest_to_check(monkeypatch):
    blinkit, croma = _store("Blinkit", 57900), _store("Croma", 85990)
    _, _, read = _run([blinkit, croma], "Croma", {}, monkeypatch)
    assert read == ["https://croma.in/p/1"]


def test_a_wild_page_price_is_ignored(monkeypatch):
    # A page price outside half-to-one-and-a-half times the listing is more
    # likely a different item on the page than a real price change.
    sathya, reliance = _store("Sathya Retail", 69899), _store("Reliance Digital", 69900)
    output, updated, _ = _run(
        [sathya, reliance], "Reliance Digital", {"https://sathyaretail.in/p/1": 9999.0}, monkeypatch,
    )
    assert updated is None and sathya["price"] == 69899
    assert output["price_check"][1]["live"] is None


def test_pasted_page_price_is_not_re_read(monkeypatch):
    # A pinned row already carries the live price read off the pasted link.
    pasted, croma = _store("Amazon.in", 3299, pinned=True), _store("Croma", 3499)
    _, _, read = _run([pasted, croma], "Croma", {}, monkeypatch)
    assert read == ["https://croma.in/p/1"]
