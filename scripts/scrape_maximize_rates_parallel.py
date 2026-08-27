"""Fast, parallel rates-only refresh for maximize.money.

Unlike scrape_maximize.py (one tab, full detail incl. How-To-Redeem/T&C
dialogs), this opens several tabs at once in the SAME logged-in browser
(shares cookies via the same CDP-connected context) and only reads what
actually changes day-to-day: per-payment-mode discount/earn rates and
denominations. Terms & Conditions / How-To-Redeem are intentionally skipped
and merged back in from the last full scrape afterward (those don't change).

Uses Playwright's ASYNC API (not threads) — Playwright's sync wrapper is not
safe to drive from multiple Python threads sharing one browser connection;
asyncio.gather over one event loop is the supported way to run several pages
concurrently.

Usage:  /usr/local/bin/python3.11 scripts/scrape_maximize_rates_parallel.py [N_WORKERS]
"""
import sys, json, os, re, time, asyncio, random
from datetime import date
from playwright.async_api import async_playwright

CDP_URL = "http://localhost:9222"
CATALOG_FILE = "db/maximize_catalog.json"
PROGRESS_FILE = "db/maximize_rates_progress.json"
FAILED_LOG = "db/maximize_rates_failures.json"
CHECKPOINT_EVERY = 10
MAX_ATTEMPTS = 2
PAYMENT_MODES = ["UPI", "Debit Card", "Credit Card", "CC on UPI", "Diners Club", "Amex"]
N_WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 6

progress = {}
failed = []
save_lock = asyncio.Lock()


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def parse_denominations(text):
    lines = [l.strip() for l in text.split("\n")]
    try:
        start = lines.index("Select your Shopping Amount")
    except ValueError:
        return [], False
    denoms, custom = [], False
    for l in lines[start + 1:]:
        if l == "Quantity":
            break
        if l == "Custom":
            custom = True
        elif re.match(r"^₹[\d,]+$", l):
            denoms.append(int(l.replace("₹", "").replace(",", "")))
    return denoms, custom


def parse_current_rate(text):
    off_m = re.search(r"(\d+(?:\.\d+)?)%\s*Off", text)
    earn_m = re.search(r"(\d+(?:\.\d+)?)%\s*Earn", text)
    return {
        "instant_discount_pct": float(off_m.group(1)) if off_m else None,
        "maxcoins_earn_pct": float(earn_m.group(1)) if earn_m else None,
    }


async def dismiss_tour_if_present(page):
    """Fresh tabs can show the 'Search anything 1 of 2' onboarding tour,
    which sits on top of the page and swallows every click underneath it
    until dismissed — this is what made the first (single-tab) run of this
    pipeline silently return empty rates for every product."""
    try:
        skip = page.get_by_text("Skip", exact=True).first
        if await skip.is_visible(timeout=1500):
            await skip.click(timeout=1500)
            await page.wait_for_timeout(400)
    except Exception:
        pass


class LoggedOutError(Exception):
    """Raised when the site session has expired mid-run — never silently
    collect empty-rate data past this point (CLAUDE.md rule 1)."""


async def scrape_rates(page, url):
    result = {"url": url}
    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
    await page.wait_for_timeout(2500)
    await dismiss_tour_if_present(page)

    text = await page.inner_text("body")
    result["logged_in"] = "Sign In" not in text
    if not result["logged_in"]:
        raise LoggedOutError(f"Session expired (logged out) while scraping {url}")

    # A real, logged-in page occasionally still hasn't finished rendering
    # its payment-mode widget at this point (confirmed by hand: re-visiting
    # a "no payment mode found" page moments later showed it fine) — one
    # extra wait-and-recheck before accepting "this page has no rates".
    if "Select Your Payment Mode" not in text:
        await page.wait_for_timeout(2000)
        text = await page.inner_text("body")

    denoms, custom = parse_denominations(text)
    result["denominations"] = denoms
    result["custom_amount"] = custom

    discounts = {}
    if "Select Your Payment Mode" in text:
        # Confirmed by hand: the FIRST mode clicked (always UPI, since it's
        # first in PAYMENT_MODES) fails disproportionately often — the
        # selector's text renders slightly before its click target is
        # actually interactive, right after page load. A settle wait plus a
        # one-shot retry per mode (not just the first) fixes it without
        # slowing down the modes that were already fine.
        await page.wait_for_timeout(500)
        for mode in PAYMENT_MODES:
            rate = None
            for mode_attempt in range(2):
                try:
                    await page.get_by_text(mode, exact=True).first.click(timeout=4000)
                    await page.wait_for_timeout(700)
                    mode_text = await page.inner_text("body")
                    rate = parse_current_rate(mode_text)
                    if rate.get("instant_discount_pct") is not None:
                        break
                except Exception:
                    pass
                await page.wait_for_timeout(500)
            discounts[mode] = rate
    result["discounts"] = discounts

    if discounts:
        best_mode, best_pct = None, -1
        for mode, d in discounts.items():
            if d and d.get("instant_discount_pct") is not None and d["instant_discount_pct"] > best_pct:
                best_pct = d["instant_discount_pct"]
                best_mode = mode
        result["best_payment_method"] = best_mode
        result["best_discount_pct"] = best_pct if best_mode else None

    return result


async def scrape_with_retry(page, url):
    last_exc = None
    logged_out_strikes = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # Individual Playwright calls inside scrape_rates() have their
            # own timeouts, but a dead/frozen CDP connection can make those
            # not fire — confirmed by hand: the scraper hung on one product
            # for 20+ minutes with the process still alive. This outer
            # watchdog guarantees forward progress either way.
            res = await asyncio.wait_for(scrape_rates(page, url), timeout=45)
            res["attempts"] = attempt
            return res
        except asyncio.TimeoutError as e:
            last_exc = Exception("watchdog timeout after 45s")
            await asyncio.sleep(1)
            continue
        except LoggedOutError as e:
            # A single logged-out read can be a transient render hiccup
            # (confirmed by hand: a page reported logged-out, then read
            # logged-in a few seconds later with no re-login). Only treat
            # it as a real session loss if it repeats on retry.
            logged_out_strikes += 1
            last_exc = e
            if logged_out_strikes >= 2:
                raise
            await asyncio.sleep(2)
        except Exception as e:
            last_exc = e
            await asyncio.sleep(1)
    return {"url": url, "error": str(last_exc)[:300], "attempts": MAX_ATTEMPTS}


async def worker(worker_id, page, ids, catalog, total, stop_event):
    for pid in ids:
        if stop_event.is_set():
            return
        entry = catalog[pid]
        url = entry["url"]
        try:
            res = await scrape_with_retry(page, url)
        except LoggedOutError as e:
            print(f"\n!!! LOGGED OUT (worker {worker_id}): {e}\n"
                  f"    Stopping all workers — session needs to be re-established "
                  f"before continuing. Progress so far is saved.", flush=True)
            stop_event.set()
            return
        res["product_name"] = entry.get("product_name")
        res["maximize_product_id"] = pid
        res["last_scraped"] = date.today().isoformat()

        async with save_lock:
            progress[pid] = res
            if res.get("error") or not res.get("discounts"):
                failed.append(pid)
            done_so_far = len(progress)
            if done_so_far % CHECKPOINT_EVERY == 0:
                save_json(PROGRESS_FILE, progress)
                save_json(FAILED_LOG, failed)
                print(f"[{done_so_far}/{total}] checkpoint saved", flush=True)

        # Jittered pacing between pages — a tight, mechanically regular
        # request rhythm reads as automation to the site's abuse detection
        # (this is what was triggering the repeated mid-run logouts).
        await asyncio.sleep(random.uniform(4.0, 9.0))


async def run():
    with open(CATALOG_FILE) as f:
        catalog = json.load(f)
    all_ids = list(catalog.keys())

    global progress, failed
    progress = load_json(PROGRESS_FILE, {})

    # Entries saved with an error (dead page/browser handle, watchdog
    # timeout, etc.) or logged_in != True are worthless and must be
    # retried, not treated as done — otherwise a run cut off mid-failure
    # permanently poisons the last few products it touched.
    invalid_pids = [pid for pid, res in progress.items()
                     if res.get("error") or res.get("logged_in") is not True
                     or not res.get("discounts")]
    for pid in invalid_pids:
        del progress[pid]
    if invalid_pids:
        print(f"Dropped {len(invalid_pids)} invalid entries from progress to retry: {invalid_pids}")

    remaining = [pid for pid in all_ids if pid not in progress]
    total = len(all_ids)
    print(f"Total products: {total}. Already done: {len(progress)}. Remaining: {len(remaining)}. Workers: {N_WORKERS}.")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0]

        opener = None
        for pg in ctx.pages:
            if "maximize.money" in pg.url and "gift-cards" in pg.url:
                opener = pg
                break
        if opener is None:
            opener = await ctx.new_page()
            await opener.goto("https://www.maximize.money/gift-cards", wait_until="domcontentloaded", timeout=25000)

        await opener.wait_for_timeout(1200)
        opener_text = await opener.inner_text("body")
        if "Sign In" in opener_text:
            print("!!! Not logged in on the source tab — log into maximize.money in "
                  "that Chrome window and re-run. Nothing scraped.", flush=True)
            return

        # New tabs opened via window.open() FROM an already-logged-in page
        # inherit its sessionStorage (per spec: a script-opened top-level
        # browsing context copies its opener's session storage). A tab
        # created via a fresh browser context (ctx.new_page()) does NOT get
        # this copy and comes up logged out — confirmed by hand this
        # session, and the reason the first parallel attempt silently
        # scraped nothing.
        pages = [opener]
        for _ in range(N_WORKERS - 1):
            async with ctx.expect_page() as new_page_info:
                await opener.evaluate("() => window.open(window.location.href, '_blank')")
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
            pages.append(new_page)

        buckets = [[] for _ in range(N_WORKERS)]
        for i, pid in enumerate(remaining):
            buckets[i % N_WORKERS].append(pid)

        stop_event = asyncio.Event()
        start_time = time.time()
        await asyncio.gather(*[
            worker(i, pages[i], buckets[i], catalog, total, stop_event) for i in range(N_WORKERS)
        ])

        save_json(PROGRESS_FILE, progress)
        save_json(FAILED_LOG, failed)

        elapsed = time.time() - start_time
        status = "STOPPED EARLY (session expired)" if stop_event.is_set() else "Done"
        print(f"\n{status}. {len(progress)}/{total} products scraped. {len(failed)} failed/incomplete. Elapsed: {elapsed/60:.1f} min.")
        if stop_event.is_set():
            print("Log back into maximize.money in the Chrome window and re-run this "
                  "script — it will resume from where it left off (progress is checkpointed).")

        # Never close pages[0] — it's the user's own pre-existing logged-in
        # tab (the opener), not one we created. Closing it was the actual
        # cause of "the tab disappeared" happening after every run.
        for pg in pages[1:]:
            try:
                await pg.close()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run())
