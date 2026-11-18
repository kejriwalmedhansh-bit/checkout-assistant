"""Safe buying through Hubble (audit 18 Nov 2026).

- the "voucher ready" screen gets the code of THIS purchase, never an
  earlier one bought in the last 30 minutes;
- an in-store buy link sells the in-store card;
- a purchase that fails to save is not reported "ok" to Hubble;
- a brief Hubble hiccup uses the last good copy of the voucher.

Run:  .venv/bin/python -m pytest tests/test_hubble_safe_buying.py -q
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.routers import hubble as router  # noqa: E402
from src.services import buyer_service, hubble_service  # noqa: E402

PROD = Path(__file__).resolve().parents[1] / "data" / "hubble_catalogue.json"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(router, "_recent_orders", {})
    monkeypatch.setattr(router, "_sessions", {})
    monkeypatch.setattr(hubble_service, "_catalogue_path", lambda: PROD)


def _order(brand, code, ref):
    return {"brandName": brand, "orderStatus": "COMPLETED", "userId": "u1", "transactionReferenceId": ref,
            "vouchers": [{"cardNumber": code}]}


def test_second_purchase_gets_its_own_code(monkeypatch):
    router._remember_order("u1", _order("Swiggy", "FIRST", "r1"))
    sid = router._open_session("u1", "Nykaa")
    # Nothing new yet: the earlier Swiggy code is NOT this purchase's.
    assert router._this_purchase("u1", sid, "Nykaa") is None
    time.sleep(0.01)
    router._remember_order("u1", _order("Nykaa", "SECOND", "r2"))
    assert router._this_purchase("u1", sid, "Nykaa")["vouchers"][0]["cardNumber"] == "SECOND"


def test_same_brand_twice_takes_the_one_after_the_screen_opened():
    router._remember_order("u1", _order("Swiggy", "OLD", "r1"))
    time.sleep(0.01)
    sid = router._open_session("u1", "Swiggy")
    assert router._this_purchase("u1", sid, "Swiggy") is None
    time.sleep(0.01)
    router._remember_order("u1", _order("Swiggy", "NEW", "r2"))
    assert router._this_purchase("u1", sid, "Swiggy")["vouchers"][0]["cardNumber"] == "NEW"


def test_someone_elses_session_is_ignored():
    sid = router._open_session("someone-else", "Nykaa")
    router._remember_order("u1", _order("Swiggy", "S", "r1"))
    # Falls back to the brand asked for: no Nykaa order, so nothing.
    assert router._this_purchase("u1", sid, "Nykaa") is None


def test_older_page_without_session_still_works():
    router._remember_order("u1", _order("Swiggy", "S", "r1"))
    assert router._this_purchase("u1", None, None)["vouchers"][0]["cardNumber"] == "S"
    assert router._this_purchase("u1", None, "swiggy")["vouchers"][0]["cardNumber"] == "S"


def test_resent_order_is_kept_once():
    router._remember_order("u1", _order("Swiggy", "S", "r1"))
    router._remember_order("u1", _order("Swiggy", "S", "r1"))
    assert len(router._recent_orders["u1"]) == 1


def test_in_store_link_sells_the_in_store_card():
    # Lifestyle has an online and an in-store card under one name.
    assert hubble_service.brand_by_slug("lifestyle")["works"] == ["ONLINE"]
    assert hubble_service.brand_by_slug("lifestyle", in_store=True)["works"] == ["OFFLINE"]
    assert hubble_service.buy_link("Lifestyle", 2000, "wa", in_store=True).endswith("/buy/lifestyle?amount=2000&src=wa&store=1")
    assert "store=" not in hubble_service.buy_link("Lifestyle", 2000, "wa")


def test_failed_save_is_reported(monkeypatch):
    s = buyer_service.get_settings()
    monkeypatch.setattr(s, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(s, "SUPABASE_SECRET_KEY", "x")
    monkeypatch.setattr(buyer_service.analytics_service, "fire", lambda e: None)

    class Down:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): raise httpx.ConnectError("down")
    monkeypatch.setattr(buyer_service.httpx, "AsyncClient", Down)
    assert asyncio.run(buyer_service.save_purchase(_order("Swiggy", "S", "r9"), "production")) is False


def test_hiccup_uses_last_good_copy(monkeypatch):
    good = {"status": "ACTIVE"}
    monkeypatch.setattr(hubble_service, "_products", {"b1": (time.time() - 700, good)})  # past the 10 min

    class Down:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(hubble_service.httpx, "AsyncClient", Down)
    assert asyncio.run(hubble_service._product("b1")) is good
    monkeypatch.setattr(hubble_service, "_products", {"b1": (time.time() - 4000, good)})  # too old
    assert asyncio.run(hubble_service._product("b1")) is None


def test_every_dealo_card_with_a_known_website_gets_it():
    lifestyle = [b for b in __import__("json").loads(PROD.read_text()) if b["name"] == "Lifestyle"]
    assert all(hubble_service.shop_url(b["id"]) == "https://lifestylestores.com" for b in lifestyle)


def test_hubble_env_typo_refuses_to_start(monkeypatch):
    from src.config import Settings
    assert Settings(HUBBLE_ENV=" Production").HUBBLE_ENV == "production"
    with pytest.raises(ValueError):
        Settings(HUBBLE_ENV="prod")
