"""WhatsApp business logic — input classification, pipeline dispatch, message
formatting, and Meta Graph send calls.

Consolidates the old whatsapp/{classifier,formatter,webhook,session_store}.py.

Fixes applied during the port:
  - Bug #1: the formatter now reads the pipeline voucher schema
    (voucher["merchant"], voucher["upi"]["pct"/"voucher_amount"],
    voucher["voucher_url"]) instead of the stale brand/best_discount/... keys.
  - Bug #5: the dead inner _headers() helpers are gone.
  - R7: WhatsApp settings are read lazily via get_settings() inside the send
    helpers, so the app boots even without WhatsApp configured.
"""
from __future__ import annotations

import asyncio
import re

import httpx

from ..cache import session_store
from ..config import get_settings
from ..constants import (
    WHATSAPP_CHECKING_MSG,
    WHATSAPP_DEAD_END_MSG,
    WHATSAPP_GRAPH_BASE,
    WHATSAPP_GRAPH_VERSION,
    WHATSAPP_NO_ALTERNATIVES_MSG,
    WHATSAPP_NUDGE_MSG,
    WHATSAPP_ONBOARDING_MSG,
    WHATSAPP_SESSION_EXPIRED_MSG,
)
from . import search_service

# ── input classification (ported from whatsapp/classifier.py) ───────────────────

URL_RE = re.compile(r"https?://\S+")

NOISE_PHRASES = {
    "hi", "hii", "hiii", "hello", "hey", "yo", "sup",
    "thanks", "thank you", "thx", "ty",
    "ok", "okay", "k", "kk",
    "test", "testing",
    "who are you", "what is this", "what are you", "how does this work",
    "help", "start", "menu",
}


def classify_input(text: str) -> dict:
    if not text or not text.strip():
        return {"type": "unparseable", "reason": "empty"}
    cleaned = text.strip()
    url_match = URL_RE.search(cleaned)
    if url_match:
        return {"type": "url", "url": url_match.group(0)}
    lowered = re.sub(r"[!.?,]+$", "", cleaned.lower()).strip()
    if lowered in NOISE_PHRASES:
        return {"type": "unparseable", "reason": "noise_phrase"}
    if len(cleaned) < 3:
        return {"type": "unparseable", "reason": "too_short"}
    if not re.search(r"[a-zA-Z0-9]", cleaned):
        return {"type": "unparseable", "reason": "no_alphanumeric_content"}
    return {"type": "product_name", "query": cleaned}


# ── formatting (bug #1 fixed to the pipeline voucher schema) ─────────────────────

def format_recommended(route: dict) -> str:
    lines = []

    title = route.get("title", "")
    merchant = route.get("merchant", "")
    listed_price = route.get("listed_price", 0)
    final_cost = route.get("final_cost", 0)
    voucher = route.get("voucher")
    card_fomo = route.get("card_fomo")
    sellers = route.get("sellers", [])

    lines.append(f"*{title}* — Best way to buy ⭐")
    lines.append("")
    lines.append(f"🏪 *{merchant}*")

    if listed_price and final_cost and final_cost < listed_price:
        savings = listed_price - final_cost
        lines.append(f"💰 Final cost: ₹{final_cost:,.0f} _(was ₹{listed_price:,.0f})_")
        lines.append(f"✅ You save: ₹{savings:,.0f}")
    else:
        lines.append(f"💰 Final cost: ₹{final_cost:,.0f}")

    if sellers:
        link = sellers[0].get("link", "")
        if link:
            lines.append(f"🔗 {link}")

    if voucher:
        brand = voucher.get("merchant", "")
        upi = voucher.get("upi", {})
        discount = upi.get("pct", 0)
        denomination = upi.get("voucher_amount", 0)
        lines.append("")
        lines.append(f"🎟 *Gyftr Voucher — {brand}*")
        lines.append(f"Buy ₹{denomination:,.0f} voucher at {discount}% off before checkout")
        redeem_url = voucher.get("voucher_url", "")
        if redeem_url:
            lines.append(f"Buy voucher: {redeem_url}")

    if card_fomo:
        card_name = card_fomo.get("card_name", "")
        extra_saving = card_fomo.get("actual_saving", 0)
        final_with_card = card_fomo.get("final_cost_with_card", 0)
        lines.append("")
        lines.append(f"💳 Have an *{card_name}* card?")
        lines.append(f"Pay with it at checkout to save an extra ₹{extra_saving:,.0f}")
        lines.append(f"Your final cost: ₹{final_with_card:,.0f}")

    return "\n".join(lines) + "\n"


# ── Meta Graph send helpers (R7: settings read lazily) ───────────────────────────

def _graph_config() -> tuple[str, dict]:
    settings = get_settings()
    api_url = (
        f"{WHATSAPP_GRAPH_BASE}/{WHATSAPP_GRAPH_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    return api_url, headers


async def send_text(phone: str, text: str) -> None:
    api_url, headers = _graph_config()
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(api_url, headers=headers, json=payload)
        print(f"[WhatsApp Send] Status: {r.status_code} | Body: {r.text}")


async def send_with_alternatives_button(phone: str, text: str) -> None:
    api_url, headers = _graph_config()
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "see_alternatives", "title": "See other routes"}}
                ]
            },
        },
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(api_url, headers=headers, json=payload)
        print(f"[WhatsApp Send] Status: {r.status_code} | Body: {r.text}")


def _truncate(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1] + "…"


async def send_list_message(phone: str, body_text: str, button_text: str, rows: list[dict]) -> None:
    """Meta interactive List Message — up to 10 rows, each {id, title, description}.
    The tapped row's id comes back as msg["interactive"]["list_reply"]["id"]."""
    api_url, headers = _graph_config()
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": [{"title": "Options", "rows": rows}],
            },
        },
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(api_url, headers=headers, json=payload)
        print(f"[WhatsApp Send] Status: {r.status_code} | Body: {r.text}")


# ── dispatch ─────────────────────────────────────────────────────────────────────

async def _send_routes_for_token(phone: str, product_token: str, query: str) -> None:
    result = await asyncio.to_thread(search_service.build_routes_for_token, product_token, query)
    routes = result.get("routes", {})
    recommended = routes.get("recommended")
    if not recommended:
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        return
    session_store.set_session(phone, {"routes": routes})
    msg = format_recommended(recommended)
    if routes.get("alternatives"):
        await send_with_alternatives_button(phone, msg)
    else:
        await send_text(phone, msg)


async def process_and_respond(phone: str, classification: dict) -> None:
    """Step 1: search candidates and ask the user to confirm the exact
    product (same picker the web two-step flow uses) — same pattern as
    handle_alternative_selection, just one step earlier in the flow."""
    try:
        query = classification.get("query") or classification.get("url")
        listing = await asyncio.to_thread(search_service.search_candidates, query)
        products = listing.get("products") or []
        if not products:
            await send_text(phone, WHATSAPP_DEAD_END_MSG)
            return

        if len(products) == 1:
            await _send_routes_for_token(phone, products[0]["product_token"], query)
            return

        session_store.set_session(phone, {"candidates": products, "query": query})
        rows = []
        for i, p in enumerate(products[:10]):
            price = p.get("price")
            desc = f"₹{price:,.0f}" if price else (p.get("source") or "")
            rows.append({
                "id": f"prod_{i}",
                "title": _truncate(p.get("title") or f"Option {i + 1}", 24),
                "description": _truncate(desc, 72),
            })
        await send_list_message(
            phone,
            body_text="Which one is it? Tap to confirm the exact product:",
            button_text="Select product",
            rows=rows,
        )
    except Exception as e:
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        print(f"[Webhook] Error for {phone}: {e}")


async def handle_product_selection(phone: str, reply_id: str) -> None:
    session = session_store.get_session(phone)
    if not session:
        await send_text(phone, WHATSAPP_SESSION_EXPIRED_MSG)
        return
    candidates = session.get("candidates", [])
    query = session.get("query", "")
    try:
        idx = int(reply_id.split("_", 1)[1])
        chosen = candidates[idx]
    except (ValueError, IndexError):
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        return
    await _send_routes_for_token(phone, chosen["product_token"], query)


async def handle_alternatives(phone: str) -> None:
    session = session_store.get_session(phone)
    if not session:
        await send_text(phone, WHATSAPP_SESSION_EXPIRED_MSG)
        return
    alternatives = session.get("routes", {}).get("alternatives", [])
    if not alternatives:
        await send_text(phone, WHATSAPP_NO_ALTERNATIVES_MSG)
        return
    rows = []
    for i, alt in enumerate(alternatives[:3]):
        final_cost = alt.get("final_cost")
        desc = f"₹{final_cost:,.0f}" if final_cost else ""
        voucher = alt.get("voucher")
        if voucher:
            desc += f" · Gyftr voucher {voucher['upi']['pct']}% off"
        rows.append({
            "id": f"alt_{i}",
            "title": _truncate(alt.get("merchant") or f"Option {i + 1}", 24),
            "description": _truncate(desc, 72),
        })
    await send_list_message(
        phone,
        body_text="Other ways to buy this — pick one to see the full route:",
        button_text="View options",
        rows=rows,
    )


async def handle_alternative_selection(phone: str, reply_id: str) -> None:
    """A picked alternative is promoted to the same full detail the
    recommended route gets — rendered through format_recommended(), not the
    brief format_alternative() summary."""
    session = session_store.get_session(phone)
    if not session:
        await send_text(phone, WHATSAPP_SESSION_EXPIRED_MSG)
        return
    alternatives = session.get("routes", {}).get("alternatives", [])
    try:
        idx = int(reply_id.split("_", 1)[1])
        chosen = alternatives[idx]
    except (ValueError, IndexError):
        await send_text(phone, WHATSAPP_NO_ALTERNATIVES_MSG)
        return
    await send_text(phone, format_recommended(chosen))


async def handle_incoming(body: dict) -> None:
    """Parse a Meta webhook payload and dispatch. Swallows malformed payloads."""
    try:
        entry = body["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return
        msg = messages[0]
        phone = msg["from"]
        msg_type = msg.get("type")

        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype = interactive.get("type")
            if itype == "button_reply":
                reply_id = interactive["button_reply"]["id"]
                if reply_id == "see_alternatives":
                    asyncio.create_task(handle_alternatives(phone))
            elif itype == "list_reply":
                reply_id = interactive["list_reply"]["id"]
                if reply_id.startswith("alt_"):
                    asyncio.create_task(handle_alternative_selection(phone, reply_id))
                elif reply_id.startswith("prod_"):
                    asyncio.create_task(handle_product_selection(phone, reply_id))
            return

        if msg_type != "text":
            await send_text(phone, WHATSAPP_NUDGE_MSG)
            return

        text = msg["text"]["body"]
        is_new = session_store.is_new_user(phone)
        if is_new:
            await send_text(phone, WHATSAPP_ONBOARDING_MSG)

        classification = classify_input(text)
        if classification["type"] == "unparseable":
            if not is_new:
                await send_text(phone, WHATSAPP_NUDGE_MSG)
            return

        await send_text(phone, WHATSAPP_CHECKING_MSG)
        asyncio.create_task(process_and_respond(phone, classification))
    except (KeyError, IndexError):
        pass
