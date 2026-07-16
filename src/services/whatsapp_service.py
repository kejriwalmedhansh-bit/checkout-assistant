"""WhatsApp business logic — input classification, pipeline dispatch, message
formatting, and Meta Graph send calls.

Message architecture (redesigned 2026-07-14 for a less chatty flow): every
reply is "one message = one job" — a typing indicator while the search runs
(no "checking..." text bubble), then a compact photo+numbers result, then one
short step message per required action (each with its own CTA-URL button,
since WhatsApp never tells us whether a URL button was tapped), then a single
message with the two things a user can actually do next as trackable native
reply buttons ("Other route" / "Need help" — list/button taps DO trigger a
webhook, unlike CTA-URL taps).
"""
from __future__ import annotations

import asyncio
import io
import re
from urllib.parse import quote

import httpx
from PIL import Image

from ..cache import session_store
from ..config import get_settings
from ..constants import (
    CUELINKS_BASE,
    KNOWN_BRANDS,
    WHATSAPP_DEAD_END_MSG,
    WHATSAPP_GRAPH_BASE,
    WHATSAPP_GRAPH_VERSION,
    WHATSAPP_MORE_OPTIONS_MSG,
    WHATSAPP_MULTI_MATCH_MSG,
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


# ── result formatting ─────────────────────────────────────────────────────────

def _build_result_caption(route: dict) -> str:
    """Compact result text — title, best route, price, and a prominent
    savings line. The savings figure is deliberately voucher/price-only
    (listed price vs. the actual route cost) — it must never include a
    credit-card cashback, since that's conditional on owning one specific
    card and isn't available to everyone (see CLAUDE.md rule: card savings
    never affect ranking, users may not have premium cards). Card cashback
    is shown as its own clearly-optional callout below, with an apply link,
    never blended into the headline number."""
    title = route.get("title", "")
    merchant = route.get("merchant") or "—"
    voucher = route.get("voucher")
    card_fomo = route.get("card_fomo")
    listed_price = route.get("listed_price")
    final_cost = route.get("final_cost") or 0

    # In-store routes already carry "(in-store)" baked into route["merchant"]
    # (see search_service._build_routes) — only online vouchers get the
    # "+ Gift Voucher" suffix, so an in-store route doesn't read as
    # "X (in-store) + Gift Voucher". "Gyftr" by name is deliberately kept
    # out of this summary line (and the alternatives list) — it's meaningless
    # to a customer who's never heard of it; it only appears in the Step 1
    # instruction text, where naming the actual site orients them right
    # before they're sent there.
    if voucher and not voucher.get("offline_only"):
        best_route = f"{merchant} + Gift Voucher"
    else:
        best_route = merchant

    savings = (listed_price - final_cost) if listed_price else 0
    has_discount = savings > 0

    lines = [
        f"*{title}*",
        f"Best route: {best_route}",
    ]
    if has_discount:
        lines.append(f"Price: ~₹{listed_price:,.0f}~ *₹{final_cost:,.0f}*")
        pct = round((savings / listed_price) * 100)
        lines.append(f"*YOU SAVE ₹{savings:,.0f} ({pct}% off)* 🎉")
    else:
        lines.append(f"Price: ₹{final_cost:,.0f}")

    if card_fomo:
        card_name = card_fomo.get("card_name", "")
        extra_saving = card_fomo.get("actual_saving", 0)
        apply_url = card_fomo.get("apply_url") or ""
        lines.append("")
        lines.append(f"💳 Have an {card_name} card? Save an extra ₹{extra_saving:,.0f} paying with it.")
        if apply_url:
            lines.append(f"Don't have it? Apply: {apply_url}")

    return "\n".join(lines)


def _voucher_word(denom_breakdown: list[dict]) -> str:
    return "voucher" if sum(b.get("count", 0) for b in denom_breakdown) <= 1 else "vouchers"


async def _send_voucher_steps(phone: str, route: dict) -> None:
    """Step 1: buy the voucher (its own CTA button). Step 2: redeem it — a
    CTA button to the merchant when there's a real online link, plain text
    when the voucher is in-store only (there's nothing to link a button to).
    Gyftr only sells fixed denominations, so Step 1 always states the exact
    amount to buy — and when a per-transaction cap forces multiple separate
    purchases, that requirement is folded into the same message rather than
    dropped, since skipping it risks a purchase failing with no explanation."""
    voucher = route["voucher"]
    merchant = (route.get("merchant") or "the store").replace(" (in-store)", "")
    in_store = bool(voucher.get("offline_only"))
    upi = voucher.get("upi", {})

    denom_breakdown = upi.get("denomination_breakdown") or []
    voucher_word = _voucher_word(denom_breakdown)
    voucher_brand = voucher.get("merchant") or merchant
    discount_pct = upi.get("pct", 0)

    txns = upi.get("txns_needed", 1)

    if len(denom_breakdown) > 1:
        # A single inline "2×₹10,000 + 1×₹3,000 + 3×₹500" string reads as a
        # cramped run-on when it's more than one or two items — a short
        # bulleted list is much easier to actually follow while shopping.
        breakdown_lines = "\n".join(f"• {b['count']} × ₹{b['denom']:,}" for b in denom_breakdown)
        step1_text = (
            f"*Step 1 of 2*\n\n"
            f"Buy these {voucher_brand} {voucher_word} on Gyftr ({discount_pct}% off via UPI):\n"
            f"{breakdown_lines}"
        )
        # Multiple denominations reads like multiple separate trips to
        # Gyftr, which is demotivating and usually wrong — Gyftr has a cart,
        # so unless a real per-transaction cap forces separate purchases
        # (handled below), all of these go in one cart, one checkout.
        if txns <= 1:
            step1_text += "\n\nAdd all of these to your Gyftr cart — one checkout covers it."
    else:
        breakdown = upi.get("purchase_breakdown") or f"₹{upi.get('voucher_amount', 0):,.0f}"
        step1_text = (
            f"*Step 1 of 2*\n\n"
            f"Buy exactly {breakdown} {voucher_brand} {voucher_word} on Gyftr first "
            f"({discount_pct}% off via UPI)."
        )
    if txns > 1:
        cap = upi.get("purchase_cap_per_txn")
        cap_text = f", ₹{cap:,.0f} max per transaction" if cap else ""
        step1_text += f"\n\nYou'll need to do this {txns} separate times{cap_text}."
    await send_cta_url(phone, step1_text, "1. Buy Voucher", voucher["voucher_url"])
    await asyncio.sleep(_MESSAGE_PACE_SECONDS)

    remainder = upi.get("remainder", 0)
    redeem_instruction = voucher.get("how_to_redeem_short")
    if in_store:
        step2_text = f"*Step 2 of 2*\n\nHead to your nearest {merchant} store. {redeem_instruction or 'Show the voucher at checkout.'}"
        step2_text += f"\nPay the remaining ₹{remainder:,.0f}." if remainder else "\nIt covers the full order."
        await send_text(phone, step2_text)
    else:
        step2_text = f"*Step 2 of 2*\n\nOpen {merchant}, add the item to cart. {redeem_instruction or 'Apply the voucher.'}"
        step2_text += f"\nPay the remaining ₹{remainder:,.0f}." if remainder else "\nIt covers the full order."
        sellers = route.get("sellers") or []
        link = sellers[0].get("link") if sellers else None
        if link:
            await send_cta_url(phone, step2_text, "2. Open Store", _affiliate_url(link))
        else:
            await send_text(phone, step2_text)


async def _send_direct_cta(phone: str, route: dict) -> None:
    """No-voucher flow: one merchant CTA message, no step framing — skipped
    entirely (falls straight through to the follow-up buttons) if there's no
    recoverable seller link at all."""
    merchant = route.get("merchant") or "the store"
    sellers = route.get("sellers") or []
    link = sellers[0].get("link") if sellers else None
    if link:
        await send_cta_url(phone, f"Ready to buy from {merchant}?", f"Open {merchant}", _affiliate_url(link))


async def _send_result_message(phone: str, image_url: str | None, caption: str) -> None:
    """Photo + caption when a real image URL is available and Meta accepts
    it; falls back to a plain text bubble otherwise, so the image is never
    required for the result to be understandable."""
    sent = False
    if image_url and image_url.startswith("http"):
        sent = await send_image(phone, image_url, caption)
    if not sent:
        await send_text(phone, caption)


async def _send_followup_buttons(phone: str) -> None:
    await send_reply_buttons(
        phone, WHATSAPP_MORE_OPTIONS_MSG,
        [("see_alternatives", "Other route")],
    )


_MESSAGE_PACE_SECONDS = 2  # Breathing room between bubbles so a fast reply doesn't arrive as one dense burst.


async def _send_success_flow(phone: str, route: dict, image_url: str | None) -> None:
    """The full 3-4 message success reply, shared by every path that ends in
    showing a route: a fresh recommended route, a no-voucher route, and a
    promoted alternative all render identically through here. A short pause
    between each bubble keeps it readable as a sequence instead of a burst —
    without it, everything can land within the same second once the search
    itself is done."""
    caption = _build_result_caption(route)
    await _send_result_message(phone, image_url, caption)
    await asyncio.sleep(_MESSAGE_PACE_SECONDS)
    if route.get("voucher"):
        await _send_voucher_steps(phone, route)
    else:
        await _send_direct_cta(phone, route)
    await asyncio.sleep(_MESSAGE_PACE_SECONDS)
    await _send_followup_buttons(phone)


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


async def send_typing_indicator(message_id: str | None) -> None:
    """Marks the triggering message read and shows WhatsApp's native typing
    indicator (visible up to 25s, or until we send a reply) — replaces the
    old "Checking prices..." text bubble with no chat message spent at all.
    Never raises: a missed typing indicator must not block the real search."""
    if not message_id:
        return
    api_url, headers = _graph_config()
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(api_url, headers=headers, json=payload)
            print(f"[WhatsApp Send] Status: {r.status_code} | Body: {r.text}")
    except Exception as e:
        print(f"[WhatsApp Send] typing indicator failed: {e}")


_TYPING_REFRESH_SECONDS = 20  # Meta's indicator expires after 25s — refresh before that.


async def _run_with_typing_keepalive(msg_id: str | None, work) -> None:
    """Runs a background reply coroutine while re-firing the typing
    indicator every ~20s for as long as it's still running. The external
    pricing search this wraps can occasionally take 20-30+ seconds (real,
    observed third-party API latency) — without this, WhatsApp's typing
    indicator silently expires partway through the wait, leaving dead
    silence right before the reply finally lands."""
    task = asyncio.create_task(work)
    while not task.done():
        done, _ = await asyncio.wait({task}, timeout=_TYPING_REFRESH_SECONDS)
        if not done:
            await send_typing_indicator(msg_id)
    await task


async def _fetch_and_convert_to_jpeg(image_url: str) -> bytes | None:
    """Downloads a product thumbnail and converts it to JPEG in memory.
    Required, not defensive: every thumbnail this app's search source serves
    (Google's shopping tbn proxy) is WebP (confirmed via Content-Type), and
    WhatsApp's Cloud API rejects WebP outright ("WebP image uploads are not
    currently supported") — sending the original link always fails."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(image_url)
            if r.status_code >= 400 or not r.content:
                return None
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"[WhatsApp Image] convert failed: {e}")
        return None


async def _upload_media(jpeg_bytes: bytes) -> str | None:
    """Uploads image bytes to Meta's media endpoint; returns a media id for
    a subsequent image message, or None on failure."""
    settings = get_settings()
    api_url = f"{WHATSAPP_GRAPH_BASE}/{WHATSAPP_GRAPH_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
    files = {"file": ("product.jpg", jpeg_bytes, "image/jpeg")}
    data = {"messaging_product": "whatsapp", "type": "image/jpeg"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(api_url, headers=headers, data=data, files=files)
        print(f"[WhatsApp Send] Media upload status: {r.status_code} | Body: {r.text}")
        if r.status_code >= 400:
            return None
        return r.json().get("id")


async def send_image(phone: str, image_url: str, caption: str) -> bool:
    """Downloads + converts the thumbnail to JPEG and uploads it to Meta as
    media, then sends it by media id — sending by link doesn't work here
    since the source is always WebP (see _fetch_and_convert_to_jpeg).
    Returns True only once the final send itself is accepted; callers fall
    back to send_text on False (download, conversion, upload, or send — any
    stage failing lands here)."""
    jpeg_bytes = await _fetch_and_convert_to_jpeg(image_url)
    if not jpeg_bytes:
        return False
    media_id = await _upload_media(jpeg_bytes)
    if not media_id:
        return False
    api_url, headers = _graph_config()
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "image",
        "image": {"id": media_id, "caption": caption},
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(api_url, headers=headers, json=payload)
        print(f"[WhatsApp Send] Status: {r.status_code} | Body: {r.text}")
        return r.status_code < 400


async def send_cta_url(phone: str, body_text: str, button_text: str, url: str) -> None:
    """Meta interactive CTA-URL message — a proper tappable button with a
    clean label, instead of pasting a raw (possibly long, Cuelinks-wrapped)
    link into message text. Meta never tells us whether this gets tapped."""
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


async def send_reply_buttons(phone: str, text: str, buttons: list[tuple[str, str]]) -> None:
    """Native WhatsApp reply buttons (max 3) — along with list rows, the only
    interactive element whose tap triggers a webhook event back to us."""
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
                    {"type": "reply", "reply": {"id": button_id, "title": title}}
                    for button_id, title in buttons
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

async def _send_routes_for_token(
    phone: str, product_token: str, query: str, title: str = "",
    picked_price: float | None = None, picked_source: str = "",
    picked_thumbnail: str | None = None,
) -> None:
    result = await asyncio.to_thread(
        search_service.build_routes_for_token, product_token, query, title,
        picked_price, picked_source, picked_thumbnail,
    )
    routes = result.get("routes", {})
    recommended = routes.get("recommended")
    if not recommended:
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        return
    image_url = result.get("source", {}).get("image") or picked_thumbnail
    session_store.set_session(phone, {"routes": routes, "image": image_url})
    await _send_success_flow(phone, recommended, image_url)


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
                only.get("price"), only.get("source", ""), only.get("thumbnail"),
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
        await send_text(phone, WHATSAPP_MULTI_MATCH_MSG)
        await asyncio.sleep(_MESSAGE_PACE_SECONDS)
        await send_list_message(
            phone,
            body_text="Select the exact product:",
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
        chosen.get("price"), chosen.get("source", ""), chosen.get("thumbnail"),
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
        path = "Gift Voucher → Buy" if alt.get("voucher") else "Direct Buy"
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
    """A picked alternative gets the exact same full success flow the
    original recommended route did (image, numbers, steps, follow-up
    buttons) — reusing the product image already stored in the session
    rather than re-fetching it, since the image identifies the product, not
    the specific merchant route."""
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
    await _send_success_flow(phone, chosen, session.get("image"))


async def handle_incoming(body: dict) -> None:
    """Parse a Meta webhook payload and dispatch. Swallows malformed payloads
    and any Graph-API-call failures — Meta expects a 200 ack regardless, and
    an uncaught exception here would surface as a 500 in the webhook route,
    risking Meta's retry/backoff behavior on an already-processed message."""
    try:
        entry = body["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return
        msg = messages[0]
        phone = msg["from"]
        msg_id = msg.get("id")
        msg_type = msg.get("type")

        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype = interactive.get("type")
            if itype == "button_reply":
                reply_id = interactive["button_reply"]["id"]
                if reply_id == "see_alternatives":
                    await send_typing_indicator(msg_id)
                    asyncio.create_task(handle_alternatives(phone))
            elif itype == "list_reply":
                reply_id = interactive["list_reply"]["id"]
                if reply_id.startswith("alt_"):
                    # Not a fresh pricing search, but still a real wait —
                    # the image download/convert/upload + several message
                    # sends take noticeable time, so this gets the typing
                    # indicator too rather than assuming "cached = instant".
                    await send_typing_indicator(msg_id)
                    asyncio.create_task(
                        _run_with_typing_keepalive(msg_id, handle_alternative_selection(phone, reply_id))
                    )
                elif reply_id.startswith("prod_"):
                    await send_typing_indicator(msg_id)
                    asyncio.create_task(
                        _run_with_typing_keepalive(msg_id, handle_product_selection(phone, reply_id))
                    )
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

        await send_typing_indicator(msg_id)
        asyncio.create_task(_run_with_typing_keepalive(msg_id, process_and_respond(phone, classification)))
    except (KeyError, IndexError):
        pass
    except Exception as e:
        print(f"[Webhook] handle_incoming error: {e}")
