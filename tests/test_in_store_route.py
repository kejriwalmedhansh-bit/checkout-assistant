"""A Gift Voucher that works only in the shop's stores (12 Nov 2026).

An in-store route asks the shopper to visit a shop, so it is recommended first
only when it beats the best online price by at least ₹200
(search_service.IN_STORE_MIN_SAVING). Every in-store voucher carries a maps
link to the nearest stores, the first of its three steps.

Run:  .venv/bin/python -m pytest tests/test_in_store_route.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import search_service, voucher_service  # noqa: E402


def _voucher(merchant: str, effective: float, offline: bool) -> dict:
    return {"merchant": merchant, "offline_only": offline,
            "upi": {"effective_price": effective}, "card": {"effective_price": effective}}


def _routes(store_cost: float, online_price: float) -> dict:
    results = [
        {"merchant": "Indian Terrain", "price": 2999, "title": "Navy Check Shirt", "sellers": []},
        {"merchant": "Myntra", "price": online_price, "title": "Navy Check Shirt", "sellers": []},
    ]
    return search_service._build_routes(results, [_voucher("Indian Terrain", store_cost, True)])


def test_in_store_leads_when_it_saves_200_or_more():
    r = _routes(store_cost=2602, online_price=2899)  # saves ₹297 over Myntra
    assert r["recommended"]["merchant"] == "Indian Terrain (in-store)"


def test_in_store_waits_behind_online_when_saving_is_small():
    r = _routes(store_cost=2602, online_price=2749)  # saves only ₹147
    assert r["recommended"]["merchant"] == "Myntra"
    assert r["alternatives"][0]["merchant"] == "Indian Terrain (in-store)"


def test_in_store_alone_still_leads():
    results = [{"merchant": "Indian Terrain", "price": 2999, "title": "Shirt", "sellers": []}]
    r = search_service._build_routes(results, [_voucher("Indian Terrain", 2602, True)])
    assert r["recommended"]["merchant"] == "Indian Terrain (in-store)"


def test_store_finder_link():
    url = voucher_service.store_finder_url("Indian Terrain (in-store)")
    assert url == "https://www.google.com/maps/search/?api=1&query=Indian+Terrain+store+near+me"
    assert "In+Store" not in voucher_service.store_finder_url("Westside In Store")
