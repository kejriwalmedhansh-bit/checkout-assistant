"""WhatsApp: "stop" is acted on, and every message in a webhook payload is
handled (not just the first of the first entry)."""
import asyncio

from src.services import whatsapp_service

PHONE = "919999999999"


def _run(text, monkeypatch, new_user=False, classification_type=None):
    calls = {"texts": [], "searched": [], "nudges": 0, "events": []}

    async def noop(*a, **k):
        return None

    async def fake_text(phone, body):
        calls["texts"].append(body)

    async def fake_search(phone, classification):
        calls["searched"].append(classification)

    async def fake_nudge(phone):
        calls["nudges"] += 1

    async def run_now(msg_id, work):
        await work

    monkeypatch.setattr(whatsapp_service.asyncio, "sleep", noop)
    monkeypatch.setattr(whatsapp_service, "send_text", fake_text)
    monkeypatch.setattr(whatsapp_service, "process_and_respond", fake_search)
    monkeypatch.setattr(whatsapp_service, "_send_state_aware_nudge", fake_nudge)
    monkeypatch.setattr(whatsapp_service, "_run_with_typing_keepalive", run_now)
    monkeypatch.setattr(whatsapp_service, "_track", lambda event, *a, **k: calls["events"].append(event))
    monkeypatch.setattr(whatsapp_service.analytics_service, "fire", lambda *a, **k: None)
    monkeypatch.setattr(whatsapp_service.session_store, "is_new_user", lambda phone: new_user)
    monkeypatch.setattr(whatsapp_service._search_rate_limiter, "allow", lambda phone: True)
    asyncio.run(whatsapp_service._process_text_message(PHONE, "wamid.1", text))
    return calls


def setup_function():
    whatsapp_service._opted_out.pop(PHONE)


def test_stop_gets_one_confirmation_and_no_nudge(monkeypatch):
    calls = _run("STOP", monkeypatch)
    assert calls["texts"] == [whatsapp_service.WHATSAPP_OPT_OUT_MSG]
    assert calls["nudges"] == 0
    assert whatsapp_service._opted_out.get(PHONE)


def test_first_time_stop_is_not_answered_with_a_welcome(monkeypatch):
    calls = _run("unsubscribe", monkeypatch, new_user=True)
    assert calls["texts"] == [whatsapp_service.WHATSAPP_OPT_OUT_MSG]


def test_filler_after_stop_is_met_with_silence(monkeypatch):
    _run("stop", monkeypatch)
    calls = _run("hi", monkeypatch)
    assert calls["texts"] == [] and calls["nudges"] == 0
    assert "WhatsApp Nudge Suppressed" in calls["events"]


def test_a_product_after_stop_lifts_it(monkeypatch):
    _run("stop", monkeypatch)
    calls = _run("boAt Airdopes 141", monkeypatch)
    assert len(calls["searched"]) == 1
    assert not whatsapp_service._opted_out.get(PHONE)
    assert "WhatsApp Opted Back In" in calls["events"]


def test_every_message_in_a_payload_is_handled(monkeypatch):
    seen = []

    async def fake_handle(msg):
        seen.append(msg["id"])

    monkeypatch.setattr(whatsapp_service, "_handle_message", fake_handle)
    body = {
        "entry": [
            {"changes": [
                {"value": {"messages": [{"id": "m1", "from": PHONE}, {"id": "m2", "from": PHONE}]}},
                {"value": {"statuses": []}},
            ]},
            {"changes": [{"value": {"messages": [{"id": "m3", "from": PHONE}]}}]},
        ]
    }
    asyncio.run(whatsapp_service.handle_incoming(body))
    assert seen == ["m1", "m2", "m3"]


def test_malformed_payload_is_swallowed():
    asyncio.run(whatsapp_service.handle_incoming({"entry": [{"changes": [{"value": None}]}]}))
    asyncio.run(whatsapp_service.handle_incoming({}))
