"""Server-side Mixpanel event tracking for the WhatsApp bot.

Mirrors react/src/utils/analytics.js's project (same Mixpanel token, same
EU data-residency endpoint — the default US host silently drops events for
an EU-residency token) but identifies WhatsApp users by phone number
instead of an anonymous browser id, and tags every event with
channel="whatsapp" so it stays filterable from, or comparable to, web
events in the same project.
"""
from __future__ import annotations

import time

import httpx

from ..config import get_settings

_TRACK_URL = "https://api-eu.mixpanel.com/track"


async def track(event: str, phone: str, properties: dict | None = None) -> None:
    """Fire-and-forget event send. Never raises — a Mixpanel outage must
    never affect the WhatsApp bot's replies (same defensive stance as
    send_typing_indicator in whatsapp_service.py). Callers should wrap this
    in asyncio.create_task so a slow Mixpanel response can't delay a reply."""
    settings = get_settings()
    token = settings.MIXPANEL_TOKEN
    if not token:
        return
    payload = [{
        "event": event,
        "properties": {
            "token": token,
            "distinct_id": f"wa:{phone}",
            "time": int(time.time()),
            "channel": "whatsapp",
            "phone": phone,
            **(properties or {}),
        },
    }]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                _TRACK_URL,
                json=payload,
                headers={"Accept": "text/plain"},
                params={"ip": "0"},
            )
            print(f"[Analytics] {event} -> {r.status_code} | {r.text}")
    except Exception as e:
        print(f"[Analytics] track failed for {event}: {e}")
