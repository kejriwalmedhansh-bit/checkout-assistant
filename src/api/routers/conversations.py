"""Admin-only WhatsApp conversation viewer.

Reads from message_log (in-memory, see src/message_log.py) — a plain list of
phone numbers, each opening into a readable transcript. Built as a manual QA
tool: after any change to the WhatsApp bot, spot-check real conversations
(or replay a few test ones) to confirm nothing went silent or broke.

Gated by a single shared password (ADMIN_PASSWORD) rather than real
authentication — deliberately minimal, matches the "just for you" scope.
Returns 404 (not 401/403) when unconfigured or the password is wrong, so an
unset/incorrect key doesn't even reveal the endpoint exists.
"""
from __future__ import annotations

import hmac
from html import escape
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from ... import message_log
from ...config import get_settings

router = APIRouter(tags=["admin"])


def _check_key(key: str) -> None:
    settings = get_settings()
    if not settings.ADMIN_PASSWORD or not hmac.compare_digest(key, settings.ADMIN_PASSWORD):
        raise HTTPException(status_code=404)


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 640px; margin: 24px auto; padding: 0 16px; color: #222; }}
a {{ color: #0a7; text-decoration: none; }}
.bubble {{ padding: 8px 12px; border-radius: 10px; margin: 6px 0; max-width: 80%; white-space: pre-wrap; }}
.in {{ background: #eee; margin-right: auto; }}
.out {{ background: #dcf8c6; margin-left: auto; text-align: left; }}
.row {{ display: flex; }}
.ts {{ font-size: 11px; color: #888; margin: 2px 0 10px; }}
li {{ margin: 6px 0; }}
</style></head><body>{body}</body></html>"""


@router.get("/admin/conversations", response_class=HTMLResponse)
async def list_conversations(key: str = Query(...)) -> str:
    _check_key(key)
    phones = message_log.list_phones()
    if not phones:
        return _page("Conversations", "<h1>Conversations</h1><p>No messages logged yet.</p>")
    items = "".join(
        f'<li><a href="/admin/conversations/{escape(p)}?key={escape(key)}">{escape(p)}</a></li>'
        for p in phones
    )
    return _page("Conversations", f"<h1>Conversations</h1><ul>{items}</ul>")


@router.get("/admin/conversations/{phone}", response_class=HTMLResponse)
async def view_conversation(phone: str, key: str = Query(...)) -> str:
    _check_key(key)
    messages = message_log.get_conversation(phone)
    if not messages:
        raise HTTPException(status_code=404, detail="No messages logged for this number")
    bubbles = []
    for m in messages:
        when = datetime.fromtimestamp(m["ts"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        cls = "out" if m["direction"] == "out" else "in"
        bubbles.append(
            f'<div class="row"><div class="bubble {cls}">{escape(m["text"])}<div class="ts">{when}</div></div></div>'
        )
    back = f'<p><a href="/admin/conversations?key={escape(key)}">&larr; All conversations</a></p>'
    return _page(f"Conversation with {phone}", f"<h1>{escape(phone)}</h1>{back}{''.join(bubbles)}")
