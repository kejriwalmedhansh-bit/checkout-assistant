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
import base64
import io
import json
import re
from urllib.parse import quote

import httpx
from PIL import Image

from .. import message_log
from ..cache import RateLimiter, TTLCache, session_store
from ..config import get_settings
from ..constants import (
    KNOWN_BRANDS,
    WHATSAPP_DEAD_END_MSG,
    WHATSAPP_FLOW_FIELD_NAME,
    WHATSAPP_FLOW_SCREEN_ID,
    WHATSAPP_GRAPH_BASE,
    WHATSAPP_GRAPH_VERSION,
    WHATSAPP_LOW_CONFIDENCE_MSG,
    WHATSAPP_MORE_OPTIONS_MSG,
    WHATSAPP_MULTI_MATCH_MSG,
    WHATSAPP_NO_ALTERNATIVES_MSG,
    WHATSAPP_ONBOARDING_MSG,
    WHATSAPP_PICK_REMINDER_MSG,
    WHATSAPP_RATE_LIMITED_MSG,
    WHATSAPP_SESSION_EXPIRED_MSG,
)
from . import analytics_service, search_service

_search_rate_limiter = RateLimiter(
    max_per_window=get_settings().WHATSAPP_MAX_SEARCHES_PER_HOUR, window_seconds=3600,
)


def _track(event: str, phone: str, **properties) -> None:
    """Fire-and-forget wrapper around analytics_service.track — creates a
    background task so a slow/down Mixpanel never delays a WhatsApp reply."""
    asyncio.create_task(analytics_service.track(event, phone, properties))


def _affiliate_url(link: str) -> str:
    """Cuelinks wrapper for merchant store links — mirrors the web frontend's
    affiliateUrl(). Deliberately NOT applied to Gyftr voucher links.

    Routes through our own /go redirect (see api/routers/redirect.py)
    instead of linksredirect.com directly, so the WhatsApp button's URL —
    visible to Meta's link scanner and, briefly, in-browser on tap — shows
    our own domain rather than an unfamiliar third-party tracking redirect.
    """
    if not link:
        return link
    settings = get_settings()
    return f"{settings.PUBLIC_BASE_URL}/go?url={quote(link, safe='')}"


# ── input classification (ported from whatsapp/classifier.py) ───────────────────

URL_RE = re.compile(r"https?://\S+")

NOISE_PHRASES = {
    "hi", "hii", "hiii", "hello", "helo", "hlo", "hola", "namaste",
    "hey", "heyy", "yo", "yoo", "sup", "wassup",
    "good morning", "good afternoon", "good evening", "good night", "gm", "gn",
    "thanks", "thank you", "thx", "ty", "tysm",
    "ok", "okay", "k", "kk", "alright", "cool", "nice", "great", "awesome",
    "yes", "yeah", "yep", "yup", "no", "nope", "nah", "sure", "fine",
    "lol", "haha", "hahaha", "hmm", "hmm ok",
    "test", "testing",
    "who are you", "what is this", "what are you", "how does this work",
    "are you a bot", "is this a bot", "u there", "you there", "anyone there",
    "hello?", "hey there", "who dis", "wrong number",
    "help", "start", "menu",
}

# Distinct from a plain confused/noise message — a real (if unactionable
# right now) opt-out or command signal, worth its own analytics tag even
# though the reply to the user is the same "didn't catch that" nudge. Not
# acted on beyond that yet — see Phase C follow-up-messaging work.
OPT_OUT_PHRASES = {"stop", "unsubscribe", "cancel", "no thanks", "not interested"}

# Collapses a run of 3+ identical characters down to 2 ("hiiiiii" -> "hii",
# "heyyyyy" -> "heyy") so elongated greetings match NOISE_PHRASES without
# hardcoding every possible spelling.
_REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")

# Every single-word entry from the phrase sets above, reused to catch a
# message made of nothing but repeated/combined filler words — "Hi hi",
# "yes yes", "hey hey" — which no *exact* multi-word phrase entry would
# ever cover (there's no realistic way to enumerate every such combo).
# Live-tested 2026-08-26: "Hi hi" wasn't in NOISE_PHRASES verbatim, so it
# fell through as a real product query and returned a garbage picker.
_NOISE_WORDS = {p for p in NOISE_PHRASES if " " not in p}
_OPT_OUT_WORDS = {p for p in OPT_OUT_PHRASES if " " not in p}


def _all_words_are_filler(cleaned: str) -> str | None:
    """Returns "opt_out"/"noise_phrase" if every letter-word in the message
    is a known filler word on its own (any count, any order), None if any
    word isn't recognized filler — so a real product query (which always
    has at least one non-filler word, e.g. "boAt") is never affected."""
    words = re.findall(r"[a-zA-Z]+", cleaned)
    if not words:
        return None
    normalized_words = [_REPEATED_CHAR_RE.sub(r"\1\1", w.lower()) for w in words]
    if all(w in _OPT_OUT_WORDS for w in normalized_words):
        return "opt_out"
    if all(w in _NOISE_WORDS or w in _OPT_OUT_WORDS for w in normalized_words):
        return "noise_phrase"
    return None


def classify_input(text: str) -> dict:
    if not text or not text.strip():
        return {"type": "unparseable", "reason": "empty"}
    cleaned = text.strip()
    url_match = URL_RE.search(cleaned)
    if url_match:
        return {"type": "url", "url": url_match.group(0)}
    lowered = re.sub(r"[!.?,]+$", "", cleaned.lower()).strip()
    normalized = _REPEATED_CHAR_RE.sub(r"\1\1", lowered)
    if normalized in OPT_OUT_PHRASES:
        return {"type": "unparseable", "reason": "opt_out"}
    if normalized in NOISE_PHRASES:
        return {"type": "unparseable", "reason": "noise_phrase"}
    filler_reason = _all_words_are_filler(cleaned)
    if filler_reason:
        return {"type": "unparseable", "reason": filler_reason}
    if len(cleaned) < 3:
        return {"type": "unparseable", "reason": "too_short"}
    if not re.search(r"[a-zA-Z0-9]", cleaned):
        return {"type": "unparseable", "reason": "no_alphanumeric_content"}
    return {"type": "product_name", "query": cleaned}


# ── result formatting ─────────────────────────────────────────────────────────

def _display_merchant(route: dict) -> str:
    """Prefer the voucher database's own clean brand name (e.g. "AJIO Luxe")
    over the raw merchant string a search result reports for this listing —
    that raw string is sometimes a bare domain like "luxe.ajio.com" rather
    than a display name, since it's passed through verbatim from whatever
    the search source called the seller. Falls back to route["merchant"]
    when there's no voucher, or the voucher has no clean name to prefer.
    Preserves the "(in-store)" suffix search_service.py bakes into
    route["merchant"] for offline-only voucher routes."""
    raw = route.get("merchant") or "the store"
    voucher = route.get("voucher")
    if voucher and voucher.get("brand_name"):
        suffix = " (in-store)" if raw.endswith(" (in-store)") else ""
        return voucher["brand_name"] + suffix
    return raw


_RESULT_TITLE_MAX_CHARS = 70


def _clean_result_title(title: str) -> str:
    """Scraped titles are frequently SEO-stuffed with every spec/feature
    ("... Dimmmable Light Electric ... with 2 Bulbs, ... Premium Scented
    Jar") — bolding the whole thing in a chat bubble reads as a wall of
    text, not a product name. Trims to a clean word boundary rather than a
    hard character cut, so it never ends mid-word."""
    title = (title or "").strip()
    if len(title) <= _RESULT_TITLE_MAX_CHARS:
        return title
    cut = title[:_RESULT_TITLE_MAX_CHARS].rsplit(" ", 1)[0]
    return (cut or title[:_RESULT_TITLE_MAX_CHARS]).rstrip(",.-") + "…"


def _build_result_caption(route: dict) -> str:
    """Compact result text — title, route, and price/savings. Card cashback
    is sent separately by _send_card_fomo, after the redemption steps —
    never blended into this headline (see CLAUDE.md rule: card savings
    never affect ranking, users may not have premium cards)."""
    title = _clean_result_title(route.get("title", ""))
    merchant = _display_merchant(route)
    voucher = route.get("voucher")
    listed_price = route.get("listed_price")
    final_cost = route.get("final_cost") or 0

    # In-store routes already carry "(in-store)" baked into route["merchant"]
    # (see search_service._build_routes) — only online vouchers get the
    # "+ gift voucher" suffix, so an in-store route doesn't read as
    # "X (in-store) + gift voucher". "Gyftr" by name is deliberately kept
    # out of this summary line (and the alternatives list) — it's meaningless
    # to a customer who's never heard of it; it only appears in the Step 1
    # instruction text, where naming the actual site orients them right
    # before they're sent there.
    if voucher and not voucher.get("offline_only"):
        best_route = f"{merchant} + gift voucher"
    else:
        best_route = merchant

    savings = (listed_price - final_cost) if listed_price else 0
    has_discount = savings > 0

    lines = [
        f"*{title}*",
        best_route,
    ]
    if has_discount:
        lines.append(f"₹{listed_price:,.0f} → *₹{final_cost:,.0f}*")
        pct = round((savings / listed_price) * 100)
        # A party emoji on a 1% saving reads as fake enthusiasm — reserve
        # the celebration for a discount actually worth celebrating.
        celebration = " 🎉" if pct >= 10 else ""
        lines.append(f"You save ₹{savings:,.0f} ({pct}% off){celebration}")
    else:
        lines.append(f"Price: ₹{final_cost:,.0f}")

    return "\n".join(lines)


def _voucher_word(denom_breakdown: list[dict]) -> str:
    return "voucher" if sum(b.get("count", 0) for b in denom_breakdown) <= 1 else "vouchers"


async def _send_voucher_steps(phone: str, route: dict) -> None:
    """All steps for a voucher route are sent back-to-back with only brief
    breathing room between bubbles — never gated on the user having actually
    tapped a button first (Meta never reports CTA-url taps, so pacing by an
    assumed click time was pure guesswork and just made Step 2 feel like it
    was withheld until a click that was never actually detected).

    Up to three steps: an optional check-the-page disclaimer (online routes
    only — nothing to check for an in-store voucher) telling the user to
    confirm the price/specs and look for a coupon Dealo's price-only scan
    might have missed, since that changes what voucher amount to buy; buy
    the voucher; then redeem it. Gyftr only sells fixed denominations, so
    the buy step always states the exact amount to buy — and when a
    per-transaction cap forces multiple separate purchases, that requirement
    is folded into the same message rather than dropped, since skipping it
    risks a purchase failing with no explanation."""
    voucher = route["voucher"]
    merchant = _display_merchant(route).replace(" (in-store)", "")
    in_store = bool(voucher.get("offline_only"))
    upi = voucher.get("upi", {})

    sellers = route.get("sellers") or []
    link = sellers[0].get("link") if sellers else None
    check_page_first = bool(link) and not in_store
    total_steps = 3 if check_page_first else 2
    step_n = 1

    if check_page_first:
        affiliate_link = _affiliate_url(link)
        check_text = (
            f"*Step {step_n} of {total_steps}*\n\n"
            f"Quick check — is everything still right on {merchant}?"
        )
        if not await send_cta_url(phone, check_text, f"View on {merchant}", affiliate_link):
            await send_text(phone, f"{check_text}\n{affiliate_link}")
        step_n += 1
        # Longer pause here on purpose — this is the one step that sends the
        # user away from the chat to actually look at something, so it gets
        # real breathing room before the buy/redeem steps land, unlike the
        # short beat used between every other bubble pair in this flow.
        await asyncio.sleep(_CHECK_PAGE_GAP_SECONDS)

    denom_breakdown = upi.get("denomination_breakdown") or []
    voucher_word = _voucher_word(denom_breakdown)
    voucher_brand = voucher.get("brand_name") or voucher.get("merchant") or merchant
    discount_pct = upi.get("pct", 0)
    platform_label = "Maximize" if voucher.get("voucher_source") == "maximize" else "Gyftr"

    txns = upi.get("txns_needed", 1)

    if len(denom_breakdown) > 1:
        # A single inline "2×₹10,000 + 1×₹3,000 + 3×₹500" string reads as a
        # cramped run-on when it's more than one or two items — a short
        # bulleted list is much easier to actually follow while shopping.
        breakdown_lines = "\n".join(f"• *{b['count']} × ₹{b['denom']:,}*" for b in denom_breakdown)
        step1_text = (
            f"*Step {step_n} of {total_steps}*\n\n"
            f"Buy these {voucher_brand} {voucher_word} on {platform_label} ({discount_pct}% off via UPI):\n"
            f"{breakdown_lines}"
        )
        # Multiple denominations reads like multiple separate trips to the
        # platform, which is demotivating and usually wrong — both sources
        # have a cart, so unless a real per-transaction cap forces separate
        # purchases (handled below), all of these go in one cart, one checkout.
        if txns <= 1:
            step1_text += f"\n\nAdd all of these to your {platform_label} cart — one checkout covers it."
    else:
        breakdown = upi.get("purchase_breakdown") or f"₹{upi.get('voucher_amount', 0):,.0f}"
        step1_text = (
            f"*Step {step_n} of {total_steps}*\n\n"
            f"Buy exactly *{breakdown}* {voucher_brand} {voucher_word} on {platform_label} first "
            f"({discount_pct}% off via UPI)."
        )
    if txns > 1:
        cap = upi.get("purchase_cap_per_txn")
        cap_text = f", *₹{cap:,.0f}* max per transaction" if cap else ""
        step1_text += f"\n\nYou'll need to do this {txns} separate times{cap_text}."
    voucher_url = voucher["voucher_url"]
    if not await send_cta_url(phone, step1_text, "Buy Gift Voucher Now", voucher_url):
        await send_text(phone, f"{step1_text}\n{voucher_url}")
    _track(
        "WhatsApp Buy Step Shown", phone,
        step="voucher", platform=platform_label, merchant=merchant,
        discount_pct=discount_pct,
    )
    step_n += 1
    await asyncio.sleep(_MESSAGE_PACE_SECONDS)

    remainder = upi.get("remainder", 0)
    remainder_line = f"Pay the remaining *₹{remainder:,.0f}*." if remainder else "It covers the full order."
    redeem_instruction = voucher.get("how_to_redeem_short")
    if in_store:
        step2_text = (
            f"*Step {step_n} of {total_steps}*\n\n"
            f"Head to your nearest {merchant} store.\n"
            f"{redeem_instruction or 'Show the voucher at checkout.'}\n"
            f"{remainder_line}"
        )
        await send_text(phone, step2_text)
    else:
        step2_text = (
            f"*Step {step_n} of {total_steps}*\n\n"
            f"Open {merchant} and add the item to your cart.\n"
            f"{redeem_instruction or 'Apply the voucher at checkout.'}\n"
            f"{remainder_line}"
        )
        if link:
            affiliate_link = _affiliate_url(link)
            if not await send_cta_url(phone, step2_text, f"Open {merchant}", affiliate_link):
                await send_text(phone, f"{step2_text}\n{affiliate_link}")
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
        affiliate_link = _affiliate_url(link)
        body_text = f"Ready to buy from {merchant}?"
        if not await send_cta_url(phone, body_text, f"Open {merchant}", affiliate_link):
            await send_text(phone, f"{body_text}\n{affiliate_link}")
        _track("WhatsApp Buy Step Shown", phone, step="direct", platform="none", merchant=merchant)


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
        [("see_alternatives", "See other route"), ("pick_again", "Different product")],
    )


async def _send_card_fomo(phone: str, route: dict) -> bool:
    """Optional standalone bubble for the credit-card cashback callout —
    kept out of the main result caption (see _build_result_caption) and
    sent after the redemption steps instead. Only fires when there's an
    actual positive saving to show. Returns whether anything was actually
    sent, so callers can skip a breathing-room pause meant for this message
    when there was nothing to pause after."""
    card_fomo = route.get("card_fomo")
    if not card_fomo:
        return False
    card_saving = card_fomo.get("actual_saving", 0)
    if not card_saving or card_saving <= 0:
        return False
    card_name = card_fomo.get("card_name", "")
    apply_url = card_fomo.get("apply_url") or ""
    body_text = f"💳 Have an {card_name} card? You could save an extra ₹{card_saving:,.0f} on this order."
    if apply_url:
        # Fixed generic label, not f"Apply for {card_name}" — the card name
        # is already in body_text above, and "Apply for {card_name}" hits
        # Meta's 20-char CTA limit for most real card names anyway (e.g.
        # "Apply for SBI Cashback" got truncated to the awkward "Apply for
        # SBI…" live 2026-08-26); this always fits with room to spare.
        if not await send_cta_url(phone, body_text, "Apply for card", apply_url):
            await send_text(phone, f"{body_text}\nDon't have one? Apply here: {apply_url}")
    else:
        await send_text(phone, body_text)
    return True


_MESSAGE_PACE_SECONDS = 2  # Breathing room between bubbles so a fast reply doesn't arrive as one dense burst.
_CHECK_PAGE_GAP_SECONDS = 7  # Longer pause after the check-the-page step — see _send_voucher_steps.
_POST_STEPS_GAP_SECONDS = 5  # Pause after the buy/redeem steps, before the card-fomo and follow-up bubbles.


async def _send_success_flow(phone: str, route: dict, image_url: str | None) -> None:
    """The full message success reply, shared by every path that ends in
    showing a route: a fresh recommended route, a no-voucher route, and a
    promoted alternative all render identically through here. A short pause
    between each bubble keeps it readable as a sequence instead of a burst —
    without it, everything can land within the same second once the search
    itself is done."""
    caption = _build_result_caption(route)
    await _send_result_message(phone, image_url, caption)

    voucher = route.get("voucher")
    listed_price = route.get("listed_price") or 0
    final_cost = route.get("final_cost") or 0
    savings = (listed_price - final_cost) if listed_price else 0
    voucher_platform = "none"
    if voucher:
        voucher_platform = "Maximize" if voucher.get("voucher_source") == "maximize" else "Gyftr"
    _track(
        "WhatsApp Recommendation Shown", phone,
        title=route.get("title", ""),
        vendor=_display_merchant(route),
        voucher_platform=voucher_platform,
        listed_price=listed_price,
        final_cost=final_cost,
        discount_amount=savings,
        discount_pct=round((savings / listed_price) * 100) if listed_price and savings > 0 else 0,
    )
    await asyncio.sleep(_MESSAGE_PACE_SECONDS)
    if route.get("voucher"):
        await _send_voucher_steps(phone, route)
    else:
        await _send_direct_cta(phone, route)

    await asyncio.sleep(_POST_STEPS_GAP_SECONDS)
    card_sent = await _send_card_fomo(phone, route)

    # No point pausing 5s for a card-fomo bubble that never sent — fall
    # back to the normal short beat so the follow-up buttons don't lag for
    # no reason.
    await asyncio.sleep(_POST_STEPS_GAP_SECONDS if card_sent else _MESSAGE_PACE_SECONDS)
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


_SEND_RETRY_DELAY_SECONDS = 2  # short pause before the one retry in _post_graph


async def _alert_admin(message: str, affected_phone: str | None = None) -> None:
    """Fire-and-forget text to WHATSAPP_ADMIN_PHONE (if configured) so a send
    that fails even after retrying reaches a person, not just a server log
    nobody's watching. Deliberately posts directly rather than through
    _post_graph — an alert about a failure must never itself recurse into
    another alert attempt if it also fails.

    Skips sending when affected_phone is the admin's own number: that
    means the failure happened on a message meant for whoever's actually
    reading these alerts, who is already watching it happen live in that
    same chat thread (e.g. a button silently falling back to plain text) —
    an alert on top of that just interleaves noise into the middle of
    their own conversation. A failure on any other phone still alerts
    immediately, since that's the whole point: a real user's problem the
    admin would otherwise never see."""
    admin_phone = get_settings().WHATSAPP_ADMIN_PHONE
    if not admin_phone or affected_phone == admin_phone:
        return
    try:
        api_url, headers = _graph_config()
        payload = {
            "messaging_product": "whatsapp",
            "to": admin_phone,
            "type": "text",
            "text": {"body": f"⚠️ Dealo bot: {message}"},
        }
        async with httpx.AsyncClient() as client:
            await client.post(api_url, headers=headers, json=payload)
    except Exception as e:
        print(f"[WhatsApp Alert] failed to notify admin: {e}")


async def _post_graph(payload: dict, context: str, timeout: float | None = None) -> httpx.Response | None:
    """POSTs a message payload to the Graph API, retrying once after a short
    delay on any failure (non-2xx or a raised exception, e.g. a timeout)
    before giving up. Only alerts the admin once both attempts are
    exhausted, so a single transient blip doesn't page anyone. Returns the
    successful response, or None if both attempts failed — callers that
    need a success/failure bool check `is not None`."""
    api_url, headers = _graph_config()
    last_error = ""
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(api_url, headers=headers, json=payload)
            print(f"[WhatsApp Send] Status: {r.status_code} | Body: {r.text}")
            if r.status_code < 400:
                return r
            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_error = str(e)[:200]
        if attempt == 0:
            await asyncio.sleep(_SEND_RETRY_DELAY_SECONDS)
    await _alert_admin(f"send failed ({context}): {last_error}", affected_phone=payload.get("to"))
    return None


async def send_text(phone: str, text: str) -> None:
    message_log.record(phone, "out", text)
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }
    await _post_graph(payload, context=f"text to {phone}")


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
    silence right before the reply finally lands.

    If this coroutine itself gets cancelled (see _run_exclusive — a newer
    message from the same phone superseded it), the inner `work` task is
    cancelled too rather than left running unsupervised in the background:
    cancelling only the outer wait would abandon the typing-keepalive loop
    while the actual search/reply work silently kept going to completion."""
    task = asyncio.create_task(work)
    try:
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=_TYPING_REFRESH_SECONDS)
            if not done:
                await send_typing_indicator(msg_id)
        await task
    except asyncio.CancelledError:
        task.cancel()
        raise


_active_reply_tasks: dict[str, asyncio.Task] = {}


def _run_exclusive(phone: str, coro) -> None:
    """Starts `coro` as this phone's reply flow, cancelling any not-yet-
    finished reply flow already running for the same phone first.

    A message that arrives while the bot is still mid-reply to that
    person's previous message almost always means "ignore that, answer
    this instead" (a correction, a different product, an impatient
    re-send) rather than "also answer my first one" — without this, two
    flows can run concurrently and their bubbles land interleaved,
    reading as a confusing double reply."""
    prior = _active_reply_tasks.get(phone)
    if prior and not prior.done():
        prior.cancel()
    task = asyncio.create_task(coro)
    _active_reply_tasks[phone] = task

    def _clear_if_current(finished: asyncio.Task, phone=phone) -> None:
        if _active_reply_tasks.get(phone) is finished:
            _active_reply_tasks.pop(phone, None)

    task.add_done_callback(_clear_if_current)


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


_FLOW_IMAGE_MAX_BYTES = 90_000  # margin under Meta's 100KB-per-photo Flow image cap
_FLOW_IMAGE_STEPS = [(480, 80), (360, 70), (240, 60), (160, 50)]  # (width, JPEG quality), largest first


async def _fetch_and_convert_for_flow(image_url: str) -> str | None:
    """Downloads a product thumbnail and step-down compresses it to fit inside
    a WhatsApp Flow RadioButtonsGroup image field (100KB cap). Distinct from
    _fetch_and_convert_to_jpeg (built for the media-upload endpoint, no resize,
    no size ceiling) — this returns a base64 string for direct inline
    embedding in the Flow's JSON payload, sized down since Flow images render
    as small list thumbnails rather than full chat-width photos."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(image_url)
            if r.status_code >= 400 or not r.content:
                return None
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        for width, quality in _FLOW_IMAGE_STEPS:
            resized = img if img.width <= width else img.resize(
                (width, round(img.height * width / img.width)), Image.LANCZOS
            )
            buf = io.BytesIO()
            resized.save(buf, format="JPEG", quality=quality)
            data = buf.getvalue()
            if len(data) <= _FLOW_IMAGE_MAX_BYTES:
                return base64.b64encode(data).decode("ascii")
        return None  # even the smallest/lowest-quality step didn't fit
    except Exception as e:
        print(f"[WhatsApp Flow Image] convert failed: {e}")
        return None


_flow_placeholder_cache: str | None = None


def _flow_placeholder_image() -> str:
    """Lazily builds a flat neutral-gray JPEG (once, cached) used when a
    specific product's thumbnail fails to download/compress — so one bad
    image never blocks that option from appearing in the picker."""
    global _flow_placeholder_cache
    if _flow_placeholder_cache is None:
        img = Image.new("RGB", (240, 240), (230, 230, 230))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        _flow_placeholder_cache = base64.b64encode(buf.getvalue()).decode("ascii")
    return _flow_placeholder_cache


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
    message_log.record(phone, "out", f"[photo] {caption}")
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "image",
        "image": {"id": media_id, "caption": caption},
    }
    return await _post_graph(payload, context=f"image to {phone}") is not None


_CTA_BUTTON_MAX_CHARS = 20  # Meta hard-rejects a longer cta_url display_text with HTTP 400


def _truncate_at_word(s: str, n: int) -> str:
    """Truncates to at most n chars at a clean word boundary (never mid-word)
    when it doesn't fit, appending a single ellipsis char. Same approach as
    _clean_result_title's title-trimming, generalized for reuse here since a
    CTA button label is short enough that a mid-word cut ("...Cashb…") reads
    as sloppy far more often than a full product title would."""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return (cut or s[: n - 1]).rstrip(",.-") + "…"


async def send_cta_url(phone: str, body_text: str, button_text: str, url: str) -> bool:
    """Meta interactive CTA-URL message — a proper tappable button with a
    clean label, instead of pasting a raw (possibly long, Cuelinks-wrapped)
    link into message text. Meta never tells us whether this gets tapped.
    Returns True only on a 2xx response — Meta rejects some button messages
    outright (e.g. a malformed link) with no exception raised on our side,
    so callers must check this and fall back to plain text rather than let
    the whole step silently vanish for the user.

    button_text is built from a merchant/card name of unknown length at
    every call site (f"Open {merchant}", f"Apply for {card_name}", etc.) —
    live-tested 2026-08-26: "Apply for SBI Cashback" (23 chars) got a real
    HTTP 400 from Meta ("Parameter display_text..."), which fell back to
    plain text as designed but is worth avoiding, not just tolerating.
    Truncated centrally here rather than per call site, so every caller is
    covered without remembering to truncate its own button text."""
    button_text = _truncate_at_word(button_text, _CTA_BUTTON_MAX_CHARS)
    message_log.record(phone, "out", f"{body_text} [{button_text}]")
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
    return await _post_graph(payload, context=f"cta_url to {phone}") is not None


async def send_reply_buttons(phone: str, text: str, buttons: list[tuple[str, str]]) -> None:
    """Native WhatsApp reply buttons (max 3) — along with list rows, the only
    interactive element whose tap triggers a webhook event back to us."""
    button_labels = " / ".join(title for _id, title in buttons)
    message_log.record(phone, "out", f"{text} [{button_labels}]")
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
    await _post_graph(payload, context=f"reply_buttons to {phone}")


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
    row_titles = ", ".join(row["title"] for row in rows)
    message_log.record(phone, "out", f"{body_text} [list: {row_titles}]")
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
    await _post_graph(payload, context=f"list to {phone}")


async def send_product_flow(phone: str, body_text: str, flow_cta: str, query: str, products: list[dict]) -> bool:
    """Sends the multi-candidate picker as a WhatsApp Flow (a native screen
    with one real photo per option) instead of send_list_message's text-only
    rows. Returns False on any failure — missing WHATSAPP_FLOW_ID, no
    products, or a non-2xx send — so callers fall back to send_list_message.
    Must never raise past its own boundary; a broken photo picker should
    never be able to break the whole search reply."""
    settings = get_settings()
    if not settings.WHATSAPP_FLOW_ID:
        return False

    items = []
    for i, p in enumerate(products[:10]):  # same 10-item cap as the list-message picker
        full_title = p.get("title") or f"Option {i + 1}"
        price = p.get("price")
        thumbnail = p.get("thumbnail")
        image_b64 = await _fetch_and_convert_for_flow(thumbnail) if thumbnail else None
        items.append({
            "id": f"prod_{i}",
            "title": _truncate(_short_title(full_title, query), 24),
            "description": f"₹{price:,.0f}" if price else "",
            "image": image_b64 or _flow_placeholder_image(),
        })
    if not items:
        return False

    message_log.record(phone, "out", f"{body_text} [flow: {len(items)} products]")
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "flow",
            "body": {"text": body_text},
            "action": {
                "name": "flow",
                "parameters": {
                    "flow_message_version": "3",
                    "flow_id": settings.WHATSAPP_FLOW_ID,
                    "flow_cta": flow_cta,
                    "flow_action": "navigate",
                    "flow_action_payload": {
                        "screen": WHATSAPP_FLOW_SCREEN_ID,
                        "data": {"products": items},
                    },
                },
            },
        },
    }
    return await _post_graph(payload, context=f"flow to {phone}", timeout=15.0) is not None


# ── dispatch ─────────────────────────────────────────────────────────────────────

async def _send_product_picker(
    phone: str, query: str, products: list[dict], approximate: bool = False
) -> None:
    """Shared by process_and_respond and handle_pick_again — both are the
    same picker moment (initial search vs. re-showing the same candidates).
    Tries the photo-carrying Flow first; falls back to the original text-only
    list message unchanged if the Flow isn't configured or fails to send, so
    a broken/unset Flow never breaks the picker outright.

    `approximate` mirrors the web picker's LowConfidenceNotice (same
    search_service flag) — swaps in a body message that says so, rather than
    a separate silent message, since WhatsApp has no room for a banner.

    Always (re)records candidates/query/approximate and marks the session as
    waiting on a product pick — this is what lets a confused reply while
    this picker is up get redirected back here instead of going unanswered
    (see _send_state_aware_nudge)."""
    session = session_store.get_session(phone) or {}
    session_store.set_session(phone, {
        **session, "candidates": products, "query": query,
        "approximate": approximate, "state": "awaiting_product_pick",
    })
    body_text = WHATSAPP_LOW_CONFIDENCE_MSG if approximate else WHATSAPP_MULTI_MATCH_MSG
    flow_sent = await send_product_flow(
        phone, body_text, "Select product", query, products,
    )
    if flow_sent:
        return
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
        body_text=body_text,
        button_text="Select product",
        rows=rows,
    )


async def _send_routes_for_token(
    phone: str, product_token: str, query: str, title: str = "",
    picked_price: float | None = None, picked_source: str = "",
    picked_thumbnail: str | None = None, candidates: list[dict] | None = None,
) -> None:
    result = await asyncio.to_thread(
        search_service.build_routes_for_token, product_token, query, title,
        picked_price, picked_source, picked_thumbnail,
    )
    routes = result.get("routes", {})
    recommended = routes.get("recommended")
    if not recommended:
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        _track("WhatsApp Dead End", phone, stage="no_route", query=query)
        return
    image_url = result.get("source", {}).get("image") or picked_thumbnail
    session_store.set_session(phone, {
        "routes": routes,
        "image": image_url,
        "candidates": candidates or [],
        "query": query,
    })
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
            _track("WhatsApp Dead End", phone, stage="no_candidates", query=query)
            return

        if len(products) == 1:
            # No picker step to attach a low-confidence notice to here — send
            # it as its own message first so a weak single match doesn't
            # reach the route with the same silent confidence as a real one.
            if listing.get("approximate"):
                await send_text(phone, WHATSAPP_LOW_CONFIDENCE_MSG.split("\n\n")[0])
            only = products[0]
            await _send_routes_for_token(
                phone, only["product_token"], query, only.get("title", ""),
                only.get("price"), only.get("source", ""), only.get("thumbnail"),
                candidates=products,
            )
            return

        await _send_product_picker(phone, query, products, approximate=listing.get("approximate", False))
    except Exception as e:
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        _track("WhatsApp Dead End", phone, stage="exception", query=str(e)[:200])
        print(f"[Webhook] Error for {phone}: {e}")


async def handle_product_selection(phone: str, reply_id: str) -> None:
    session = session_store.get_session(phone)
    if not session:
        await send_text(phone, WHATSAPP_SESSION_EXPIRED_MSG)
        _track("WhatsApp Session Expired", phone, at="product_selection")
        return
    candidates = session.get("candidates", [])
    query = session.get("query", "")
    try:
        idx = int(reply_id.split("_", 1)[1])
        chosen = candidates[idx]
    except (ValueError, IndexError):
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        _track("WhatsApp Dead End", phone, stage="bad_selection_id", query=query)
        return
    _track("WhatsApp Product Selected", phone, title=chosen.get("title", ""), price=chosen.get("price"))
    await _send_routes_for_token(
        phone, chosen["product_token"], query, chosen.get("title", ""),
        chosen.get("price"), chosen.get("source", ""), chosen.get("thumbnail"),
        candidates=candidates,
    )


async def handle_alternatives(phone: str) -> None:
    session = session_store.get_session(phone)
    if not session:
        await send_text(phone, WHATSAPP_SESSION_EXPIRED_MSG)
        _track("WhatsApp Session Expired", phone, at="alternatives")
        return
    alternatives = session.get("routes", {}).get("alternatives", [])
    if not alternatives:
        await send_text(phone, WHATSAPP_NO_ALTERNATIVES_MSG)
        return
    _track("WhatsApp Alternatives Requested", phone, count=len(alternatives))
    rows = []
    for i, alt in enumerate(alternatives[:3]):
        merchant_name = alt.get("merchant") or f"Option {i + 1}"
        final_cost = alt.get("final_cost")
        path = "Via gift card" if alt.get("voucher") else "Direct"
        desc = f"{merchant_name} · {path} · ₹{final_cost:,.0f}" if final_cost else f"{merchant_name} · {path}"
        rows.append({
            "id": f"alt_{i}",
            "title": _truncate(merchant_name, 24),
            "description": _truncate(desc, 72),
        })
    # Marks the session as waiting on an alternative pick, mirroring
    # _send_product_picker — lets a confused reply here get redirected back
    # to this list instead of going unanswered.
    session_store.set_session(phone, {**session, "state": "awaiting_alternative_pick"})
    await send_list_message(
        phone,
        body_text="Want a different route? Pick one:",
        button_text="See options",
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
        _track("WhatsApp Session Expired", phone, at="alternative_selection")
        return
    alternatives = session.get("routes", {}).get("alternatives", [])
    try:
        idx = int(reply_id.split("_", 1)[1])
        chosen = alternatives[idx]
    except (ValueError, IndexError):
        await send_text(phone, WHATSAPP_NO_ALTERNATIVES_MSG)
        return
    _track("WhatsApp Alternative Selected", phone, merchant=chosen.get("merchant", ""))
    await _send_success_flow(phone, chosen, session.get("image"))


async def handle_pick_again(phone: str) -> None:
    session = session_store.get_session(phone)
    if not session:
        await send_text(phone, WHATSAPP_SESSION_EXPIRED_MSG)
        _track("WhatsApp Session Expired", phone, at="pick_again")
        return
    candidates = session.get("candidates", [])
    query = session.get("query", "")
    if not candidates:
        await send_text(phone, WHATSAPP_DEAD_END_MSG)
        _track("WhatsApp Dead End", phone, stage="pick_again_empty", query=query)
        return
    await _send_product_picker(phone, query, candidates, approximate=session.get("approximate", False))


async def _send_state_aware_nudge(phone: str) -> None:
    """Gentle redirect for anything that doesn't make sense right now —
    free text or a non-text message that isn't a valid reply. Never tries to
    guess what the user meant; it only re-surfaces whatever the bot is
    actually waiting on, so a confused reply never gets silence. If nothing
    is currently pending, falls back to the full onboarding message rather
    than a terser one-line nudge — user feedback 2026-08-26: a returning
    user saying "hi" should get the same welcoming, informative reply as a
    first-time one, not a stripped-down version of it."""
    session = session_store.get_session(phone)
    state = (session or {}).get("state")
    if state == "awaiting_product_pick":
        candidates = (session or {}).get("candidates") or []
        if candidates:
            await send_text(phone, WHATSAPP_PICK_REMINDER_MSG)
            await _send_product_picker(
                phone, session.get("query", ""), candidates,
                approximate=(session or {}).get("approximate", False),
            )
            return
    elif state == "awaiting_alternative_pick":
        alternatives = (session or {}).get("routes", {}).get("alternatives") or []
        if alternatives:
            await send_text(phone, WHATSAPP_PICK_REMINDER_MSG)
            await handle_alternatives(phone)
            return
    await send_text(phone, WHATSAPP_ONBOARDING_MSG)


_SEEN_MESSAGE_TTL_SECONDS = 600  # comfortably longer than Meta's webhook retry window
_seen_message_ids = TTLCache(default_ttl=_SEEN_MESSAGE_TTL_SECONDS)


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

        # Meta delivers "at least once", not "exactly once" — if our ack is
        # slow (e.g. a Render free-tier cold start), it retries the same
        # message, and without this check that meant the whole reply
        # sequence (onboarding, nudges, everything) ran twice, landing as
        # duplicate/out-of-order bubbles. The check+set below has no await
        # between them, so it's race-safe against a near-simultaneous retry
        # within this one process.
        if msg_id:
            if _seen_message_ids.get(msg_id):
                return
            _seen_message_ids.set(msg_id, True)

        _track("WhatsApp Message Received", phone, msg_type=msg_type)

        if msg_type == "interactive":
            interactive = msg.get("interactive", {})
            itype = interactive.get("type")
            if itype == "button_reply":
                reply_id = interactive["button_reply"]["id"]
                reply_title = interactive["button_reply"].get("title", reply_id)
                message_log.record(phone, "in", f"[tapped] {reply_title}")
                if reply_id == "see_alternatives":
                    await send_typing_indicator(msg_id)
                    _run_exclusive(phone, handle_alternatives(phone))
                elif reply_id == "pick_again":
                    await send_typing_indicator(msg_id)
                    _run_exclusive(phone, handle_pick_again(phone))
            elif itype == "list_reply":
                reply_id = interactive["list_reply"]["id"]
                reply_title = interactive["list_reply"].get("title", reply_id)
                message_log.record(phone, "in", f"[tapped] {reply_title}")
                if reply_id.startswith("alt_"):
                    # Not a fresh pricing search, but still a real wait —
                    # the image download/convert/upload + several message
                    # sends take noticeable time, so this gets the typing
                    # indicator too rather than assuming "cached = instant".
                    await send_typing_indicator(msg_id)
                    _run_exclusive(
                        phone, _run_with_typing_keepalive(msg_id, handle_alternative_selection(phone, reply_id))
                    )
                elif reply_id.startswith("prod_"):
                    await send_typing_indicator(msg_id)
                    _run_exclusive(
                        phone, _run_with_typing_keepalive(msg_id, handle_product_selection(phone, reply_id))
                    )
            elif itype == "nfm_reply":
                # A completed WhatsApp Flow (the photo picker) — same
                # destination as a list_reply's "prod_" branch above, just
                # arriving through the Flow's own response shape instead of
                # a plain interactive id.
                raw_response = interactive.get("nfm_reply", {}).get("response_json")
                try:
                    response = json.loads(raw_response) if raw_response else {}
                except (TypeError, ValueError):
                    response = {}
                reply_id = response.get(WHATSAPP_FLOW_FIELD_NAME)
                message_log.record(phone, "in", f"[flow pick] {reply_id or 'unknown'}")
                if reply_id and reply_id.startswith("prod_"):
                    await send_typing_indicator(msg_id)
                    _run_exclusive(
                        phone, _run_with_typing_keepalive(msg_id, handle_product_selection(phone, reply_id))
                    )
            return

        if msg_type == "text":
            text = msg["text"]["body"]
        elif msg_type in ("image", "video") and (msg.get(msg_type) or {}).get("caption"):
            # A phone's native "Share" sheet from a shopping app almost
            # always lands on WhatsApp as a photo/video with the product
            # link in its caption, not as a plain text message — Meta
            # delivers it as an "image"/"video" message either way, so
            # without this branch the caption (and any link in it) was
            # never even looked at, and this exact real-world flow (share
            # a product straight from a shopping app to Dealo) silently
            # never worked. Reuses the normal text pipeline unchanged —
            # classify_input already finds a URL anywhere in the string.
            text = msg[msg_type]["caption"]
        else:
            message_log.record(phone, "in", f"[{msg_type} message]")
            await _send_state_aware_nudge(phone)
            _track("WhatsApp Nudge Sent", phone, reason=f"non_text:{msg_type}")
            return

        message_log.record(phone, "in", text)
        # Marks this message read + shows typing immediately, regardless of
        # what it turns out to be — without this, the debounce delay below
        # would read as dead silence instead of "the bot is composing a
        # reply." A later message in the same burst re-marks/re-shows this
        # harmlessly; only one of them ends up producing an actual reply.
        await send_typing_indicator(msg_id)
        _run_exclusive(phone, _process_text_message(phone, msg_id, text))
    except (KeyError, IndexError):
        pass
    except Exception as e:
        print(f"[Webhook] handle_incoming error: {e}")


_TEXT_DEBOUNCE_SECONDS = 2  # see _process_text_message


async def _process_text_message(phone: str, msg_id: str | None, text: str) -> None:
    """The actual decide-and-reply logic for one incoming text, run only
    after a short quiet gap. Waiting first means that if another text
    arrives from the same phone in that window, _run_exclusive (see
    handle_incoming) cancels this call before it ever runs its body — so a
    quick burst of separate texts (e.g. "hi" immediately followed by
    "hello") produces exactly one reply cycle, based on the last message,
    instead of stacking one bot reply per human message. Live-tested
    2026-08-26: two greetings sent seconds apart otherwise produced three
    stacked bot messages (onboarding + two separate nudges), which read as
    overwhelming rather than responsive."""
    await asyncio.sleep(_TEXT_DEBOUNCE_SECONDS)

    is_new = session_store.is_new_user(phone)
    classification = classify_input(text)

    if is_new:
        await send_text(phone, WHATSAPP_ONBOARDING_MSG)
        _track("WhatsApp Onboarded", phone)
        if classification["type"] == "unparseable":
            # The onboarding message just sent already explains how to use
            # Dealo — immediately following it with "I didn't catch a
            # product there" on this same first turn is redundant, not
            # helpful. A later unparseable message from the same (now no
            # longer new) phone still gets the normal nudge below.
            _track(
                "WhatsApp Nudge Sent", phone,
                reason=classification.get("reason", ""), text=text, suppressed_first_time=True,
            )
            return

    if classification["type"] == "unparseable":
        await _send_state_aware_nudge(phone)
        _track("WhatsApp Nudge Sent", phone, reason=classification.get("reason", ""), text=text)
        return

    if not _search_rate_limiter.allow(phone):
        await send_text(phone, WHATSAPP_RATE_LIMITED_MSG)
        _track("WhatsApp Rate Limited", phone, query=text)
        return

    _track("WhatsApp Search", phone, query=text, input_type=classification["type"])
    await _run_with_typing_keepalive(msg_id, process_and_respond(phone, classification))
