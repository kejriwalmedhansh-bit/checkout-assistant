"""Affiliate click redirect.

Merchant links are wrapped through Cuelinks for commission tracking, but
sending users straight to linksredirect.com (with a "cid=" tracking param
in plain view) reads as a suspicious third-party redirect. Routing the
click through our own domain first — /go?url=... — hides that hop behind
a domain users already trust, then forwards to Cuelinks unchanged.
"""
from __future__ import annotations

from urllib.parse import quote, urlparse

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from ...config import get_settings
from ...constants import CUELINKS_BASE

router = APIRouter(tags=["redirect"])


@router.get("/go")
async def go(url: str = Query(..., min_length=1)) -> RedirectResponse:
    if urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="url must be http(s)")
    settings = get_settings()
    target = CUELINKS_BASE.format(cid=settings.CUELINKS_CID, url=quote(url, safe=""))
    return RedirectResponse(target, status_code=302)
