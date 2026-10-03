"""Flipkart's own search, for products Google Shopping doesn't list there.

Google Shopping often has no Flipkart entry for smaller brands. Live
2026-10-03: FINGERS 2Mic-GrooveBox-K30 was ₹5,849 on Flipkart, but Google's
23-store list for it had no Flipkart row, so Dealo recommended Amazon's 1.25%
voucher over Flipkart's 2.13%.

Flipkart blocks Dealo's server, so the results page is read through
Crawlbase (crawlbase_repository, which also caches by URL). Same contract as
the other repositories: never raises, returns [] on any failure.

Rows come back in search_service._offer_rows shape, so they go through the
exact same checks as every Google store row (exact-product ID card, stock,
believable-price floor). This module only reads the page; it decides nothing.
"""
from __future__ import annotations

import html
import logging
import re
from urllib.parse import quote_plus

from . import crawlbase_repository

logger = logging.getLogger("uvicorn.error")

_SEARCH_URL = "https://www.flipkart.com/search?q="
_RESULTS_READ = 10   # cards from the top; further down is unrelated filler

# Each result card opens with <div data-id="<Flipkart product id>">. The
# rest is read by what it is (a /p/itm product link, a title attribute, a ₹
# amount), not by Flipkart's generated class names, which change often.
_CARD_SPLIT = '<div data-id="'
_LINK_RE = re.compile(r'href="(/[^"]*/p/itm[^"]*)"')
_TITLE_RE = re.compile(r'<a[^>]+title="([^"]+)"[^>]*href="/[^"]*/p/')
_ALT_RE = re.compile(r'<img[^>]+alt="([^"]+)"')
# Fashion cards put the brand in its own line above the title ("NIKE" /
# "WMNS AIR FORCE 1 '07 Running Shoes For Women").
_BRAND_RE = re.compile(r'<div class="[^"]+">([^<]{2,40})</div><a[^>]+title=')
# The selling price is the first ₹ amount on a card; the struck-out MRP
# follows it.
_PRICE_RE = re.compile(r'>₹([0-9,]+)<')
_OOS_RE = re.compile(r"sold out|currently unavailable|coming soon|out of stock", re.IGNORECASE)


def search(query: str) -> list[dict]:
    """The top Flipkart results for `query` as store rows, or [] on failure."""
    markup = crawlbase_repository.fetch_rendered_html(_SEARCH_URL + quote_plus(query))
    if not markup:
        logger.info("[flipkart] search page unreadable for %r", query)
        return []
    rows = []
    for card in markup.split(_CARD_SPLIT)[1:]:
        link = _LINK_RE.search(card)
        price = _PRICE_RE.search(card)
        title = _TITLE_RE.search(card) or _ALT_RE.search(card)
        if not (link and price and title):
            continue
        name = html.unescape(title.group(1)).strip()
        brand = _BRAND_RE.search(card)
        if brand and not name.lower().startswith(brand.group(1).strip().lower()):
            name = f"{html.unescape(brand.group(1)).strip()} {name}"
        # Drop the search-tracking parameters; pid/lid name the listing.
        path = html.unescape(link.group(1))
        keep = [p for p in path.split("?", 1)[-1].split("&") if p.startswith(("pid=", "lid="))] if "?" in path else []
        url = "https://www.flipkart.com" + path.split("?", 1)[0] + ("?" + "&".join(keep) if keep else "")
        text = re.sub(r"<[^>]+>", " ", card)
        rows.append({
            "merchant": "Flipkart",
            "title": name,
            "price": float(price.group(1).replace(",", "")),
            "link": url,
            "details": ["Out of stock"] if _OOS_RE.search(text) else [],
            "_source_token": "flipkart-search",
        })
        if len(rows) >= _RESULTS_READ:
            break
    logger.info("[flipkart] %d result(s) for %r", len(rows), query)
    return rows
