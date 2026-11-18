"""The server keeps Hubble's list and popular rates current by itself
(18 Nov 2026: the list file was three weeks old and new vouchers like Zudio
couldn't be sold until someone refreshed it and deployed).

Run:  .venv/bin/python -m pytest tests/test_hubble_keep_current.py -q
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services import hubble_service as h  # noqa: E402

OLD = [
    {"id": "a", "name": "Myntra", "brand_key": "myntra", "works": ["ONLINE"], "add_voucher_url": None},
    {"id": "z", "name": "Zepto", "brand_key": "zepto", "works": ["ONLINE"], "add_voucher_url": None},
]


def _listing(*items):
    return {"data": [{"products": [
        {"id": i, "type": "VOUCHER", "brandKey": k, "voucherProduct": {"title": t, "status": "ACTIVE"}} for i, t, k in items
    ]}]}


def _client(listing, pages):
    """A stand-in for Hubble: the listing, and each voucher's page (a dict,
    an int status, or an exception)."""
    class Resp:
        def __init__(self, status, body):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("x", request=httpx.Request("GET", "http://h"), response=None)

    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def get(self, url, params=None, **k):
            if url.endswith("/search"):
                return Resp(200, listing)
            page = pages[url.rsplit("/", 1)[1]]
            if isinstance(page, Exception):
                raise page
            if isinstance(page, int):
                return Resp(page, {})
            return Resp(200, page)
    return Client


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(h.get_settings(), "HUBBLE_CLIENT_ID", "dealo-test-id")
    monkeypatch.setattr(h, "_live", {"brands": None, "index": None, "at": 0.0})
    monkeypatch.setattr(h, "catalogue_brands", lambda: h._live["brands"] if h._live["brands"] is not None else list(OLD))


def test_new_voucher_is_sellable_the_same_day(monkeypatch):
    zudio = {"status": "ACTIVE", "voucherProductMetadata": {"howToUseSteps": [{"retailMode": "OFFLINE"}]}}
    monkeypatch.setattr(h.httpx, "AsyncClient", _client(
        _listing(("a", "Myntra", "myntra"), ("z", "Zepto", "zepto"), ("n", "Zudio", "zudio")), {"n": zudio}))
    out = asyncio.run(h.refresh_catalogue())
    assert out["added"] == ["Zudio"] and out["removed"] == []
    assert h.brand_for("Zudio", in_store=True)["id"] == "n"


def test_listing_is_the_answer(monkeypatch):
    # Read with Dealo's id, Hubble's listing is what Dealo may sell: a voucher
    # off it is gone (18 Nov: Zepto only looked gone when read without the id).
    monkeypatch.setattr(h.httpx, "AsyncClient", _client(_listing(("a", "Myntra", "myntra"), ("b", "Nykaa", "nykaa")),
                                                         {"b": {"status": "ACTIVE"}}))
    out = asyncio.run(h.refresh_catalogue())
    assert out["removed"] == ["Zepto"] and out["added"] == ["Nykaa"]


def test_new_voucher_that_errors_waits(monkeypatch):
    monkeypatch.setattr(h.httpx, "AsyncClient", _client(
        _listing(("a", "Myntra", "myntra"), ("z", "Zepto", "zepto"), ("n", "Zudio", "zudio")),
        {"n": httpx.ReadTimeout("slow")}))
    out = asyncio.run(h.refresh_catalogue())
    assert out["removed"] == [] and out["added"] == []


def test_never_read_without_dealos_id(monkeypatch):
    monkeypatch.setattr(h.get_settings(), "HUBBLE_CLIENT_ID", "")
    with pytest.raises(RuntimeError):
        asyncio.run(h.fetch_catalogue())


def test_a_much_smaller_read_is_not_trusted(monkeypatch):
    big = [{"id": str(i), "name": f"Shop {i}", "brand_key": "", "works": ["ONLINE"]} for i in range(100)]
    monkeypatch.setattr(h, "catalogue_brands", lambda: big)
    monkeypatch.setattr(h.httpx, "AsyncClient", _client(_listing(("1", "Shop 1", "")), {str(i): 404 for i in range(100)}))
    assert asyncio.run(h.refresh_catalogue())["kept_old"] is True
    assert h._live["brands"] is None


def test_popular_vouchers_are_read_again_before_they_expire(monkeypatch):
    read = []

    async def fake_product(brand_id, background=False):
        read.append((brand_id, background))
    monkeypatch.setattr(h, "_product", fake_product)
    now = time.time()
    monkeypatch.setattr(h, "_looked_up", {"hot": now - 60, "cold": now - 2 * 24 * 3600, "fresh": now})
    monkeypatch.setattr(h, "_products", {"hot": (now - 500, {}), "fresh": (now - 10, {})})
    assert asyncio.run(h.refresh_popular()) == 1
    assert read == [("hot", True)] and "cold" not in h._looked_up


def test_background_read_does_not_count_as_interest(monkeypatch):
    monkeypatch.setattr(h, "_looked_up", {})
    monkeypatch.setattr(h, "_products", {"x": (time.time(), {"status": "ACTIVE"})})
    asyncio.run(h._product("x"))
    assert "x" in h._looked_up
    h._looked_up.clear()

    class Down:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, *a, **k): raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(h.httpx, "AsyncClient", Down)
    # A failed early re-read keeps the good copy.
    assert asyncio.run(h._product("x", background=True)) == {"status": "ACTIVE"}
    assert h._looked_up == {}
