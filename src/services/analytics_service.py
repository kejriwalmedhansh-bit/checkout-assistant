"""Server-side Mixpanel events: the one sender every backend event goes through.

Same Mixpanel project as the website (react/src/utils/analytics.js) and the
extension. Every event name must be listed in tracking-plan.json at the repo
root — tests/test_tracking_plan.py fails the build otherwise.

Identity follows Mixpanel's Simplified ID Merge (confirmed on this project:
events carry $device_id / $user_id):
  - $device_id  an anonymous id. Website and extension ids arrive as `did` on
                /go and /out. A WhatsApp phone gets a scrambled one from
                whatsapp_device_id() — that is the id that leaves our systems
                (affiliate sub-ids), never the phone number itself.
  - $user_id    a known person. Only WhatsApp has one: wa:<phone>.
The first event carrying both joins every earlier event of that device to
the person, which is how a website visit, an affiliate click and a purchase
reported days later all land on one WhatsApp user.

The EU host matters: the default US host silently drops events for an
EU-residency token while still answering 200.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
import uuid

import httpx

from ..config import get_settings

logger = logging.getLogger("uvicorn.error")

_TRACK_URL = "https://api-eu.mixpanel.com/track"

_background_tasks: set[asyncio.Task] = set()


def environment() -> str:
    # Render sets RENDER=true on every service it runs; scheduled jobs outside
    # Render (GitHub Actions) set DEALO_ENVIRONMENT themselves.
    if os.environ.get("DEALO_ENVIRONMENT"):
        return os.environ["DEALO_ENVIRONMENT"]
    return "production" if os.environ.get("RENDER") else "development"


def app_version() -> str:
    return (os.environ.get("RENDER_GIT_COMMIT") or os.environ.get("GITHUB_SHA") or "dev")[:7]


def whatsapp_device_id(phone: str) -> str:
    """Stable scrambled id for a phone. Must never change once live: purchases
    reported weeks later are matched on it."""
    secret = get_settings().ANALYTICS_ID_SECRET.encode()
    digest = hmac.new(secret, phone.encode(), hashlib.sha256).hexdigest()
    return f"wa-{digest[:24]}"


def is_internal_phone(phone: str) -> bool:
    settings = get_settings()
    internal = {p.strip() for p in settings.INTERNAL_PHONES.split(",") if p.strip()}
    if settings.WHATSAPP_ADMIN_PHONE:
        internal.add(settings.WHATSAPP_ADMIN_PHONE)
    return phone in internal


def build_event(
    event: str,
    *,
    surface: str,
    device_id: str | None = None,
    user_id: str | None = None,
    properties: dict | None = None,
    ip: str | None = None,
    timestamp: float | None = None,
    insert_id: str | None = None,
) -> dict:
    settings = get_settings()
    props: dict = {
        "token": settings.MIXPANEL_TOKEN,
        "time": int((timestamp or time.time()) * 1000),
        "$insert_id": insert_id or uuid.uuid4().hex,
        "surface": surface,
        "environment": environment(),
        "app_version": app_version(),
    }
    if user_id:
        props["distinct_id"] = user_id
        props["$user_id"] = user_id
    if device_id:
        props["$device_id"] = device_id
        props["dealo_id"] = device_id
        props.setdefault("distinct_id", f"$device:{device_id}")
    if not user_id and not device_id:
        # No id means the visitor hasn't agreed to be recorded (website) —
        # counted, but never told apart from anyone else.
        props["distinct_id"] = "anonymous"
    if ip:
        props["ip"] = ip
    props.update(properties or {})
    return {"event": event, "properties": props}


async def send(events: list[dict]) -> bool:
    """Never raises: analytics must never break a reply or a redirect."""
    if not events or not get_settings().MIXPANEL_TOKEN:
        return False
    # ip=1 lets Mixpanel geolocate from the "ip" property we set; events
    # without one get no location (the request itself comes from our server).
    params = {"ip": "1" if any("ip" in e["properties"] for e in events) else "0", "verbose": "1"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(_TRACK_URL, json=events, params=params)
        ok = r.status_code == 200 and '"status":1' in r.text.replace(" ", "")
        if not ok:
            logger.warning("[analytics] rejected %s: %s %s", [e["event"] for e in events], r.status_code, r.text[:300])
        return ok
    except Exception as exc:
        logger.warning("[analytics] send failed for %s: %s", [e["event"] for e in events], exc)
        return False


def fire(event_payload: dict) -> None:
    """Schedule a send without waiting for it. Keeps a reference so the task
    isn't garbage-collected mid-flight."""
    task = asyncio.create_task(send([event_payload]))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def whatsapp_event(event: str, phone: str, properties: dict | None = None, *, device_id: str | None = None) -> dict:
    return build_event(
        event,
        surface="whatsapp",
        user_id=f"wa:{phone}",
        device_id=device_id or whatsapp_device_id(phone),
        properties={
            "channel": "whatsapp",
            "phone": phone,
            "is_internal_tester": is_internal_phone(phone),
            **(properties or {}),
        },
    )

