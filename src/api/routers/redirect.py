"""Outbound click redirects — the one place every click out of Dealo is logged.

/go   a shop link. Wrapped for commission (Cuelinks, or INRDeals where
      data/affiliate_coverage.json says so), stamped with our own ids so a
      sale the network reports later can be matched back to the person and
      the click: subid = the person's device id, subid2 = click id,
      subid3 = surface. Routing through our own domain also hides the
      third-party tracking hop behind a domain users already trust.
/out  a voucher-partner or card-application link. Not an affiliate link,
      just logged and forwarded — limited to known partner hosts so it can't
      be used as an open redirect.

Query parameters shared by both: surface (web / whatsapp / extension),
did (the person's anonymous device id, absent when the visitor hasn't
consented), ctx (where on the surface the link was, e.g. checkout_step).

Link-preview bots (WhatsApp, Facebook, Slack...) fetch these URLs too; their
hits are still redirected but tagged is_bot so dashboards can drop them.
"""
from __future__ import annotations

import re
import uuid
from urllib.parse import quote, urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from ...config import get_settings
from ...constants import CUELINKS_BASE, INRDEALS_BASE, OUTBOUND_ALLOWED_HOSTS
from ...repositories.affiliate_coverage_repository import network_for_brand
from ...repositories.domain_brand_repository import brand_for_domain
from ...services import analytics_service

router = APIRouter(tags=["redirect"])

SURFACES = {"web", "whatsapp", "extension"}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CTX_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_BOT_UA_RE = re.compile(
    r"bot|crawl|spider|preview|facebookexternalhit|whatsapp|slack|telegram|discord|skype|curl|python-|headless",
    re.IGNORECASE,
)


def _clean(value: str | None, pattern: re.Pattern) -> str | None:
    return value if value and pattern.match(value) else None


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _host_allowed(host: str) -> bool:
    host = host.lower().split(":")[0]
    return any(host == h or host.endswith("." + h) for h in OUTBOUND_ALLOWED_HOSTS)


def _context(request: Request, surface: str | None, did: str | None, ctx: str | None) -> tuple[str, str | None, dict]:
    surface = surface if surface in SURFACES else "unknown"
    did = _clean(did, _ID_RE)
    ua = request.headers.get("user-agent", "")
    props = {
        "ctx": _clean(ctx, _CTX_RE) or "unknown",
        "is_bot": bool(_BOT_UA_RE.search(ua)) or not ua,
        "referrer": request.headers.get("referer", "")[:200],
    }
    return surface, did, props


def _parse_http_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="url must be http(s)")
    return parsed


@router.get("/go")
async def go(
    request: Request,
    url: str = Query(..., min_length=1),
    surface: str | None = None,
    did: str | None = None,
    ctx: str | None = None,
) -> RedirectResponse:
    parsed = _parse_http_url(url)
    settings = get_settings()
    surface, did, props = _context(request, surface, did, ctx)
    click_id = uuid.uuid4().hex[:16]
    subid = did or "anon"

    brand = brand_for_domain(parsed.netloc)
    coverage = network_for_brand(brand) if brand else None

    if coverage and coverage.get("network") == "inrdeals":
        network = "inrdeals"
        target = INRDEALS_BASE.format(
            publisher_id=settings.INRDEALS_PUBLISHER_ID,
            campaign_type=coverage["inrdeals_campaign_type"],
            url=quote(url, safe=""),
        )
    else:
        network = "cuelinks"
        target = CUELINKS_BASE.format(cid=settings.CUELINKS_CID, url=quote(url, safe=""))
    target += f"&subid={subid}&subid2={click_id}&subid3={surface}"

    analytics_service.fire(analytics_service.build_event(
        "Shop Link Opened",
        surface=surface,
        device_id=did,
        ip=_client_ip(request) if did else None,
        insert_id=click_id,
        properties={
            **props,
            "click_id": click_id,
            "brand": brand or "",
            "shop_domain": parsed.netloc.lower(),
            "shop_url": url[:500],
            "network": network,
        },
    ))
    return RedirectResponse(target, status_code=302)


@router.get("/out")
async def out(
    request: Request,
    url: str = Query(..., min_length=1),
    kind: str = Query("voucher_site"),
    surface: str | None = None,
    did: str | None = None,
    ctx: str | None = None,
) -> RedirectResponse:
    parsed = _parse_http_url(url)
    if not _host_allowed(parsed.netloc):
        raise HTTPException(status_code=400, detail="destination not allowed")
    surface, did, props = _context(request, surface, did, ctx)
    event = "Card Link Opened" if kind == "card_apply" else "Voucher Site Opened"

    analytics_service.fire(analytics_service.build_event(
        event,
        surface=surface,
        device_id=did,
        ip=_client_ip(request) if did else None,
        properties={
            **props,
            "destination_domain": parsed.netloc.lower(),
            "destination_url": url[:500],
        },
    ))
    return RedirectResponse(url, status_code=302)
