"""One Hubble decision for every screen (18 Nov 2026).

The website, WhatsApp and the price lists used to ask Hubble only when a
partner (Gyftr / Maximize / BuyHatke) also sold the shop, and each screen
asked on its own. Now the search asks Hubble once for every shop and ranks
by what the shopper pays through Dealo.

Run:  .venv/bin/python -m pytest tests/test_hubble_one_decision.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import hubble_service, price_list, search_service  # noqa: E402

OFFER = {"brand_id": "x", "brand_name": "Zudio", "discount_pct": 10.0, "voucher_total": 1000,
         "you_pay": 900.0, "you_save": 100.0, "rest_at_shop": 0, "in_store": False,
         "denominations": [{"amount": 1000, "count": 1}]}


def _results():
    return [
        {"merchant": "Myntra", "price": 950, "title": "Shirt", "sellers": [{"link": "https://myntra.com/p"}]},
        {"merchant": "Zudio", "price": 1000, "title": "Shirt", "sellers": [{"link": "https://zudio.com/p"}]},
    ]


def _fake_offers(answers):
    def fake(items, timeout=5.0):
        return [answers.get(merchant, (True, None)) for merchant, *_ in items]
    return fake


def test_hubble_only_shop_ranks_by_dealo_price(monkeypatch):
    # No partner sells Zudio; Dealo's voucher makes it ₹900, cheaper than Myntra's ₹950.
    monkeypatch.setattr(hubble_service, "offers_for_shops", _fake_offers({"Zudio": (True, OFFER)}))
    monkeypatch.setattr(search_service, "_card_fomo_for_route", lambda r: None)
    routes = search_service._build_routes(_results(), [])
    rec = routes["recommended"]
    assert rec["merchant"] == "Zudio" and rec["final_cost"] == 900.0
    assert rec["hubble"] == OFFER and rec["hubble_checked"] is True and rec["voucher"] is None
    assert routes["alternatives"][0]["hubble_checked"] is True and routes["alternatives"][0]["hubble"] is None


def test_hubble_slow_means_dont_know(monkeypatch):
    monkeypatch.setattr(hubble_service, "offers_for_shops", _fake_offers({"Zudio": (False, None)}))
    monkeypatch.setattr(search_service, "_card_fomo_for_route", lambda r: None)
    routes = search_service._build_routes(_results(), [])
    zudio = next(r for r in [routes["recommended"], *routes["alternatives"]] if r["merchant"] == "Zudio")
    assert zudio["hubble_checked"] is False and zudio["final_cost"] == 1000


def test_results_carry_the_answer_for_price_lists(monkeypatch):
    monkeypatch.setattr(hubble_service, "offers_for_shops", _fake_offers({"Zudio": (True, OFFER)}))
    monkeypatch.setattr(search_service, "_card_fomo_for_route", lambda r: None)
    results = _results()
    routes = search_service._build_routes(results, [])
    shops = price_list.build_price_list({"results": results, "vouchers": []})
    zudio = next(s for s in shops if s["merchant"] == "Zudio")
    assert zudio["voucher_route"]["final_cost"] == 900.0 and zudio["voucher_route"]["hubble"] == OFFER
    assert price_list.gift_card_saving(zudio) == 100
    # Saves ₹50 against the cheapest shop: under ₹100, so the price list leads.
    assert price_list.should_show_price_list(shops, routes["recommended"]) is True


def test_offers_for_shops_sure_no_without_asking(monkeypatch):
    monkeypatch.setattr(hubble_service, "get_settings", lambda: type("S", (), {"HUBBLE_ENABLED": True})())
    monkeypatch.setattr(hubble_service, "brand_for", lambda *a, **k: None)

    async def boom(*a, **k):
        raise AssertionError("not asked")
    monkeypatch.setattr(hubble_service, "offer_for", boom)
    assert hubble_service.offers_for_shops([("Croma", 1000, False, None)]) == [(True, None)]


def test_offers_for_shops_timeout_is_dont_know(monkeypatch):
    monkeypatch.setattr(hubble_service, "get_settings", lambda: type("S", (), {"HUBBLE_ENABLED": True})())
    monkeypatch.setattr(hubble_service, "brand_for", lambda *a, **k: {"id": "z", "name": "Zudio"})

    async def slow(*a, **k):
        await asyncio.sleep(1)
    monkeypatch.setattr(hubble_service, "offer_for", slow)
    assert hubble_service.offers_for_shops([("Zudio", 1000, False, None)], timeout=0.05) == [(False, None)]


def test_shop_name_search_gets_dealo_card(monkeypatch):
    partner = {"brand_name": "Steam", "voucher_source": "maximize", "best_discount_pct": 4.5,
               "voucher_url": "https://www.maximize.money/x"}
    dealo = {"brand_name": "Steam wallet", "slug": "steam-wallet", "voucher_source": "hubble",
             "voucher_url": "https://getdealo.in/buy/steam-wallet", "best_discount_pct": 4.0, "denominations": [150]}
    monkeypatch.setattr(search_service, "_hubble_card", lambda name: dealo if name == "Steam" else None)
    assert search_service._as_hubble_card(partner, "steam") == dealo
    # A shop's kinds keep their label ("Hotels").
    choice = {**partner, "choice_label": "Wallet"}
    assert search_service._as_hubble_card(choice)["choice_label"] == "Wallet"
    # Hubble doesn't sell it: the partner card stays.
    monkeypatch.setattr(search_service, "_hubble_card", lambda name: None)
    assert search_service._as_hubble_card(partner, "steam") == partner
