"""Affiliate click redirect.

Merchant links are wrapped for commission tracking, but sending users
straight to linksredirect.com / inr.deals (with a tracking id in plain
view) reads as a suspicious third-party redirect. Routing the click through
our own domain first — /go?url=... — hides that hop behind a domain users
already trust, then forwards to whichever network should get this brand.

Which network that is comes from data/affiliate_coverage.json (see
scripts/refresh_affiliate_coverage.py): most brands default to Cuelinks
unchanged, but a brand can route through INRDeals instead when it pays
better there, or when it's the only network that carries it at all (e.g.
Amazon, which has no Cuelinks program). A brand with no live campaign on
either network still falls through to the Cuelinks default — unwrapped,
that click would earn nothing at all either way, so this is never a
regression versus the old always-Cuelinks behavior.
"""
from __future__ import annotations

from urllib.parse import quote, urlparse

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from ...config import get_settings
from ...constants import CUELINKS_BASE, INRDEALS_BASE
from ...repositories.affiliate_coverage_repository import network_for_brand
from ...repositories.domain_brand_repository import brand_for_domain

router = APIRouter(tags=["redirect"])


@router.get("/go")
async def go(url: str = Query(..., min_length=1)) -> RedirectResponse:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    settings = get_settings()

    brand = brand_for_domain(parsed.netloc)
    coverage = network_for_brand(brand) if brand else None

    if coverage and coverage.get("network") == "inrdeals":
        target = INRDEALS_BASE.format(
            publisher_id=settings.INRDEALS_PUBLISHER_ID,
            campaign_type=coverage["inrdeals_campaign_type"],
            url=quote(url, safe=""),
        )
    else:
        target = CUELINKS_BASE.format(cid=settings.CUELINKS_CID, url=quote(url, safe=""))

    return RedirectResponse(target, status_code=302)
