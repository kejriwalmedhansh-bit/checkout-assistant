"""Where a buyer came from, kept on their record and on each purchase, and
their own answer to "How did you hear about Dealo?".

Run:  .venv/bin/python -m pytest tests/test_buyer_source.py -q
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.routers import hubble  # noqa: E402
from src.services import buyer_service  # noqa: E402

ORDER = {"transactionReferenceId": "HB-1", "userId": "u1", "brandName": "Dominos", "amount": 400,
         "discountAmount": 64, "orderStatus": "COMPLETED"}
SOURCE = {"utm_source": "instagram", "utm_medium": "short_link", "utm_campaign": "pvr-reel",
          "referrer_domain": "l.instagram.com", "landing_page": "/ig/pvr-reel"}


@pytest.fixture
def supabase(monkeypatch):
    """A stand-in Supabase: records every request, answers from `reply`."""
    calls: list[httpx.Request] = []
    box = SimpleNamespace(calls=calls, reply=lambda request: httpx.Response(201))
    real = httpx.AsyncClient

    def client(**kwargs):
        def handler(request):
            calls.append(request)
            return box.reply(request)
        return real(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(buyer_service.httpx, "AsyncClient", client)
    monkeypatch.setattr(buyer_service, "get_settings",
                        lambda: SimpleNamespace(SUPABASE_URL="https://db.test", SUPABASE_SECRET_KEY="k"))
    monkeypatch.setattr(buyer_service.analytics_service, "fire", lambda payload: None)
    return box


def test_purchase_row_carries_the_visit_source(supabase):
    assert asyncio.run(buyer_service.save_purchase(ORDER, "production", attribution=SOURCE))
    row = json.loads(supabase.calls[0].content)
    assert row["utm_source"] == "instagram" and row["utm_campaign"] == "pvr-reel"
    assert row["landing_page"] == "/ig/pvr-reel" and row["brand"] == "Dominos"


def test_purchase_still_saves_when_the_source_columns_are_missing(supabase):
    """Backend deployed before the database change: the sale must not be lost."""
    supabase.reply = lambda request: httpx.Response(400 if b"utm_source" in request.content else 201,
                                                    json={"message": "column utm_source does not exist"})
    assert asyncio.run(buyer_service.save_purchase(ORDER, "production", attribution=SOURCE))
    assert len(supabase.calls) == 2
    assert "utm_source" not in json.loads(supabase.calls[1].content)


def test_purchase_with_no_known_source_sends_no_source_columns(supabase):
    """A resent webhook after a restart must not blank a source saved earlier."""
    assert asyncio.run(buyer_service.save_purchase(ORDER, "production", attribution={}))
    assert not set(json.loads(supabase.calls[0].content)) & set(SOURCE)


def test_first_source_is_written_only_where_none_is_kept(supabase):
    asyncio.run(buyer_service.note_first_source("u1", SOURCE))
    request = supabase.calls[0]
    assert request.method == "PATCH"
    assert request.url.params["firebase_uid"] == "eq.u1" and request.url.params["first_source_at"] == "is.null"
    row = json.loads(request.content)
    assert row["first_utm_source"] == "instagram" and row["first_landing_page"] == "/ig/pvr-reel"

    # Nothing known about the visit: nothing is written.
    asyncio.run(buyer_service.note_first_source("u1", {"utm_source": None}))
    assert len(supabase.calls) == 1


def test_first_source_never_fails_a_login(supabase):
    supabase.reply = lambda request: httpx.Response(400, json={"message": "no such column"})
    asyncio.run(buyer_service.note_first_source("u1", SOURCE))  # no exception


def test_heard_from_is_asked_until_answered(supabase):
    supabase.reply = lambda request: httpx.Response(200, json=[{"heard_from": None}])
    assert asyncio.run(buyer_service.should_ask_heard_from("u1")) is True
    supabase.reply = lambda request: httpx.Response(200, json=[{"heard_from": "friend"}])
    assert asyncio.run(buyer_service.should_ask_heard_from("u1")) is False
    # Column missing or database down: never ask on a guess.
    supabase.reply = lambda request: httpx.Response(400, json={"message": "no such column"})
    assert asyncio.run(buyer_service.should_ask_heard_from("u1")) is False


def test_heard_from_accepts_only_the_listed_answers(supabase, monkeypatch):
    async def verify(token):
        return {"uid": "u1", "phone": "+919999999999"}
    monkeypatch.setattr(hubble.buyer_service, "verify_login", verify)
    out = asyncio.run(hubble.heard_from(hubble.HeardFromRequest(id_token="good", choice="friend")))
    assert out == {"ok": True}
    assert json.loads(supabase.calls[0].content)["heard_from"] == "friend"
    with pytest.raises(HTTPException) as err:
        asyncio.run(hubble.heard_from(hubble.HeardFromRequest(id_token="good", choice="<script>")))
    assert err.value.status_code == 422


def test_sale_event_names_the_post_that_brought_the_buyer():
    body = hubble.SessionRequest(id_token="x", name="A", merchant="Dominos", price=400, **SOURCE)
    hubble._remember_attribution("u-camp", body)
    event = buyer_service.voucher_sold_event({**ORDER, "userId": "u-camp"}, "production", hubble._attribution_for("u-camp"))
    assert event["properties"]["utm_campaign"] == "pvr-reel" and event["properties"]["utm_medium"] == "short_link"
