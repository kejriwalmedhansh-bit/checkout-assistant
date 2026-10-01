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

import re
from pathlib import Path
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from ...services import analytics_service
from .voucher_check import voucher_check

router = APIRouter(tags=["chat-app"])

CARD_URI = "ui://dealo/gift-card-deal.html"
CARD_MIME = "text/html;profile=mcp-app"
CARD_HTML = (Path(__file__).with_name("chat_app_card.html")).read_text(encoding="utf-8")

# Newest first. We answer with the client's version when we know it, else ours.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

SERVER_INSTRUCTIONS = (
    "Dealo finds the cheapest way to pay at Indian online shops: buy the shop's "
    "own gift card at a discount (from Gyftr, Maximize or BuyHatke), then pay "
    "with it at checkout. Call find_gift_card_deal whenever someone is about to "
    "buy from an Indian shop or brand and wants to save. Cashback is never "
    "counted as a saving. Never promise a discount the tool did not return."
)

TOOL = {
    "name": "find_gift_card_deal",
    "title": "Find a gift card discount",
    "description": (
        "Find how much someone saves at an Indian shop (Myntra, Nykaa, AJIO, Tata "
        "CLiQ, MakeMyTrip, Croma, and ~900 more) by first buying that shop's "
        "discounted gift card on Gyftr, Maximize or BuyHatke. Give the shop name "
        "or website, and the amount in rupees if known. Returns the voucher site, "
        "the discount, how much to buy, and what they actually pay."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "shop": {
                "type": "string",
                "description": "Shop or brand name, or its website. e.g. 'Nykaa', 'tatacliq.com'",
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
        "title": "Find a gift card discount",
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


def _rupees(value: float | None) -> str:
    return f"₹{value:,.0f}" if value is not None else ""


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
    return out


def _summary(shop: str, amount: float | None, deal: dict, choices: list[dict]) -> str:
    """What the chat model reads. Plain sentences so it can retell them, and
    complete on its own for any app that can't show the card."""
    if not deal.get("has_voucher"):
        return (
            f"Dealo has no gift card discount for '{shop}' right now (it checks "
            "Gyftr, Maximize and BuyHatke). Don't suggest a gift card for this shop."
        )
    if choices:
        lines = [
            f"- {c.get('choice_label') or c.get('brand_name')}: {_pct(c.get('pct'))} off on "
            f"{_SOURCE_NAMES.get(c.get('voucher_source'), c.get('voucher_source'))}"
            + (f", saves {_rupees(c.get('saving'))}" if c.get("priced") else "")
            for c in choices
        ]
        return (
            f"{shop} sells different gift cards for different things. "
            "Ask what they are buying, then point them to the matching card:\n" + "\n".join(lines)
        )
    source = _SOURCE_NAMES.get(deal.get("voucher_source"), deal.get("voucher_source"))
    if not deal.get("priced"):
        return (
            f"{deal['brand_name']}: {_pct(deal.get('pct'))} off. Buy {deal['brand_name']} gift "
            f"cards on {source} (pay by UPI), then pay with them at checkout. Ask how much "
            "they plan to spend to work out the exact saving."
        )
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
    return text


def _find_deal(args: dict, request: Request) -> dict:
    shop = str(args.get("shop") or "").strip()
    if not shop:
        return {"content": [{"type": "text", "text": "Which shop? Give a shop name or website."}], "isError": True}
    amount = args.get("amount_inr")
    amount = float(amount) if isinstance(amount, (int, float)) and amount > 0 else None

    deal = voucher_check(_shop_key(shop), amount)
    choices = deal.get("product_choices") or []
    surface = _surface(request)
    base_url = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https":
        base_url = base_url.replace("http://", "https://", 1)

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
        "content": [{"type": "text", "text": _summary(shop, amount, deal, choices)}],
        "structuredContent": structured,
        "isError": False,
    }


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
                "openai/widgetPrefersBorder": True,
                "openai/widgetDescription": "Shows the gift card to buy, where, and what you pay.",
            },
        }]})
    return _error(rpc_id, -32601, f"Method not found: {method}")


@router.get("/mcp")
async def mcp_stream() -> Response:
    return Response(status_code=405, headers={"Allow": "POST"})
