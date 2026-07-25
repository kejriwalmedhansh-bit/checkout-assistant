"""Discover the full maximize.money gift-card catalog via the header search box.

There is no browse-all page on the site, so the catalog isn't otherwise enumerable.
The search box does substring matching but requires >=3 typed characters before it
queries the backend. This script probes it with a candidate set of 3-letter
substrings ("trigrams") built from:
  - every trigram found in the macOS system English dictionary (covers real words)
  - every trigram found in GyFTR's 380 brand names (covers non-English brand
    fragments like "nyk", "jio", "kfc" that don't appear in a dictionary)

This is not a mathematical guarantee of 100% completeness (a full 26^3 brute force
would be, at ~3x the runtime) but gives very high coverage in about half the time.

Resumable: progress is checkpointed to CATALOG_RAW every CHECKPOINT_EVERY queries,
and completed trigrams are tracked so a restart skips them.
"""
from playwright.sync_api import sync_playwright
import json, os, re, time, sys, urllib.request

CDP_URL = "http://localhost:9222"
GIFT_CARDS_URL = "https://www.maximize.money/gift-cards"
CATALOG_RAW = "db/maximize_catalog_raw.json"       # {slug/id: {brand_name, id, url}}
TRIGRAMS_DONE = "db/maximize_trigrams_done.json"   # list of trigrams already queried
CHECKPOINT_EVERY = 50
TYPE_DELAY_MS = 90
POST_TYPE_WAIT_MS = 600
PRE_CLEAR_WAIT_MS = 150

HREF_RE = re.compile(r'/gift-cards/([^"\\/]+)/(\d+)')


def build_trigrams():
    dict_trigrams = set()
    try:
        with open("/usr/share/dict/words") as f:
            for line in f:
                w = re.sub(r"[^a-z]", "", line.strip().lower())
                for i in range(len(w) - 2):
                    dict_trigrams.add(w[i:i + 3])
    except FileNotFoundError:
        pass

    brand_trigrams = set()
    try:
        with open("db/gyftr_master.json") as f:
            gyftr = json.load(f)
        names = [v.get("brand_name", k) for k, v in gyftr.items()]
        for n in names:
            w = re.sub(r"[^a-z]", "", n.lower())
            for i in range(len(w) - 2):
                brand_trigrams.add(w[i:i + 3])
    except FileNotFoundError:
        pass

    combined = sorted(dict_trigrams | brand_trigrams)
    return combined


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def extract_hrefs(html):
    return set(HREF_RE.findall(html))


def _cdp_open_new_tab():
    req = urllib.request.Request(f"{CDP_URL}/json/new?about:blank", method="PUT")
    urllib.request.urlopen(req, timeout=5)


def ensure_cdp_tab_exists():
    """connect_over_cdp errors out ('Browser context management is not
    supported') if zero tabs are open in the target Chrome. Open one via the
    CDP HTTP API first if needed."""
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/list", timeout=5) as r:
            tabs = json.loads(r.read())
        if not tabs:
            _cdp_open_new_tab()
    except Exception:
        _cdp_open_new_tab()


def get_connected_page():
    """Connect over CDP, ensuring exactly one usable tab exists."""
    ensure_cdp_tab_exists()
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]
    if ctx.pages:
        page = ctx.pages[0]
    else:
        page = ctx.new_page()
    return p, browser, page


def ensure_on_gift_cards_page(page):
    try:
        if "/gift-cards" not in page.url:
            page.goto(GIFT_CARDS_URL, wait_until="networkidle", timeout=25000)
            page.wait_for_timeout(1200)
    except Exception:
        page.goto(GIFT_CARDS_URL, wait_until="networkidle", timeout=25000)
        page.wait_for_timeout(1200)


def run():
    trigrams = build_trigrams()
    total = len(trigrams)
    done = set(load_json(TRIGRAMS_DONE, []))
    catalog = load_json(CATALOG_RAW, {})
    remaining = [t for t in trigrams if t not in done]

    print(f"Total candidate trigrams: {total}. Already done: {len(done)}. Remaining: {len(remaining)}.")
    print(f"Catalog size so far: {len(catalog)} products.")

    p, browser, page = get_connected_page()
    ensure_on_gift_cards_page(page)
    search_box = page.locator("input").first

    processed_this_run = 0
    start_time = time.time()

    for i, tri in enumerate(remaining, 1):
        for attempt in range(3):
            try:
                search_box.fill("")
                page.wait_for_timeout(PRE_CLEAR_WAIT_MS)
                search_box.type(tri, delay=TYPE_DELAY_MS)
                page.wait_for_timeout(POST_TYPE_WAIT_MS)
                html = page.content()
                for name, pid in extract_hrefs(html):
                    catalog[pid] = {"product_name": name, "id": pid,
                                     "url": f"https://www.maximize.money/gift-cards/{name}/{pid}"}
                break
            except Exception as e:
                print(f"  [{tri}] attempt {attempt+1} failed: {str(e)[:150]}")
                try:
                    page.close()
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                try:
                    p.stop()
                except Exception:
                    pass
                time.sleep(2)
                p, browser, page = get_connected_page()
                ensure_on_gift_cards_page(page)
                search_box = page.locator("input").first

        done.add(tri)
        processed_this_run += 1

        if processed_this_run % CHECKPOINT_EVERY == 0:
            save_json(CATALOG_RAW, catalog)
            save_json(TRIGRAMS_DONE, sorted(done))
            elapsed = time.time() - start_time
            rate = processed_this_run / elapsed
            eta_min = (len(remaining) - processed_this_run) / rate / 60 if rate > 0 else float("inf")
            print(f"[{len(done)}/{total}] catalog={len(catalog)} products | "
                  f"{rate:.2f} q/s | ETA {eta_min:.0f} min", flush=True)

    save_json(CATALOG_RAW, catalog)
    save_json(TRIGRAMS_DONE, sorted(done))

    print(f"\nDone. {len(catalog)} unique products discovered across {len(done)} trigrams.")

    try:
        page.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
    try:
        p.stop()
    except Exception:
        pass


if __name__ == "__main__":
    run()
