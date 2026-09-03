"""Rediscover the maximize.money gift-card catalog.

Same method as harvest_maximize_catalog.py — the site has no browse-all page and
its search needs three typed characters, so the catalog is found by probing the
box with every trigram from the system dictionary plus the brand names — but
driven through launch_persistent_context instead of CDP, which stopped
connecting (connectOverCDP times out against Chrome 152 even with the debugging
port plainly answering).

Resumable: the trigrams already tried are checkpointed, so a stop costs at most
CHECKPOINT_EVERY queries.
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

REPO = Path(__file__).resolve().parent.parent
PROFILE = Path.home() / ".maximize-scrape-profile"
GIFT_CARDS_URL = "https://www.maximize.money/gift-cards"
CATALOG_RAW = REPO / "db" / "maximize_catalog_raw.json"
TRIGRAMS_DONE = REPO / "db" / "maximize_trigrams_done.json"
CHECKPOINT_EVERY = 50
HREF_RE = re.compile(r'/gift-cards/([^"\\/]+)/(\d+)')


def load(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    tmp.replace(path)


def build_trigrams() -> list[str]:
    grams = set()
    try:
        for line in open("/usr/share/dict/words"):
            w = re.sub(r"[^a-z]", "", line.strip().lower())
            for i in range(len(w) - 2):
                grams.add(w[i:i + 3])
    except FileNotFoundError:
        pass
    # Brand fragments a dictionary will not contain: nyk, jio, kfc.
    for src in ("gyftr", "buyhatke"):
        path = REPO / "data" / f"voucher_terms_raw_{src}.json"
        if not path.exists():
            continue
        for rec in json.loads(path.read_text()).values():
            n = re.sub(r"[^a-z]", "", (rec.get("brand_name") or "").lower())
            for i in range(len(n) - 2):
                grams.add(n[i:i + 3])
    return sorted(grams)


async def main() -> None:
    trigrams = build_trigrams()
    done = set(load(TRIGRAMS_DONE, []))
    catalog = load(CATALOG_RAW, {})
    todo = [t for t in trigrams if t not in done]
    print(f"{len(trigrams)} trigrams | {len(done)} already done | {len(todo)} to go", flush=True)
    print(f"catalog so far: {len(catalog)} products", flush=True)

    start = time.time()
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(PROFILE), channel="chrome", headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(GIFT_CARDS_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4000)
        box = page.locator("input").first

        for i, tri in enumerate(todo, 1):
            try:
                await box.fill("")
                await page.wait_for_timeout(150)
                await box.type(tri, delay=80)
                await page.wait_for_timeout(600)
                for name, pid in HREF_RE.findall(await page.content()):
                    catalog[pid] = {"product_name": name, "id": pid,
                                    "url": f"https://www.maximize.money/gift-cards/{name}/{pid}"}
                done.add(tri)
            except Exception as exc:
                print(f"  ! {tri}: {str(exc)[:90]}", flush=True)
                try:
                    await page.goto(GIFT_CARDS_URL, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(3000)
                    box = page.locator("input").first
                except Exception:
                    pass
            if i % CHECKPOINT_EVERY == 0:
                save(CATALOG_RAW, catalog)
                save(TRIGRAMS_DONE, sorted(done))
                rate = i / max(time.time() - start, 1)
                print(f"[{len(done)}/{len(trigrams)}] catalog={len(catalog)} | "
                      f"{rate:.1f}/s | eta {(len(todo)-i)/max(rate,0.01)/60:.0f} min", flush=True)
        await ctx.close()

    save(CATALOG_RAW, catalog)
    save(TRIGRAMS_DONE, sorted(done))
    print(f"done — {len(catalog)} unique products", flush=True)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
