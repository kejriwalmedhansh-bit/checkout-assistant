"""Website -> WhatsApp hand-off: "Send this to my WhatsApp" pre-fills what
the shopper typed plus "(deal <code>)", and the bot answers with that exact
comparison instead of searching again. An unknown code falls back to a
normal search of their words.

Run:  .venv/bin/python -m pytest tests/test_wa_handoff.py -q
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services import search_service, whatsapp_service  # noqa: E402

KEY = "3f9a2c1b7d" + "0" * 22  # a 32-character /routes id
RESULT = {"source": {"name": "Philips HD4815/01 Pop-Up Toaster"},
          "routes": {"recommended": {"merchant": "Shopy Vision", "final_cost": 1799}, "alternatives": []}}


def _remember(result=RESULT, key=KEY):
    job = search_service._RoutesJob(key)
    job.thumbnail = "https://img/toaster.jpg"
    job.unchecked = job.checked = result
    job.unchecked_ready.set()
    job.checked_ready.set()
    search_service._routes_jobs.set(key, job)
    return job


def test_code_is_read_and_removed():
    text, code = whatsapp_service.extract_handoff_code("Philips toaster (deal 3F9A2C1B7D)")
    assert (text, code) == ("Philips toaster", "3f9a2c1b7d")
    # Works alongside the visitor ref, in either order.
    text, _, _ = whatsapp_service.extract_website_ref("Philips toaster (deal 3f9a2c1b7d) (ref d1vvc9giuw13ws56fj1uboqda)")
    assert whatsapp_service.extract_handoff_code(text) == ("Philips toaster", "3f9a2c1b7d")
    # No code, or the wrong length: nothing taken.
    assert whatsapp_service.extract_handoff_code("Philips toaster") == ("Philips toaster", None)
    assert whatsapp_service.extract_handoff_code("x (deal 3f9a)")[1] is None


def test_lookup_finds_the_remembered_comparison():
    _remember()
    assert search_service.routes_for_handoff("3f9a2c1b7d") == (RESULT, "https://img/toaster.jpg")
    assert search_service.routes_for_handoff("0000000000") is None
    assert search_service.routes_for_handoff("3f9a") is None
    search_service._routes_jobs.pop(KEY)


def test_failed_comparison_is_not_handed_off():
    _remember({"error": "boom"})
    assert search_service.routes_for_handoff("3f9a2c1b7d") is None
    search_service._routes_jobs.pop(KEY)


def _run(text, monkeypatch, new_user=False):
    calls = {"sent": [], "searched": [], "texts": [], "events": []}

    async def noop(*a, **k):
        return None

    async def fake_send_result(phone, result, query, thumbnail=None, candidates=None):
        calls["sent"].append((result, query, thumbnail))

    async def fake_search(phone, classification):
        calls["searched"].append(classification)

    async def fake_text(phone, body):
        calls["texts"].append(body)

    async def run_now(msg_id, work):
        await work

    monkeypatch.setattr(whatsapp_service.asyncio, "sleep", noop)
    monkeypatch.setattr(whatsapp_service, "_send_routes_result", fake_send_result)
    monkeypatch.setattr(whatsapp_service, "process_and_respond", fake_search)
    monkeypatch.setattr(whatsapp_service, "send_text", fake_text)
    monkeypatch.setattr(whatsapp_service, "_run_with_typing_keepalive", run_now)
    monkeypatch.setattr(whatsapp_service, "_track", lambda event, *a, **k: calls["events"].append((event, k)))
    monkeypatch.setattr(whatsapp_service.analytics_service, "fire", lambda *a, **k: None)
    monkeypatch.setattr(whatsapp_service.session_store, "is_new_user", lambda phone: new_user)
    asyncio.run(whatsapp_service._process_text_message("919999999999", "wamid.1", text))
    return calls


def test_bot_sends_the_exact_result_without_searching(monkeypatch):
    _remember()
    calls = _run("Philips toaster (deal 3f9a2c1b7d) (ref d1vvc9giuw13ws56fj1uboqda)", monkeypatch)
    assert calls["sent"] == [(RESULT, "Philips toaster", "https://img/toaster.jpg")]
    assert calls["searched"] == []
    assert ("WhatsApp Website Handoff", {"found": True, "query": "Philips toaster"}) in calls["events"]
    search_service._routes_jobs.pop(KEY)


def test_first_time_number_gets_welcome_then_result(monkeypatch):
    _remember()
    calls = _run("Philips toaster (deal 3f9a2c1b7d)", monkeypatch, new_user=True)
    assert calls["texts"] == [whatsapp_service.WHATSAPP_ONBOARDING_MSG]
    assert len(calls["sent"]) == 1 and calls["searched"] == []
    search_service._routes_jobs.pop(KEY)


def test_expired_code_searches_their_words(monkeypatch):
    calls = _run("Philips toaster (deal 3f9a2c1b7d)", monkeypatch)
    assert calls["sent"] == []
    assert len(calls["searched"]) == 1
    assert "(deal" not in str(calls["searched"][0])
    assert ("WhatsApp Website Handoff", {"found": False, "query": "Philips toaster"}) in calls["events"]


def test_different_product_after_handoff_searches_their_words(monkeypatch):
    searched = []

    async def fake_search(phone, classification):
        searched.append(classification)

    async def run_now(msg_id, work):
        await work

    monkeypatch.setattr(whatsapp_service, "process_and_respond", fake_search)
    monkeypatch.setattr(whatsapp_service, "_run_with_typing_keepalive", run_now)
    monkeypatch.setattr(whatsapp_service.session_store, "get_session",
                        lambda phone: {"routes": RESULT["routes"], "candidates": [], "query": "Philips toaster"})
    asyncio.run(whatsapp_service.handle_pick_again("919999999999"))
    assert searched == [{"type": "product_name", "query": "Philips toaster"}]
