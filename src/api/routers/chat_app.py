"""Dealo inside ChatGPT and Claude — one MCP endpoint both of them call.

    POST /mcp   JSON-RPC 2.0 (MCP over Streamable HTTP, JSON responses only)
    GET  /mcp   405 — we never push messages, so there is no event stream

Both chat apps add tools from outside servers over the same open standard
(MCP), and both draw a server's own HTML card inside the chat through its
"MCP Apps" extension. So one endpoint and one card serve both stores.

Hand-written instead of pulling in the MCP SDK: the server holds no session
and has one tool, so it needs six JSON-RPC methods and nothing else. That keeps
a new dependency (and its pins on starlette/pydantic) out of the backend.

The one tool answers "I'm spending ₹X at shop Y — how do I save?" with the
exact same lookup the Chrome extension's checkout popup uses (/voucher-check):
local catalogue files only, no paid search API, so it costs nothing to serve
and needs no rate limit.
"""
from __future__ import annotations

import difflib
import logging
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from ...config import get_settings
from ...repositories import buyhatke_repository, maximize_repository, voucher_repository
from ...services import analytics_service
from .voucher_check import voucher_check

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat-app"])

# ChatGPT caches the card for up to an hour by this address: bump the version
# whenever the card changes in a way old results can't draw.
CARD_URI = "ui://dealo/gift-card-deal-v1.html"
CARD_MIME = "text/html;profile=mcp-app"
CARD_HTML = (Path(__file__).with_name("chat_app_card.html")).read_text(encoding="utf-8")

# Newest first. We answer with the client's version when we know it, else ours.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

# Both stores reject wording that steers the model or sells, so this and the
# tool description say what Dealo does and when it fits, nothing more.
SERVER_INSTRUCTIONS = (
    "Dealo finds the cheapest way to pay at Indian shops (Myntra, Nykaa, AJIO, "
    "MakeMyTrip and about 900 more). Many shops' own gift cards are sold below "
    "face value on Gyftr, Maximize and BuyHatke; paying at the shop with one "
    "costs less than paying directly. Results cover online shopping only and leave out cashback."
)

TOOL = {
    "name": "find_gift_card_deal",
    # Shown in the chat and searched by Claude alongside the description.
    "title": "Cheapest way to pay at a shop",
    "description": (
        # Claude finds connected tools by searching their descriptions, so this
        # carries the words people actually use: "cheapest way to pay",
        # "discount", "offer", "coupon". A first version that only said "gift
        # card" was skipped for web search when asked about saving on Nykaa.
        "Use this when someone in India asks how to pay less, save money, or find "
        "a discount, offer, coupon or deal at a specific shop or brand: Myntra, "
        "Nykaa, AJIO, Tata CLiQ, Lifestyle, Skechers, boAt, Decathlon, Lenskart, "
        "FirstCry, Croma, MakeMyTrip, ixigo, PVR, BookMyShow, Zomato, BigBasket and "
        "about 900 more. Many Indian shops' own gift cards sell below face value on "
        "Gyftr, Maximize and BuyHatke, so paying at checkout with one is a direct "
        "discount anyone can use, with no bank card or coupon code needed. Returns "
        "the current best gift card price: the % off, how much to buy, and what "
        "they actually pay in rupees. Do not use it to compare products, find which "
        "store sells an item cheapest, or for shops outside India."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "shop": {
                "type": "string",
                "description": "Shop or brand name, or its website. e.g. 'Nykaa', 'tatacliq.com'",
                "maxLength": 200,
            },
            "amount_inr": {
                "type": "number",
                "description": "What they plan to spend at the shop, in rupees. Leave out if unknown.",
                "minimum": 1,
            },
        },
        "required": ["shop"],
        "additionalProperties": False,
    },
    "annotations": {
        "title": "Cheapest way to pay at a shop",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
    "_meta": {
        "ui": {"resourceUri": CARD_URI},
        # ChatGPT's older names for the same thing; harmless elsewhere.
        "openai/outputTemplate": CARD_URI,
        "openai/toolInvocation/invoking": "Checking gift card deals…",
        "openai/toolInvocation/invoked": "Checked gift card deals",
    },
}

CARD_RESOURCE = {
    "uri": CARD_URI,
    "name": "Dealo gift card deal",
    "description": "The deal Dealo found: what to buy, where, and what you pay.",
    "mimeType": CARD_MIME,
}

_SOURCE_NAMES = {"gyftr": "Gyftr", "maximize": "Maximize", "buyhatke": "BuyHatke"}


def _surface(request: Request) -> str:
    """Which chat app is calling, from its user agent. Only used to tell the
    two apart in Mixpanel; an unknown caller still gets a full answer."""
    ua = request.headers.get("user-agent", "").lower()
    if "openai" in ua or "chatgpt" in ua:
        return "chatgpt"
    if "claude" in ua or "anthropic" in ua:
        return "claude"
    return "chat_app"


def _shop_key(shop: str) -> str:
    """'Tata CLiQ' -> 'tatacliq'; 'https://www.nykaa.com/x' -> 'nykaa.com'.
    voucher_check takes a website or a bare brand label, never a spaced name."""
    text = shop.strip().lower()
    if "/" in text or "." in text:
        host = urlparse(text if "://" in text else f"https://{text}").netloc
        if host:
            return host.removeprefix("www.")
    return re.sub(r"[^a-z0-9]", "", text)


def _pct(value: float | None) -> str:
    return f"{value:g}%" if value is not None else ""


@lru_cache(maxsize=1)
def _brand_names() -> dict[str, str]:
    """Every catalogue brand, keyed by its squashed name ('tatacliq')."""
    records = (
        voucher_repository.all_vouchers()
        + maximize_repository.all_brands()
        + buyhatke_repository.all_brands()
    )
    return {
        re.sub(r"[^a-z0-9]", "", (r.get("brand_name") or "").lower()): r["brand_name"]
        for r in records if r.get("brand_name")
    }


@lru_cache(maxsize=1)
def _checked_on() -> str:
    """When the voucher sites were last read ('28 Sep'). Rates move between
    refreshes, so every answer says how old it is."""
    days = [
        str(p.get("last_scraped") or "")[:10]
        for r in voucher_repository.all_vouchers() + maximize_repository.all_brands() + buyhatke_repository.all_brands()
        for p in r.get("products") or []
    ]
    latest = max((d for d in days if len(d) == 10), default="")
    try:
        return date.fromisoformat(latest).strftime("%-d %b")
    except ValueError:
        return ""


def _redeem_steps(deal: dict) -> str:
    """The seller's own 'how to use it' steps, short enough to retell."""
    steps = [s.strip() for s in deal.get("how_to_redeem_steps") or [] if s and s.strip()]
    text = " ".join(f"({i}) {s}" for i, s in enumerate(steps[:4], 1))
    return text if len(text) <= 600 else text[:597].rsplit(" ", 1)[0] + "…"


def _closest_shop(key: str) -> str | None:
    """'sketchers' -> 'skechers'. A wrong shop is worse than none, so only a
    near-identical spelling of a name long enough to be distinctive counts."""
    if len(key) < 5 or "." in key:
        return None
    hit = difflib.get_close_matches(key, _brand_names().keys(), n=1, cutoff=0.88)
    return hit[0] if hit else None


def _rupees(value: float | None) -> str:
    return f"₹{value:,.0f}" if value is not None else ""


def _origin(request: Request) -> str:
    """This server's own https origin as the caller reached it."""
    base_url = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://", 1)
    return base_url


def _deal_for_card(deal: dict, base_url: str, surface: str) -> dict:
    """The fields the card draws, plus a logged link to the voucher site."""
    url = deal.get("voucher_url") or ""
    buy_url = (
        f"{base_url}/out?url={quote(url, safe='')}&surface={surface}&ctx=chat_card"
        if url else ""
    )
    keep = (
        "brand_name", "voucher_source", "pct", "card_pct", "saving", "effective_price",
        "priced", "voucher_amount", "purchase_breakdown", "txns_needed", "remainder",
        "restrictions", "choice_label", "covers",
    )
    out = {k: deal.get(k) for k in keep}
    out["source_name"] = _SOURCE_NAMES.get(deal.get("voucher_source") or "", deal.get("voucher_source"))
    out["buy_url"] = buy_url
    out["checked_on"] = _checked_on()
    return out


def _summary(shop: str, amount: float | None, deal: dict, choices: list[dict]) -> str:
    """What the chat model reads. Plain sentences so it can retell them, and
    complete on its own for any app that can't show the card."""
    if not deal.get("has_voucher"):
        return (
            f"Dealo has no gift card discount for '{shop}' right now "
            "(it checks Gyftr, Maximize and BuyHatke)."
        )
    if choices:
        lines = [
            f"- {c.get('choice_label') or c.get('brand_name')}: {_pct(c.get('pct'))} off on "
            f"{_SOURCE_NAMES.get(c.get('voucher_source'), c.get('voucher_source'))}"
            + (f", saves {_rupees(c.get('saving'))}" if c.get("priced") else "")
            for c in choices
        ]
        return (
            f"{shop} has different gift cards for different purchases. "
            "Which one applies depends on what is being bought:\n" + "\n".join(lines)
        )
    source = _SOURCE_NAMES.get(deal.get("voucher_source"), deal.get("voucher_source"))
    if not deal.get("priced"):
        return (
            f"{deal['brand_name']}: {_pct(deal.get('pct'))} off. Buy {deal['brand_name']} gift "
            f"cards on {source} (pay by UPI), then pay with them at checkout. The rupee "
            "saving depends on the amount spent."
        ) + _footnote(deal)
    text = (
        f"{deal['brand_name']}: buy {deal.get('purchase_breakdown')} of {deal['brand_name']} "
        f"gift cards on {source}, paying by UPI. They pay {_rupees(deal.get('effective_price'))} "
        f"for {_rupees(amount)} of shopping: {_pct(deal.get('pct'))} off, saving {_rupees(deal.get('saving'))}. "
        f"Then choose gift card as the payment method at {deal['brand_name']} checkout."
    )
    if (deal.get("txns_needed") or 1) > 1:
        text += f" The site sells these in {deal['txns_needed']} separate purchases."
    if deal.get("remainder"):
        text += f" {_rupees(deal['remainder'])} is left to pay normally."
    if deal.get("card_pct") is not None and deal["card_pct"] != deal.get("pct"):
        text += f" Paying for the gift card by card instead of UPI gives {_pct(deal['card_pct'])}."
    if deal.get("restrictions"):
        text += " Can't be used for: " + "; ".join(deal["restrictions"])
    return text + _footnote(deal)


def _footnote(deal: dict) -> str:
    out = ""
    steps = _redeem_steps(deal)
    if steps:
        out += f" How to use it at {deal['brand_name']}: {steps.rstrip('.')}."
    if _checked_on():
        out += f" Rates as of {_checked_on()}; the voucher site shows today's price before paying."
    return out


def _find_deal(args: dict, request: Request) -> dict:
    shop = str(args.get("shop") or "").strip()
    if not shop:
        return {"content": [{"type": "text", "text": "Which shop? Give a shop name or website."}], "isError": True}
    amount = args.get("amount_inr")
    amount = float(amount) if isinstance(amount, (int, float)) and amount > 0 else None

    key = _shop_key(shop)
    try:
        deal = voucher_check(key, amount)
        if not deal.get("has_voucher"):
            closest = _closest_shop(key)
            if closest:
                deal = voucher_check(closest, amount)
    except Exception:
        logger.exception("[chat_app] lookup failed for %r", shop)
        return {"content": [{"type": "text", "text": (
            f"Dealo couldn't check '{shop}' just now because of a problem on Dealo's side. "
            "Trying again in a minute usually works."
        )}], "isError": True}
    choices = deal.get("product_choices") or []
    surface = _surface(request)
    base_url = _origin(request)

    logger.info("[chat_app] %s lookup %r amount=%s -> %s %s%%", _surface(request), shop[:60], amount,
                deal.get("brand_name"), deal.get("pct"))
    analytics_service.fire(analytics_service.build_event(
        "Chat App Lookup",
        surface=surface,
        properties={
            "shop_query": shop[:100],
            "amount": amount,
            "has_voucher": bool(deal.get("has_voucher")),
            "brand": deal.get("brand_name") or "",
            "pct": deal.get("pct"),
            "choices": len(choices),
        },
    ))

    structured = {
        "shop": shop,
        "amount": amount,
        "has_voucher": bool(deal.get("has_voucher")),
        "deal": _deal_for_card(deal, base_url, surface) if deal.get("has_voucher") else None,
        "choices": [_deal_for_card(c, base_url, surface) for c in choices],
    }
    return {
        "content": [{"type": "text", "text": _summary(shop, amount, deal, choices) + _links(structured)}],
        "structuredContent": structured,
        "isError": False,
    }


def _links(structured: dict) -> str:
    """The buy links, in words too. In a follow-up ("kaise lu gift card?")
    Claude retells an earlier result instead of calling again, so no card is
    drawn; without the link in the text the shopper is left with no way to
    buy. Seen in the founder's first live test, 2026-10-03."""
    if structured.get("choices"):
        return " Buy links: " + "; ".join(
            f"{c.get('choice_label') or c.get('brand_name')}: {c['buy_url']}"
            for c in structured["choices"] if c.get("buy_url")
        )
    deal = structured.get("deal")
    if deal and deal.get("buy_url"):
        return f" Buy the gift card on {deal.get('source_name')}: {deal['buy_url']}"
    return ""


def _ok(rpc_id, result: dict) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})


def _error(rpc_id, code: int, message: str) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}})


@router.post("/mcp")
async def mcp(request: Request) -> Response:
    try:
        msg = await request.json()
    except Exception:
        return _error(None, -32700, "Parse error")
    if not isinstance(msg, dict):
        return _error(None, -32600, "Send one JSON-RPC message per request")

    method = msg.get("method")
    rpc_id = msg.get("id")
    params = msg.get("params") or {}

    # Notifications (no id) and replies to us (no method) need no answer.
    if rpc_id is None or method is None:
        return Response(status_code=202)

    if method == "initialize":
        asked = params.get("protocolVersion")
        return _ok(rpc_id, {
            "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}},
            "serverInfo": {"name": "dealo", "title": "Dealo", "version": "1.0.0"},
            "instructions": SERVER_INSTRUCTIONS,
        })
    if method == "ping":
        return _ok(rpc_id, {})
    if method == "tools/list":
        return _ok(rpc_id, {"tools": [TOOL]})
    if method == "tools/call":
        if params.get("name") != TOOL["name"]:
            return _error(rpc_id, -32602, f"Unknown tool: {params.get('name')}")
        return _ok(rpc_id, _find_deal(params.get("arguments") or {}, request))
    if method == "resources/list":
        return _ok(rpc_id, {"resources": [CARD_RESOURCE]})
    if method == "resources/templates/list":
        return _ok(rpc_id, {"resourceTemplates": []})
    if method == "prompts/list":
        return _ok(rpc_id, {"prompts": []})
    if method == "resources/read":
        if params.get("uri") != CARD_URI:
            return _error(rpc_id, -32002, "Resource not found")
        return _ok(rpc_id, {"contents": [{
            "uri": CARD_URI,
            "mimeType": CARD_MIME,
            "text": CARD_HTML,
            "_meta": {
                # The card loads nothing from outside; links open through the host.
                "ui": {"csp": {"connectDomains": [], "resourceDomains": []}, "prefersBorder": True},
                # ChatGPT opens only links on this list. Buy goes via our own /out
                # (to count the click) and lands on one of the voucher sites.
                "openai/widgetCSP": {
                    "connect_domains": [],
                    "resource_domains": [],
                    "redirect_domains": [
                        _origin(request), "https://www.gyftr.com", "https://www.maximize.money",
                        "https://buyhatke.com", "https://www.buyhatke.com",
                    ],
                },
                "openai/widgetDomain": "https://getdealo.in",
                "openai/widgetPrefersBorder": True,
                "openai/widgetDescription": "Shows the gift card to buy, where, and what you pay.",
            },
        }]})
    return _error(rpc_id, -32601, f"Method not found: {method}")


@router.get("/.well-known/openai-apps-challenge")
async def openai_apps_challenge() -> Response:
    token = get_settings().OPENAI_APPS_CHALLENGE
    return PlainTextResponse(token) if token else Response(status_code=404)


@router.get("/mcp")
async def mcp_stream() -> Response:
    return Response(status_code=405, headers={"Allow": "POST"})
