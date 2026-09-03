#!/usr/bin/env python3.11
"""Collect raw voucher terms fresh from all three platforms.

This script only COLLECTS. It does no interpretation — every field is stored as
the platform's own words, so the standardisation step afterwards can quote a real
sentence rather than a paraphrase.

Why fresh, rather than reusing db/*_master.json (verified 2026-09-03):
  * BuyHatke's live Myntra terms differ from the cached copy.
  * Gyftr's catalogue has grown to 483 brands; the cache holds 421.
  * Gyftr's short "important instruction" list can contradict the full terms —
    its AJIO summary says "one-time use GV/GC" while the full terms (and the
    user, from real use) say the balance persists as AJIO Cash. Collecting both
    is what lets the next step notice the conflict instead of picking one.

Access, all verified logged-out unless noted:
  gyftr     api.gyftr.com/gyftrapi/api/v1/brand/detail/{slug} for the structured
            fields, plus the page itself for the full terms behind the "T&C*" tab.
  buyhatke  page only; it is client-rendered, so a real browser is required.
  maximize  Cloudflare blocks plain requests. Needs real Chrome with the user's
            ~/.maximize-scrape-profile, which is also what exposes the
            per-payment-mode rates. Runs headed and single-file for that reason.

Usage:
    python3.11 scripts/scrape_voucher_terms.py                  # everything
    python3.11 scripts/scrape_voucher_terms.py --source gyftr   # one platform
    python3.11 scripts/scrape_voucher_terms.py --limit 5        # smoke test

Writes data/voucher_terms_raw.json, keyed "{source}:{slug}". Resumable: an entry
already present is skipped unless --refresh.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "data" / "voucher_terms_raw.json"
CHROME_PROFILE = Path.home() / ".maximize-scrape-profile"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

GYFTR_BRAND_LIST = "https://api.gyftr.com/gyftrapi/api/v1/home/brand/list"
GYFTR_DETAIL = "https://api.gyftr.com/gyftrapi/api/v1/brand/detail/{slug}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def untag(raw: str | None) -> str:
    """HTML fragment -> plain lines, keeping list items on separate lines.

    The platforms store these fields as HTML, and a bare tag-strip runs the
    bullets together into one sentence — which is how a rule ends up misread.
    """
    if not raw:
        return ""
    text = re.sub(r"</(li|p|div|h\d)>", "\n", raw, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.gyftr.com/"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------
# what to scrape
# --------------------------------------------------------------------------

def gyftr_targets() -> list[dict]:
    """Live catalogue, not the cached master — it is 62 brands larger."""
    brands = get_json(GYFTR_BRAND_LIST)["data"]["brands"]
    return [
        {"source": "gyftr", "slug": b["slug"], "brand_name": b["brand_name"],
         "url": f"https://www.gyftr.com/{b['slug']}"}
        for b in brands if b.get("is_published") and b.get("is_visible")
    ]


def master_targets(source: str) -> list[dict]:
    """Maximize/BuyHatke have no public catalogue endpoint; their own master
    files already carry a source_url for every listing."""
    data = json.loads((REPO / "data" / f"{source}_master.json").read_text())
    out, seen = [], set()
    for slug, record in data.items():
        url = next((p.get("source_url") for p in (record.get("products") or []) if p.get("source_url")), None)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"source": source, "slug": slug,
                    "brand_name": record.get("brand_name") or slug, "url": url})
    return out


# --------------------------------------------------------------------------
# per-platform collection
# --------------------------------------------------------------------------

async def scrape_gyftr(page, target: dict) -> dict:
    """Structured fields from the API; full terms from the page's T&C tab.

    Both are kept. The API summary is the more precise wording where it exists,
    but it is not always complete, so the full terms have to travel with it.
    """
    raw: dict = {}
    try:
        brand = get_json(GYFTR_DETAIL.format(slug=target["slug"]))["data"]["brand"]
        raw["important_instruction"] = untag(brand.get("important_instruction"))
        raw["checkout_instruction"] = untag(brand.get("checkout_instruction"))
        raw["faqs"] = untag(brand.get("faqs"))
        raw["long_description"] = untag(brand.get("long_description"))
        # ON / OFF / B — the platform's own online-vs-in-store flag, which is
        # cleaner than inferring it from prose.
        raw["redemption_type"] = brand.get("redemption_type")
    except Exception as exc:
        raw["api_error"] = str(exc)[:200]

    await page.goto(target["url"], wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2200)
    # Three elements carry the "T&C*" label (desktop div, desktop span, mobile
    # button), so a plain text= selector trips Playwright's strict mode and the
    # terms silently never load. Target the span that actually opens the panel.
    for selector in ("span.cursor-pointer:has-text('T&C')", "text=T&C*"):
        try:
            await page.locator(selector).first.click(timeout=6000)
            await page.wait_for_timeout(1800)
            break
        except Exception:
            continue  # last resort: the API fields still stand on their own
    body = await page.inner_text("body")
    idx = body.lower().find("terms & conditions")
    raw["full_terms"] = body[idx:idx + 20000].strip() if idx > -1 else ""
    raw["page_text"] = body[:6000]
    return raw


async def scrape_buyhatke(page, target: dict) -> dict:
    """Everything lives in the rendered page: restrictions block, how-to-redeem,
    then the numbered terms."""
    await page.goto(target["url"], wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(3200)
    body = await page.inner_text("body")

    def section(start_pat: str, end_pats: tuple[str, ...]) -> str:
        m = re.search(start_pat, body, re.I)
        if not m:
            return ""
        rest = body[m.start():]
        ends = [e.start() for e in (re.search(p, rest[80:], re.I) for p in end_pats) if e]
        return rest[:min(ends) + 80].strip() if ends else rest[:12000].strip()

    return {
        "restrictions": section(r"VOUCHER RESTRICTIONS", (r"REFER & EARN", r"HOW TO REDEEM")),
        "how_to_redeem": section(r"HOW TO REDEEM", (r"TERMS AND CONDITIONS", r"Frequently Asked")),
        "full_terms": section(r"TERMS AND CONDITIONS", (r"Frequently Asked Questions",)),
        "page_text": body[:8000],
    }


async def scrape_maximize(page, target: dict) -> dict:
    """Page carries labelled answer boxes ("Multi-Use or Single Use?", "Can the
    cards be clubbed?") that answer several fields outright; the fuller terms sit
    behind a modal. Both are collected."""
    await page.goto(target["url"], wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3800)
    body = await page.inner_text("body")

    boxes: dict[str, str] = {}
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    for i, ln in enumerate(lines[:-1]):
        if ln.endswith("?") or ln in ("Validity",):
            boxes[ln] = lines[i + 1]

    raw = {"info_boxes": boxes, "page_text": body[:8000], "full_terms": "", "how_to_redeem": ""}

    for label, key in (("Terms & Conditions", "full_terms"), ("How To Redeem", "how_to_redeem")):
        try:
            button = page.locator(f"button:has-text('{label}')").first
            # The button sits below the fold on most brand pages; Playwright
            # finds it but the click lands on whatever is covering it, so scroll
            # it into view first and fall back to dispatching the event directly.
            await button.scroll_into_view_if_needed(timeout=5000)
            await page.wait_for_timeout(400)
            try:
                await button.click(timeout=5000)
            except Exception:
                await button.dispatch_event("click")
            await page.wait_for_timeout(1600)
            raw[key] = (await page.locator("[role=dialog]").first.inner_text()).strip()
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(700)
        except Exception as exc:
            raw[f"{key}_error"] = str(exc)[:150]
    return raw


SCRAPERS = {"gyftr": scrape_gyftr, "buyhatke": scrape_buyhatke, "maximize": scrape_maximize}


# --------------------------------------------------------------------------
# runners
# --------------------------------------------------------------------------

def load_out() -> dict:
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_out(out: dict) -> None:
    OUT_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")


async def run_headless(source: str, targets: list[dict], out: dict, workers: int) -> None:
    """Gyftr and BuyHatke: bundled Chromium, logged out, several pages at once."""
    done = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 900})
        sem = asyncio.Semaphore(workers)

        async def one(target: dict) -> None:
            nonlocal done
            async with sem:
                page = await ctx.new_page()
                try:
                    raw = await SCRAPERS[source](page, target)
                    out[f"{source}:{target['slug']}"] = {**target, "scraped_at": now(), "raw": raw}
                except Exception as exc:
                    out[f"{source}:{target['slug']}"] = {**target, "scraped_at": now(),
                                                         "error": str(exc)[:200]}
                    print(f"  ! {target['brand_name']}: {str(exc)[:90]}", flush=True)
                finally:
                    await page.close()
                done += 1
                if done % 25 == 0:
                    save_out(out)
                    print(f"  {source}: {done}/{len(targets)}", flush=True)

        await asyncio.gather(*(one(t) for t in targets))
        await browser.close()
    save_out(out)


async def run_maximize(targets: list[dict], out: dict) -> None:
    """One real-Chrome window, one page at a time — Cloudflare rejects the
    bundled browser, and the profile can only be opened once."""
    if not CHROME_PROFILE.exists():
        print(f"  ! missing Chrome profile at {CHROME_PROFILE}; skipping maximize")
        return
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(CHROME_PROFILE), channel="chrome", headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        for i, target in enumerate(targets, 1):
            try:
                raw = await scrape_maximize(page, target)
                out[f"maximize:{target['slug']}"] = {**target, "scraped_at": now(), "raw": raw}
            except Exception as exc:
                out[f"maximize:{target['slug']}"] = {**target, "scraped_at": now(),
                                                     "error": str(exc)[:200]}
                print(f"  ! {target['brand_name']}: {str(exc)[:90]}", flush=True)
            if i % 20 == 0:
                save_out(out)
                print(f"  maximize: {i}/{len(targets)}", flush=True)
        await ctx.close()
    save_out(out)


async def main_async(args) -> None:
    out = load_out()
    sources = [args.source] if args.source else ["gyftr", "buyhatke", "maximize"]

    for source in sources:
        targets = gyftr_targets() if source == "gyftr" else master_targets(source)
        if not args.refresh:
            targets = [t for t in targets if f"{source}:{t['slug']}" not in out]
        if args.limit:
            targets = targets[: args.limit]
        if not targets:
            print(f"{source}: nothing to do")
            continue

        print(f"\n{source}: {len(targets)} listings", flush=True)
        if source == "maximize":
            print("  (opens a real Chrome window — Cloudflare rejects anything else)", flush=True)
            await run_maximize(targets, out)
        else:
            await run_headless(source, targets, out, args.workers)

    ok = sum(1 for v in out.values() if "error" not in v)
    print(f"\ncollected {ok} of {len(out)} listings -> {OUT_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SCRAPERS))
    ap.add_argument("--limit", type=int, help="first N per source, for a smoke test")
    ap.add_argument("--workers", type=int, default=4, help="parallel pages (headless sources)")
    ap.add_argument("--refresh", action="store_true", help="re-scrape listings already collected")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
