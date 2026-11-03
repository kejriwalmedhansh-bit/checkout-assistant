"""Tracking stays airtight: code and tracking-plan.json can't drift apart.

Fails when:
  - code fires an event name that isn't in tracking-plan.json
  - tracking-plan.json lists an event nothing fires
  - an event name is built at runtime instead of written literally
  - /go or /out stop redirecting, stop stamping ids, or leak a phone number
  - a voucher/card link in the data isn't allowed through /out

Run:  .venv/bin/python -m pytest tests/test_tracking_plan.py -q
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PLAN = json.loads((ROOT / "tracking-plan.json").read_text())
PLAN_EVENTS = set(PLAN["events"])

JS_DIRS = [ROOT / "react" / "src", ROOT / "extension" / "src"]
PY_DIRS = [ROOT / "src", ROOT / "scripts"]

# A call to one of our tracking functions, not a method on some other object
# (mixpanel.track inside the wrapper is the one place a variable is expected).
_JS_CALL = re.compile(r"(?<![\w.$])(track)\(\s*")
_JS_DEF = re.compile(r"function\s+track\s*\($")
_PY_CALL = re.compile(r"(?<![\w])(_track|whatsapp_event|build_event|import_event)\(\s*")
_LITERAL = re.compile(r"""(['"])([^'"\n]+)\1""")
# Wrappers pass their `event` parameter straight through; that's the only
# non-literal first argument allowed.
_PASS_THROUGH = re.compile(r"event\b")


def _files(dirs: list[Path], suffixes: tuple[str, ...]) -> list[Path]:
    out = []
    for d in dirs:
        if d.exists():
            out += [p for p in d.rglob("*") if p.suffix in suffixes and "node_modules" not in p.parts]
    return out


def _calls(path: Path, call_re: re.Pattern) -> list[tuple[int, str | None, str]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = []
    for m in call_re.finditer(text):
        before = text[max(0, m.start() - 20): m.start()]
        if re.search(r"(def|function)\s+$", before):
            continue
        rest = text[m.end(): m.end() + 200]
        line = text.count("\n", 0, m.start()) + 1
        lit = _LITERAL.match(rest)
        found.append((line, lit.group(2) if lit else None, rest[:40]))
    return found


def _all_calls():
    calls = []
    for p in _files(JS_DIRS, (".js", ".jsx")):
        calls += [(p, *c) for c in _calls(p, _JS_CALL)]
    for p in _files(PY_DIRS, (".py",)):
        calls += [(p, *c) for c in _calls(p, _PY_CALL)]
    return calls


def test_every_fired_event_is_in_the_plan():
    unknown = [
        f"{p.relative_to(ROOT)}:{line} fires '{name}'"
        for p, line, name, _ in _all_calls()
        if name is not None and name not in PLAN_EVENTS
    ]
    assert not unknown, "Add these to tracking-plan.json (or fix the name):\n" + "\n".join(unknown)


def test_event_names_are_literal():
    dynamic = [
        f"{p.relative_to(ROOT)}:{line} -> {rest!r}"
        for p, line, name, rest in _all_calls()
        if name is None and not _PASS_THROUGH.match(rest)
    ]
    assert not dynamic, "Event names must be written literally:\n" + "\n".join(dynamic)


def test_every_plan_event_is_fired_somewhere():
    corpus = "".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in _files(JS_DIRS, (".js", ".jsx")) + _files(PY_DIRS, (".py",))
    )
    unused = [e for e in sorted(PLAN_EVENTS) if f'"{e}"' not in corpus and f"'{e}'" not in corpus]
    assert not unused, "Listed in tracking-plan.json but never fired:\n" + "\n".join(unused)


def test_anonymous_events_never_carry_personal_properties():
    """Visitors without consent are counted on every event, stripped to an
    allow-list of page/deal facts. Nothing stored on the device, no ad click
    ids, no free text, nothing from the login."""
    text = (ROOT / "react/src/utils/analytics.js").read_text()
    block = re.search(r"ANONYMOUS_SAFE_PROPS = new Set\(\[(.*?)\]\)", text, re.S).group(1)
    allowed = set(re.findall(r"'([^']+)'", block))
    never = {"is_returning_visitor", "gclid", "fbclid", "ad_click_id", "note", "name", "phone", "email", "code", "pin",
             "dealo_user_id", "dealo_id", "$device_id", "$user_id", "ip"}
    assert not (allowed & never), allowed & never
    # Every allowed name is a property some web event in the plan actually has.
    plan_props = {p for e in PLAN["events"].values() if "web" in e["surfaces"] for k in e["properties"] for p in re.split(r",\s*", k)}
    assert allowed <= plan_props, allowed - plan_props
    # And the anonymous id is minted in memory, never read from storage.
    assert "VISIT_ID = `visit:${newId()}`" in text
    assert "ip: '0'" in text


# --- /go and /out -----------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from src.services import analytics_service

    sent: list[dict] = []
    monkeypatch.setattr(analytics_service, "fire", lambda payload: sent.append(payload))
    from src.application import app

    c = TestClient(app, follow_redirects=False)
    c.sent = sent
    return c


def _qs(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_go_stamps_ids_and_logs_click(client):
    did = str(uuid.uuid4())
    r = client.get("/go", params={"url": "https://www.croma.com/p/123", "surface": "web", "did": did, "ctx": "redeem_step"},
                   headers={"user-agent": "Mozilla/5.0 Chrome/120"})
    assert r.status_code == 302
    q = _qs(r.headers["location"])
    assert q["subid"] == did and q["subid3"] == "web" and len(q["subid2"]) == 16
    (event,) = client.sent
    props = event["properties"]
    assert event["event"] == "Shop Link Opened"
    assert props["$device_id"] == did and props["click_id"] == q["subid2"] and props["$insert_id"] == q["subid2"]
    assert props["ctx"] == "redeem_step" and props["is_bot"] is False and props["surface"] == "web"


def test_go_without_consent_is_anonymous(client):
    r = client.get("/go", params={"url": "https://www.croma.com/p/1"}, headers={"user-agent": "Mozilla/5.0"})
    assert _qs(r.headers["location"])["subid"] == "anon"
    props = client.sent[0]["properties"]
    assert props["distinct_id"] == "anonymous" and "$device_id" not in props and "ip" not in props


def test_go_rejects_junk_ids_and_flags_bots(client):
    r = client.get("/go", params={"url": "https://www.croma.com/", "did": "<script>", "surface": "evil"},
                   headers={"user-agent": "WhatsApp/2.23 A"})
    assert r.status_code == 302
    props = client.sent[0]["properties"]
    assert "$device_id" not in props and props["surface"] == "unknown" and props["is_bot"] is True


def test_go_still_redirects_when_mixpanel_is_down(monkeypatch):
    import httpx
    from fastapi.testclient import TestClient

    async def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.AsyncClient, "post", boom)
    from src.application import app

    r = TestClient(app, follow_redirects=False).get("/go", params={"url": "https://www.croma.com/"})
    assert r.status_code == 302


def test_out_allows_partners_and_refuses_others(client):
    ok = client.get("/out", params={"url": "https://www.gyftr.com/myntra", "kind": "voucher_site", "surface": "web"})
    assert ok.status_code == 302 and ok.headers["location"] == "https://www.gyftr.com/myntra"
    assert client.sent[0]["event"] == "Voucher Site Opened"
    card = client.get("/out", params={"url": "https://bitli.in/abc", "kind": "card_apply"})
    assert card.status_code == 302 and client.sent[1]["event"] == "Card Link Opened"
    assert client.get("/out", params={"url": "https://evil.example/phish"}).status_code == 400
    assert client.get("/out", params={"url": "https://gyftr.com.evil.example/"}).status_code == 400


def test_every_voucher_and_card_link_in_data_is_allowed():
    from src.api.routers.redirect import _host_allowed

    files = list((ROOT / "data").glob("*.json")) + list((ROOT / "db").glob("*.json")) + [ROOT / "react/src/data/allBrandDeals.json"]
    link_re = re.compile(r'"(source_url|voucher_url|apply_url)"\s*:\s*"(https?://[^"]+)"')
    hosts = set()
    for f in files:
        if f.exists():
            hosts |= {urlparse(m.group(2)).netloc for m in link_re.finditer(f.read_text(errors="ignore"))}
    deals = json.loads((ROOT / "react/src/data/allBrandDeals.json").read_text())
    hosts |= {urlparse(d["url"]).netloc for d in deals if d.get("url")}
    blocked = sorted(h for h in hosts if not _host_allowed(h))
    assert not blocked, f"Add to OUTBOUND_ALLOWED_HOSTS in src/constants.py: {blocked}"


# --- WhatsApp identity ------------------------------------------------------

def test_whatsapp_links_never_contain_the_phone():
    from src.services import whatsapp_service as ws

    phone = "919812345678"
    for url in (ws._affiliate_url("https://www.croma.com/", phone, "redeem_step"),
                ws._outbound_url("https://www.gyftr.com/x", phone, "voucher_site", "buy_voucher_step")):
        assert phone not in url
        assert _qs(url)["did"].startswith("wa-") and _qs(url)["surface"] == "whatsapp"


def test_whatsapp_events_carry_person_and_device():
    from src.services import analytics_service as a

    props = a.whatsapp_event("WhatsApp Search", "919812345678")["properties"]
    assert props["$user_id"] == props["distinct_id"] == "wa:919812345678"
    assert props["$device_id"] == a.whatsapp_device_id("919812345678")
    assert a.whatsapp_device_id("919812345678") == a.whatsapp_device_id("919812345678")


def _js_ref_code(visitor_id: str) -> str:
    """Mirror of refCode() in react/src/utils/whatsappLink.js."""
    n = int(visitor_id.replace("-", ""), 16)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out or "0"


@pytest.mark.parametrize("visitor_id", [str(uuid.uuid4()) for _ in range(20)] + ["00000000-0000-4000-8000-000000000001"])
def test_website_ref_round_trips(visitor_id):
    from src.services.whatsapp_service import extract_website_ref

    text = f"Hi! I'd like to try Dealo on WhatsApp. (ref {_js_ref_code(visitor_id)})"
    rest, found, greeting = extract_website_ref(text)
    assert found == visitor_id and greeting and "ref" not in rest


def test_website_ref_fallback_ids_and_plain_messages():
    from src.services.whatsapp_service import classify_input, extract_website_ref

    rest, found, greeting = extract_website_ref("Hi! I'd like to try Dealo on WhatsApp. (ref lq2x9a-k3j4h5g6)")
    assert found == "lq2x9a-k3j4h5g6" and greeting
    # The pre-filled greeting alone (visitor didn't consent, so no ref) must
    # not be searched as a product.
    assert extract_website_ref("Hi! I'd like to try Dealo on WhatsApp.") == ("Hi! I'd like to try Dealo on WhatsApp.", None, True)
    assert extract_website_ref("Samsung fridge ref RT28T3032S8")[1] is None
    rest, found, greeting = extract_website_ref("boAt Airdopes 141")
    assert found is None and not greeting and classify_input(rest)["type"] == "product_name"


# --- purchase sync ----------------------------------------------------------

def test_purchase_events_are_attributed_and_deduplicable():
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_affiliate_purchases as sync

    raw = {"id": 98765, "sub_id": "wa-abc123", "sub_id2": "c0ffee1234567890", "sub_id3": "whatsapp",
           "campaign_name": "Croma Retail", "sale_amount": "12,499.00", "commission": "187.49",
           "status": "Pending", "transaction_date": "2026-09-20 14:05:00"}
    sale = sync.normalize("cuelinks", raw)
    first, again = sync.to_events(sale), sync.to_events(sync.normalize("cuelinks", raw))
    assert [e["event"] for e in first] == ["Purchase Recorded", "Purchase Status Changed"]
    for a, b in zip(first, again):
        # Same insert id and time on every run -> Mixpanel keeps one copy.
        assert a["properties"]["$insert_id"] == b["properties"]["$insert_id"]
        assert a["properties"]["time"] == b["properties"]["time"]
        assert len(a["properties"]["$insert_id"]) <= 36
        assert a["properties"]["$device_id"] == "wa-abc123" and "token" not in a["properties"]
    props = first[0]["properties"]
    assert props["sale_amount"] == 12499.0 and props["commission"] == 187.49 and props["click_id"] == "c0ffee1234567890"
    validated = sync.to_events(sync.normalize("cuelinks", {**raw, "status": "validated"}))
    assert validated[1]["properties"]["$insert_id"] != first[1]["properties"]["$insert_id"]
    assert validated[0]["properties"]["$insert_id"] == first[0]["properties"]["$insert_id"]


def test_unattributed_purchase_is_kept_anonymously():
    sys.path.insert(0, str(ROOT / "scripts"))
    import sync_affiliate_purchases as sync

    events = sync.to_events(sync.normalize("inrdeals", {"transaction_id": "X1", "sub_id1": "anon", "sale_amount": 500, "status": "pending"}))
    assert all(e["properties"]["distinct_id"] == "anonymous-purchase" for e in events)


# --- vouchers Dealo sells itself (Hubble) -----------------------------------

def _hubble_order(**over):
    order = {"transactionReferenceId": "HB-9", "userId": "u1", "brandName": "Myntra", "amount": 1000,
             "discountAmount": 85, "orderStatus": "COMPLETED", "vouchers": [{"cardNumber": "SECRET", "cardPin": "1234"}]}
    return {**order, **over}


def test_completed_hubble_order_becomes_one_voucher_sold_event(monkeypatch):
    """A webhook Hubble retries must not count the sale twice, and the event
    must carry nothing that identifies the shopper or the voucher."""
    import asyncio

    from src.services import analytics_service, buyer_service

    sent: list[dict] = []
    monkeypatch.setattr(analytics_service, "fire", lambda payload: sent.append(payload))
    asyncio.run(buyer_service.save_purchase(_hubble_order(), "production"))
    asyncio.run(buyer_service.save_purchase(_hubble_order(), "production"))
    assert len(sent) == 2 and sent[0]["event"] == "Voucher Sold"
    a, b = (e["properties"] for e in sent)
    assert a["$insert_id"] == b["$insert_id"]  # Mixpanel keeps one copy
    assert a["seller"] == "hubble" and a["brand"] == "Myntra" and a["surface"] == "web"
    assert a["amount"] == 1000.0 and a["discount"] == 85.0 and a["discount_pct"] == 8.5
    assert a["seller_environment"] == "production" and a["distinct_id"] == "anonymous"
    blob = json.dumps(a)
    assert "u1" != a.get("buyer_key") and len(a["buyer_key"]) == 16
    assert "SECRET" not in blob and "1234" not in blob
    assert not any(k in a for k in ("code", "pin", "phone", "codes", "vouchers", "userId"))

    # A pending or failed order is a row in Supabase, not a sale in Mixpanel.
    asyncio.run(buyer_service.save_purchase(_hubble_order(ref="HB-2", orderStatus="PENDING"), "production"))
    asyncio.run(buyer_service.save_purchase(_hubble_order(transactionReferenceId=None), "production"))
    assert len(sent) == 2


def test_voucher_sold_joins_the_visit_that_opened_the_payment_screen(monkeypatch):
    import asyncio

    from src.api.routers import hubble as hubble_router
    from src.services import analytics_service, buyer_service

    sent: list[dict] = []
    monkeypatch.setattr(analytics_service, "fire", lambda payload: sent.append(payload))
    body = hubble_router.SessionRequest(id_token="x", name="A", merchant="Myntra", price=1000,
                                        dealo_id="3f2c1a9e-aaaa-4bbb-8ccc-123456789abc", src="wa", placement="shop_card")
    hubble_router._remember_attribution("u1", body)
    asyncio.run(buyer_service.save_purchase(_hubble_order(), "production", attribution=hubble_router._attribution_for("u1")))
    props = sent[0]["properties"]
    assert props["$device_id"] == "3f2c1a9e-aaaa-4bbb-8ccc-123456789abc" and props["distinct_id"].startswith("$device:")
    assert props["src"] == "wa" and props["placement"] == "shop_card" and props["merchant"] == "Myntra"
    # An unknown buyer, or a junk id, stays anonymous.
    assert hubble_router._attribution_for("nobody") == {}
    bad = hubble_router.SessionRequest(id_token="x", name="A", merchant="Myntra", price=1000, dealo_id="<script>")
    hubble_router._remember_attribution("u2", bad)
    asyncio.run(buyer_service.save_purchase(_hubble_order(transactionReferenceId="HB-3", userId="u2"), "production",
                                            attribution=hubble_router._attribution_for("u2")))
    assert "$device_id" not in sent[1]["properties"] and sent[1]["properties"]["distinct_id"] == "anonymous"
