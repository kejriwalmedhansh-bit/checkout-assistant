"""Context.dev page reader — renders a blocked store page and returns its HTML.

Dealo's first reader for every blocked store page — Flipkart's own search
page (flipkart_repository), pasted product links and the winner price
re-check (search_service) — with Crawlbase as the fallback; replaced Apify
2026-10-26. Owner-run comparison 2026-10-03: on 8 blocked
store product pages Context.dev read 8/8 (Crawlbase 6/8, missing AJIO and
Myntra), with identical titles and prices; on 16 Flipkart searches it
averaged 5.2s (max 7s) against Crawlbase's 9.7s (max 18s), finding the same
products at the same prices. 1 credit per page, render and anti-bot
included.

Same contract as crawlbase_repository: never raises, returns None on any
failure so the caller falls through to the next reader.
"""
from __future__ import annotations

import logging
import time

import httpx

from ..cache import search_cache
from ..config import get_settings

logger = logging.getLogger("uvicorn.error")

CONTEXT_DEV_SCRAPE_URL = "https://api.context.dev/v1/web/scrape"


def fetch_rendered_html(url: str) -> str | None:
    """The rendered page's full HTML for `url`, or None on any failure."""
    settings = get_settings()
    if not settings.CONTEXT_DEV_API_KEY:
        logger.info("[context.dev] no CONTEXT_DEV_API_KEY configured — not run")
        return None

    cache_key = ("context.dev", url)
    cached = search_cache.get(cache_key)
    if cached is not None:
        return cached

    started = time.monotonic()
    try:
        with httpx.Client(timeout=float(settings.CONTEXT_DEV_TIMEOUT)) as client:
            resp = client.post(
                CONTEXT_DEV_SCRAPE_URL,
                headers={"Authorization": f"Bearer {settings.CONTEXT_DEV_API_KEY}"},
                json={"url": url, "formats": {"html": True},
                      "maxAgeMs": settings.CONTEXT_DEV_MAX_AGE_MS},
            )
        if resp.status_code == 429:
            # Free plan: one read at a time per account. Waiting would hold
            # the shopper up; the caller's Crawlbase fallback answers instead.
            logger.info("[context.dev] busy (%s) — %s left to the next reader",
                        resp.headers.get("x-ratelimit-mode") or "rate limit", url)
            return None
        resp.raise_for_status()
        html = ((resp.json() or {}).get("html") or {}).get("data") or ""
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("[context.dev] fetch for %s failed after %.1fs: %s: %s",
                    url, time.monotonic() - started, type(exc).__name__, exc)
        return None

    if not html:
        logger.info("[context.dev] %s returned no HTML", url)
        return None
    logger.info("[context.dev] fetch for %s ok in %.1fs", url, time.monotonic() - started)
    search_cache.set(cache_key, html)
    return html
