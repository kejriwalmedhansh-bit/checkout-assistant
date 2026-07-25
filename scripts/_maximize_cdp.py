"""Shared CDP-connection helpers for maximize.money scrapers.

Connects Playwright to the real, already-running, already-logged-in Chrome
instance (launched separately with --remote-debugging-port=9222) rather than
launching headless Chromium, which Cloudflare blocks on this site.
"""
from playwright.sync_api import sync_playwright
import json, urllib.request

CDP_URL = "http://localhost:9222"


def _cdp_open_new_tab():
    req = urllib.request.Request(f"{CDP_URL}/json/new?about:blank", method="PUT")
    urllib.request.urlopen(req, timeout=5)


def ensure_cdp_tab_exists():
    """connect_over_cdp errors out ('Browser context management is not
    supported') if zero tabs are open in the target Chrome."""
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/list", timeout=5) as r:
            tabs = json.loads(r.read())
        if not tabs:
            _cdp_open_new_tab()
    except Exception:
        _cdp_open_new_tab()


def get_connected_page():
    """Connect over CDP, ensuring exactly one usable tab exists.
    Returns (playwright_instance, browser, page) — caller is responsible for
    closing all three when done."""
    ensure_cdp_tab_exists()
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return p, browser, page


def close_all(p, browser, page):
    for fn in (page.close, browser.close, p.stop):
        try:
            fn()
        except Exception:
            pass
