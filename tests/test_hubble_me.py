"""GET /hubble/me: the shopper's own purchases and total saved, for the
"Your account" screen. Codes are never part of it.

Run:  .venv/bin/python -m pytest tests/test_hubble_me.py -q
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.routers import hubble  # noqa: E402


@pytest.fixture
def logged_in(monkeypatch):
    async def verify(token):
        if token != "good":
            raise ValueError("login not valid")
        return {"uid": "u1", "phone": "+919999999999"}
    monkeypatch.setattr(hubble.buyer_service, "verify_login", verify)


def test_totals_and_list(logged_in, monkeypatch):
    seen = {}

    async def rows(uid, env):
        seen["uid"], seen["env"] = uid, env
        return [
            {"brand": "Swiggy", "amount": 250, "discount": 7.5, "created_at": "2026-11-11T16:28:12+00:00"},
            {"brand": "Dominos", "amount": "1161", "discount": "185.76", "created_at": "2026-11-08T13:14:02+00:00"},
        ]
    monkeypatch.setattr(hubble.buyer_service, "purchases_for", rows)
    out = asyncio.run(hubble.me("Bearer good"))
    assert seen["uid"] == "u1"
    assert seen["env"] == hubble.get_settings().HUBBLE_ENV
    assert out["total_saved"] == 193.26
    assert out["total_bought"] == 1411
    assert [p["brand"] for p in out["purchases"]] == ["Swiggy", "Dominos"]
    assert all("code" not in p and "pin" not in p for p in out["purchases"])


def test_bad_login_is_refused(logged_in):
    with pytest.raises(HTTPException) as err:
        asyncio.run(hubble.me("Bearer bad"))
    assert err.value.status_code == 401


def test_database_down_is_an_error_not_an_empty_list(logged_in, monkeypatch):
    async def broken(uid, env):
        raise RuntimeError("supabase down")
    monkeypatch.setattr(hubble.buyer_service, "purchases_for", broken)
    with pytest.raises(HTTPException) as err:
        asyncio.run(hubble.me("Bearer good"))
    assert err.value.status_code == 503


def test_login_without_buying_saves_the_buyer(logged_in, monkeypatch):
    saved = {}

    async def save(uid, phone, name, email, optin):
        saved.update(uid=uid, phone=phone, name=name, email=email, optin=optin)
    monkeypatch.setattr(hubble.buyer_service, "save_buyer", save)
    body = hubble.AccountRequest(id_token="good", name="  Asha  ", email="  ")
    assert asyncio.run(hubble.account(body)) == {"ok": True}
    # Blank email is left out; logging in never ticks the deals box.
    assert saved == {"uid": "u1", "phone": "+919999999999", "name": "Asha", "email": None, "optin": False}


def test_login_without_buying_needs_a_real_login(logged_in):
    with pytest.raises(HTTPException) as err:
        asyncio.run(hubble.account(hubble.AccountRequest(id_token="bad", name="Asha")))
    assert err.value.status_code == 401


def test_purchases_carry_the_hubble_ref(logged_in, monkeypatch):
    async def rows(uid, env):
        return [{"brand": "AJIO", "amount": 1000, "discount": 65, "created_at": "2026-11-03", "hubble_ref": "01M6GPSJJ7SY6YMY2BTCAQT9CR"}]
    monkeypatch.setattr(hubble.buyer_service, "purchases_for", rows)
    assert asyncio.run(hubble.me("Bearer good"))["purchases"][0]["ref"] == "01M6GPSJJ7SY6YMY2BTCAQT9CR"


def test_card_link_is_for_the_logged_in_shopper_only(logged_in, monkeypatch):
    seen = {}

    def token(uid, phone, name, email):
        seen.update(uid=uid, phone=phone)
        return "jwt"
    monkeypatch.setattr(hubble.hubble_service, "sso_token", token)
    one = asyncio.run(hubble.card("01M6GPSJJ7SY6YMY2BTCAQT9CR", "Bearer good"))["url"]
    assert "/transaction/01M6GPSJJ7SY6YMY2BTCAQT9CR?" in one and "token=jwt" in one
    assert seen == {"uid": "u1", "phone": "+919999999999"}
    # No ref, or anything that isn't a Hubble order id: the whole list.
    assert "/transactions?" in asyncio.run(hubble.card(None, "Bearer good"))["url"]
    assert "/transactions?" in asyncio.run(hubble.card("../../evil", "Bearer good"))["url"]
    with pytest.raises(HTTPException) as err:
        asyncio.run(hubble.card(None, "Bearer bad"))
    assert err.value.status_code == 401
