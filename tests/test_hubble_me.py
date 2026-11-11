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
