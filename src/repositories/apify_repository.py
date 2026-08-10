"""Apify anti-bot fallback for merchant hosts that block Dealo's own direct
page fetch (see search_service._fetch_url_page / _APIFY_MERCHANT_HOSTS).

Same shape and error-handling contract as searchapi_repository.py: never
raises, returns None on any failure so a caller can fall through to today's
weaker (search-index) price rather than break.

Design note (2026-08-06, after real testing): the first version of this file
tried 4 brand-specific, third-party Apify "actors" that both fetch *and*
parse the page themselves. Real testing against actual pasted product links
found this unreliable — Myntra/Nykaa's actors returned empty on a direct
product URL, Flipkart's either didn't support product URLs or were broken,
and AJIO's actor wasn't even URL-aware — given a real product link it
silently returned a completely different, wrong product at a confident
price. That's the wrong place to put trust.

Current approach: use Apify's own official `apify/web-scraper` actor purely
as a bot-wall-bypassing *fetcher* (real browser + residential proxy, hands
back the rendered page), then run that HTML through search_service's own
already-hand-verified `_extract_jsonld_price` — the exact same trusted
extraction path already used for Amazon, Myntra, Reliance Digital, and 20+
other working brands. Apify's only job is "get me the real page"; Dealo
still decides what the price actually is. Verified 2026-08-06 against real
Flipkart, AJIO, and Nykaa product pages, each cross-checked against an
independent price source before being trusted (see fetch_rendered_html /
search_service._APIFY_MERCHANT_HOSTS).
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from ..cache import search_cache
from ..config import get_settings

logger = logging.getLogger("uvicorn.error")

APIFY_RUN_SYNC_BASE = "https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"

# Plain JS, not jQuery — the actor's injectJQuery option didn't actually
# expose `$` inside the page function in testing ("$ is not a function"),
# so this reads the DOM directly instead.
_RENDER_PAGE_FUNCTION = (
    "async function pageFunction(context) { "
    "return { url: context.request.url, html: document.documentElement.outerHTML }; "
    "}"
)


def _run_actor(actor_id: str, run_input: dict) -> list[dict] | None:
    settings = get_settings()
    if not settings.APIFY_TOKEN:
        # Silent-by-default here cost real debugging time: with no token, this
        # returned None instantly and the caller logged "found no price",
        # which reads as "Apify tried and the page had none" rather than
        # "Apify never ran". Every exit below says which one it was.
        logger.info("[apify] no APIFY_TOKEN configured — actor %s not run", actor_id)
        return None

    # run_input can contain nested dicts/lists (startUrls, proxyConfiguration),
    # which aren't hashable as a tuple — a stable JSON string is, instead.
    cache_key = ("apify", actor_id, json.dumps(run_input, sort_keys=True))
    cached = search_cache.get(cache_key)
    if cached is not None:
        return cached

    url = APIFY_RUN_SYNC_BASE.format(actor_id=actor_id)
    started = time.monotonic()
    try:
        with httpx.Client(timeout=float(settings.APIFY_TIMEOUT)) as client:
            resp = client.post(
                url, params={"token": settings.APIFY_TOKEN}, json=run_input
            )
        if resp.status_code >= 300:
            # Body carries Apify's own reason (quota exhausted, actor not
            # permitted, bad input) — worth surfacing, it's the difference
            # between "top up the account" and "fix the request".
            logger.info(
                "[apify] actor %s failed: HTTP %s after %.1fs — %s",
                actor_id, resp.status_code, time.monotonic() - started, resp.text[:300],
            )
            return None
        items = resp.json()
    except httpx.TimeoutException:
        # The usual one: a real browser render regularly needs ~30s and can
        # exceed APIFY_TIMEOUT under load. Distinct from a hard failure —
        # the run itself may well have succeeded on Apify's side.
        logger.info(
            "[apify] actor %s timed out after %.1fs (APIFY_TIMEOUT=%ss)",
            actor_id, time.monotonic() - started, settings.APIFY_TIMEOUT,
        )
        return None
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("[apify] actor %s errored: %s: %s", actor_id, type(exc).__name__, exc)
        return None

    if not isinstance(items, list) or not items:
        logger.info("[apify] actor %s returned an empty dataset", actor_id)
        return None

    logger.info("[apify] actor %s ok in %.1fs", actor_id, time.monotonic() - started)

    search_cache.set(cache_key, items)
    return items


def fetch_rendered_html(url: str) -> str | None:
    """apify/web-scraper: fetches `url` through a real browser + Indian
    residential proxy and returns the rendered page's full HTML, or None on
    any failure. This is Apify's *official* actor, not a third-party one —
    requires one-time permission approval in the Apify console the first
    time it's used (a "full account access" gate), otherwise the API call
    itself fails with a clear, non-crashing error.

    Verified 2026-08-06 against real Flipkart, AJIO, and Nykaa product pages
    blocked by Dealo's own direct fetch — each returned real, full HTML
    (900KB-1.1MB) that search_service._extract_jsonld_price then read a
    correct price from, cross-checked against an independent source each
    time. Deliberately returns raw HTML rather than a parsed price — see
    this file's module docstring for why trusting Apify only as a fetcher,
    not a parser, is the point of this design.
    """
    items = _run_actor(
        "apify~web-scraper",
        {
            "startUrls": [{"url": url}],
            "pageFunction": _RENDER_PAGE_FUNCTION,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
                "apifyProxyCountry": "IN",
            },
        },
    )
    if not items:
        return None
    html = items[0].get("html")
    return html if isinstance(html, str) and html else None
