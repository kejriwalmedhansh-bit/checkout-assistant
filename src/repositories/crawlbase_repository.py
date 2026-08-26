"""Crawlbase anti-bot fallback — primary fetcher for merchant hosts that
block Dealo's own direct page fetch (see search_service._fetch_url_page /
_render_fallback). Replaces Apify as the default as of 2026-08-27; Apify
stays wired in as a second attempt for hosts Crawlbase can't get past (see
apify_repository.py).

Same shape and error-handling contract as apify_repository.py /
searchapi_repository.py: never raises, returns None on any failure so a
caller can fall through to the next fetcher or today's weaker (search-index)
price rather than break.

Design: uses Crawlbase's Crawling API with the JavaScript token (real
headless-browser rendering + Crawlbase's own residential proxy pool, not a
custom actor) and returns the rendered page's raw HTML — Dealo still decides
what the price/title actually is via its own already-hand-verified
_extract_jsonld_price / _extract_page_title, exactly like the Apify
integration. Crawlbase's job is only "get me the real page."

Live-tested 2026-08-27 against 13 real product pages across previously
Apify-only hosts: Flipkart, Nykaa, Myntra, Croma, BigBasket, Samsung, Tata
CLiQ, Pepperfry, Lenskart, Ethos, and Apple all returned correct real HTML
in 5-22s (each cross-checked against the seller's/Google's own listed price
or title). AJIO and Titan blocked every attempt (Akamai/Cloudflare
challenge pages) — both fall through to Apify.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import quote

import httpx

from ..cache import search_cache
from ..config import get_settings

logger = logging.getLogger("uvicorn.error")

CRAWLBASE_API_BASE = "https://api.crawlbase.com/"


def fetch_rendered_html(url: str) -> str | None:
    """Fetches `url` through Crawlbase's JavaScript-token Crawling API (real
    browser rendering) and returns the rendered page's full HTML, or None on
    any failure — a real block (Cloudflare/Akamai challenge page), a
    request error, or a timeout.

    Crawlbase surfaces two status codes on every response: the HTTP status
    of its own API call, and an `original_status` header carrying what the
    target site actually returned (200 vs. e.g. 403) — only original_status
    tells you whether the target itself let the request through, so that's
    what's checked here, not just resp.status_code.
    """
    settings = get_settings()
    if not settings.CRAWLBASE_JS_TOKEN:
        logger.info("[crawlbase] no CRAWLBASE_JS_TOKEN configured — not run")
        return None

    cache_key = ("crawlbase", url)
    cached = search_cache.get(cache_key)
    if cached is not None:
        return cached

    request_url = CRAWLBASE_API_BASE + "?token=" + settings.CRAWLBASE_JS_TOKEN + "&url=" + quote(url, safe="")
    started = time.monotonic()
    try:
        with httpx.Client(timeout=float(settings.CRAWLBASE_TIMEOUT)) as client:
            resp = client.get(request_url)
    except httpx.TimeoutException:
        logger.info(
            "[crawlbase] fetch for %s timed out after %.1fs (CRAWLBASE_TIMEOUT=%ss)",
            url, time.monotonic() - started, settings.CRAWLBASE_TIMEOUT,
        )
        return None
    except httpx.HTTPError as exc:
        logger.info("[crawlbase] fetch for %s errored: %s: %s", url, type(exc).__name__, exc)
        return None

    original_status = resp.headers.get("original_status")
    if original_status != "200":
        logger.info(
            "[crawlbase] %s blocked — original_status=%s pc_status=%s after %.1fs",
            url, original_status, resp.headers.get("pc_status"), time.monotonic() - started,
        )
        return None

    html = resp.text
    if not html:
        logger.info("[crawlbase] %s returned an empty body despite original_status=200", url)
        return None

    logger.info("[crawlbase] fetch for %s ok in %.1fs", url, time.monotonic() - started)
    search_cache.set(cache_key, html)
    return html
