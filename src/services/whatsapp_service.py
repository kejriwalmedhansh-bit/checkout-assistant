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
from urllib.parse import quote

import httpx

from ..cache import session_store
from ..config import get_settings
from ..constants import (
    CUELINKS_BASE,
    KNOWN_BRANDS,
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


def _affiliate_url(link: str) -> str:
    """Cuelinks wrapper for merchant store links — mirrors the web frontend's
    affiliateUrl(). Deliberately NOT applied to Gyftr voucher links."""
    if not link:
        return link
    settings = get_settings()
    return CUELINKS_BASE.format(cid=settings.CUELINKS_CID, url=quote(link, safe=""))

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

def format_recommended(route: dict, label: str = "RECOMMENDED ROUTE") -> str:
    """Text body only — no raw URLs. Store/voucher links go out as separate
    tappable CTA buttons (see _route_links + send_cta_url) instead of pasted
    text, so they read as clean buttons rather than a chaotic long link.
    Emoji kept only where they mark a distinct section (voucher/card), not as
    decoration on every line — bold/structure carries the "eye-catching" job.
    `label` lets a promoted alternative say "ALTERNATIVE ROUTE #N" instead of
    "RECOMMENDED ROUTE" (see handle_alternative_selection)."""
    lines = []

    title = route.get("title", "")
    merchant = route.get("merchant", "")
    listed_price = route.get("listed_price", 0)
    final_cost = route.get("final_cost", 0)
    voucher = route.get("voucher")
    card_fomo = route.get("card_fomo")
    in_store = bool(voucher and voucher.get("offline_only"))
    if in_store:
        # search_service tags the merchant "{name} (in-store)" to keep it
        # distinct from the online listing — redundant here since the steps
        # below already say "in-store" explicitly.
        merchant = merchant.replace(" (in-store)", "")

    lines.append(f"*{title}*")
    lines.append(f"*{label}*")
    lines.append("")
    lines.append(f"*{merchant}*")

    if listed_price and final_cost and final_cost < listed_price:
        savings = listed_price - final_cost
        pct = round((savings / listed_price) * 100) if listed_price else 0
        lines.append(f"Final cost: *₹{final_cost:,.0f}* ~₹{listed_price:,.0f}~")
        lines.append("")
        lines.append(f"*YOU SAVE ₹{savings:,.0f} ({pct}% OFF)* ✅")
    else:
        lines.append(f"Final cost: *₹{final_cost:,.0f}*")

    lines.append("")
    lines.append("*How to buy:*")
    if voucher:
        brand = voucher.get("merchant") or merchant
        upi = voucher.get("upi", {})
        discount = upi.get("pct", 0)
        denomination = upi.get("voucher_amount", 0)
        remainder = upi.get("remainder", 0)
        # Gyftr only sells fixed denominations — show the real breakdown
        # (e.g. "8x Rs 5,000 + 1x Rs 2,000") when more than one voucher is
        # needed, since "buy a Rs X voucher" isn't literally purchasable.
        denom_breakdown = upi.get("denomination_breakdown") or []
        voucher_word = "voucher" if sum(b.get("count", 0) for b in denom_breakdown) <= 1 else "vouchers"
        breakdown = upi.get("purchase_breakdown") or f"₹{denomination:,.0f}"
        lines.append(f"1. Buy {breakdown} {brand} {voucher_word} → UPI → {discount}% off")
        if in_store:
            lines.append(f"2. Head to nearest {merchant} store")
            lines.append(
                f"3. Show voucher at checkout → pay remaining ₹{remainder:,.0f} in-store"
                if remainder else "3. Show voucher at checkout → full order covered"
            )
        else:
            lines.append(f"2. Add item to {merchant} cart")
            lines.append(
                f"3. Apply voucher → pay remaining ₹{remainder:,.0f}"
                if remainder else "3. Apply voucher → full order covered"
            )
    elif in_store:
        lines.append(f"1. Buy in-store at {merchant}")
    else:
        lines.append(f"1. Buy directly from {merchant} — link below")

    if card_fomo:
        card_name = card_fomo.get("card_name", "")
        extra_saving = card_fomo.get("actual_saving", 0)
        final_with_card = card_fomo.get("final_cost_with_card", 0)
        apply_url = card_fomo.get("apply_url", "")
        lines.append("")
        lines.append(f"💳 Have a *{card_name}* card?")
        lines.append(f"Pay with it at checkout to save an extra ₹{extra_saving:,.0f}")
        lines.append(f"Your final cost: ₹{final_with_card:,.0f}")
        if apply_url:
            lines.append(f"Don't have it? Apply: {apply_url}")

    return "\n".join(lines) + "\n"


def _route_links(route: dict) -> list[tuple[str, str, str]]:
    """(body_text, button_label, url) for each CTA button to send after the
    route's text — voucher link first (buy it before checkout), then the
    store link (skipped for in-store routes, which have no online seller
    link). Cuelinks-wraps only the store link, per the existing rule."""
    links = []
    merchant = route.get("merchant") or "the store"
    voucher = route.get("voucher")
    if voucher and voucher.get("voucher_url"):
        voucher_brand = voucher.get("merchant") or merchant
        upi = voucher.get("upi", {})
        txns = upi.get("txns_needed", 1)
        denomination = upi.get("voucher_amount", 0)
        cap_per_txn = upi.get("purchase_cap_per_txn")
        # Same reasoning as the web UI: Gyftr only sells fixed denominations,
        # so show the real breakdown rather than implying one lump-sum voucher.
        denom_breakdown = upi.get("denomination_breakdown") or []
        voucher_word = "voucher" if sum(b.get("count", 0) for b in denom_breakdown) <= 1 else "vouchers"
        breakdown = upi.get("purchase_breakdown") or f"₹{denomination:,.0f}"
        body_lines = [f"Buy {breakdown} {voucher_brand} {voucher_word} on Gyftr using UPI."]
        if txns > 1:
            cap_text = f" (₹{cap_per_txn:,.0f} max per transaction)" if cap_per_txn else ""
            body_lines.append(f"You'll need {txns} separate Gyftr purchases{cap_text}.")
        terms = (voucher.get("redemption_instructions") or [])[:2]
        if terms:
            body_lines.append("")
            body_lines.append("Key terms:")
            body_lines.extend(f"• {t}" for t in terms)
        links.append((
            "\n".join(body_lines),
            "🎟 Buy Gyftr Voucher",
            voucher["voucher_url"],
        ))
    sellers = route.get("sellers") or []
    if sellers and sellers[0].get("link"):
        links.append((
            f"Ready to buy from {merchant}?",
            f"Open {merchant}",
            _affiliate_url(sellers[0]["link"]),
        ))
    return links


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


async def send_cta_url(phone: str, body_text: str, button_text: str, url: str) -> None:
    """Meta interactive CTA-URL message — a proper tappable button with a
    clean label, instead of pasting a raw (possibly long, Cuelinks-wrapped)
    link into message text."""
    api_url, headers = _graph_config()
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {"text": body_text},
            "action": {
                "name": "cta_url",
                "parameters": {"display_text": button_text, "url": url},
            },
        },
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
                    {"type": "reply", "reply": {"id": "see_alternatives", "title": "Check alternatives"}}
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


_ROW_TITLE_STOPWORDS = {
    "buy", "price", "online", "best", "new", "latest", "india", "offer",
    "offers", "deal", "deals", "for", "the", "a", "an", "with", "and",
}


def _short_title(title: str, query: str) -> str:
    """Strip the brand + the query's own words from a title before it gets
    truncated to Meta's 24-char list-row limit — otherwise repeated brand and
    model boilerplate (e.g. "boAt Airdopes 141") eats the whole budget before
    the actually distinguishing part (color, variant) ever appears."""
    query_words = {
        w for w in re.findall(r"[a-z0-9]+", (query or "").lower())
        if w not in _ROW_TITLE_STOPWORDS
    }
    kept = [
        w for w in (title or "").split()
        if w.lower() not in query_words and w.lower() not in KNOWN_BRANDS
    ]
    short = " ".join(kept).strip(" -,")
    return short or title


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

async def _send_route_message(
    phone: str, route: dict, with_alt_button: bool, label: str = "RECOMMENDED ROUTE"
) -> None:
    """Full route detail: text body, then a CTA-URL button per link
    (voucher, then store) — shared by the recommended-route send and by a
    promoted alternative, so both render identically."""
    msg = format_recommended(route, label=label)
    if with_alt_button:
        await send_with_alternatives_button(phone, msg)
    else:
        await send_text(phone, msg)
    for body_text, button_label, url in _route_links(route):
        await send_cta_url(phone, body_text, button_label, url)


async def _send_routes_for_token(
    phone: str, product_token: str, query: str, title: str = "",
    picked_price: float | None = None, picked_source: str = "",
) -> None:
    result = await asyncio.to_thread(
        search_service.build_routes_for_token, product_token, query, title,
        picked_price, picked_source,
    )
    routes = result.get("routes", {})
    recommended = routes.get("recommended")
    if not recommended:
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        return
    session_store.set_session(phone, {"routes": routes})
    await _send_route_message(phone, recommended, with_alt_button=bool(routes.get("alternatives")))


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
            only = products[0]
            await _send_routes_for_token(
                phone, only["product_token"], query, only.get("title", ""),
                only.get("price"), only.get("source", ""),
            )
            return

        session_store.set_session(phone, {"candidates": products, "query": query})
        rows = []
        for i, p in enumerate(products[:10]):
            full_title = p.get("title") or f"Option {i + 1}"
            price = p.get("price")
            desc = f"{full_title} · ₹{price:,.0f}" if price else full_title
            rows.append({
                "id": f"prod_{i}",
                "title": _truncate(_short_title(full_title, query), 24),
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
    await _send_routes_for_token(
        phone, chosen["product_token"], query, chosen.get("title", ""),
        chosen.get("price"), chosen.get("source", ""),
    )


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
        path = "Gyftr → Buy" if alt.get("voucher") else "Direct Buy"
        desc = f"{path} · ₹{final_cost:,.0f}" if final_cost else path
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
    recommended route gets — rendered through format_recommended(), labeled
    "ALTERNATIVE ROUTE #N" (N = how many times an alternative has been picked
    this session, so re-picking reads as a distinct choice, not a demotion of
    "recommended") instead of "RECOMMENDED ROUTE"."""
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
    alt_count = session.get("alt_count", 0) + 1
    session_store.set_session(phone, {**session, "alt_count": alt_count})
    await _send_route_message(phone, chosen, with_alt_button=False, label=f"ALTERNATIVE ROUTE #{alt_count}")


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
