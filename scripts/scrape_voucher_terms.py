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

Writes data/voucher_terms_raw_{source}.json, keyed "{source}:{slug}" — one file
per source so the three runs can go in parallel without overwriting each other.
Resumable: an entry already present is skipped unless --refresh.
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
BUYHATKE_BRANDS = "https://buyhatke.com/gift-cards/brands"
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


def buyhatke_targets() -> list[dict]:
    """Live catalogue, not the cached master — it is 161 brands larger, and the
    missing ones are not obscure (Amazon Pay, Amazon Prime, BlueStone). The
    brands page server-renders every tile, so no browser is needed here."""
    req = urllib.request.Request(BUYHATKE_BRANDS, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html_text = resp.read().decode("utf-8", "replace")

    out, seen = [], set()
    for href, inner in re.findall(r'<a[^>]+href="(/gift-cards/[^"]+)"[^>]*>(.*?)</a>',
                                  html_text, re.S):
        slug = href[len("/gift-cards/"):]
        if slug in {"brands", "referral", "my-vouchers"} or not slug.endswith("-gift-card"):
            continue
        if slug in seen:
            continue
        seen.add(slug)
        name = re.search(r"<h3[^>]*>(.*?)</h3>", inner, re.S)
        label = re.sub(r"<[^>]+>", " ", name.group(1) if name else inner)
        label = re.sub(r"\s+", " ", html.unescape(label)).strip()
        label = re.sub(r"\s*Gift Card$", "", label).strip()
        out.append({"source": "buyhatke", "slug": slug,
                    "brand_name": label or slug,
                    "url": f"https://buyhatke.com{href}"})
    return out


def maximize_targets() -> list[dict]:
    """The harvested catalog, not the cached master — it is 26 listings larger,
    and the extras are real (a working Yatra, several Amazon variants, Marks &
    Spencer). Rebuild it with harvest_maximize_catalog_v2.py; the site has no
    browse-all page, so it cannot be read in one request the way Gyftr and
    BuyHatke can."""
    cat = json.loads((REPO / "db" / "maximize_catalog_raw.json").read_text())
    out = []
    for pid, rec in cat.items():
        name = html.unescape(rec.get("product_name") or pid)
        out.append({"source": "maximize", "slug": f"{name}-{pid}".lower().replace(" ", "-"),
                    "brand_name": name, "url": rec["url"]})
    return out


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

# The instant card is the only one that lowers what the shopper pays today, and
# it is not always the first card on the page: brands that offer no instant
# discount show the MaxCoins card alone, so reading "the amount after You Pay"
# picks up the full price and reports it as though it were the deal. Anchor on
# the card's own wording instead — "Instant ₹22.5 Off. MaxCoins excluded." —
# and treat its absence as a real zero rather than guessing from a nearby card.
INSTANT_CARD = re.compile(
    r"₹\s*([\d,]+(?:\.\d+)?)\s*\n+\s*([\d.]+)%\s*Off"
    r"(?:\s*\n+\s*Instant\s*₹\s*([\d,]+(?:\.\d+)?)\s*Off)?"
    r"[^\n]*\n*[^\n]*MaxCoins excluded", re.I)


def instant_offer(text: str) -> dict:
    """The instant-discount card's figures, or an explicit zero when the brand
    offers no instant route at all (PhonePe, for one)."""
    m = INSTANT_CARD.search(text)
    if not m:
        return {"pay": None, "discount_pct": 0.0, "instant_offered": False}
    return {"pay": m.group(1), "discount_pct": float(m.group(2)),
            "saving_rupees": m.group(3), "instant_offered": True}


async def scrape_gyftr(page, target: dict) -> dict:
    """Structured fields from the API; full terms from the page's T&C tab.

    Both are kept. The API summary is the more precise wording where it exists,
    but it is not always complete, so the full terms have to travel with it.
    """
    raw: dict = {}
    try:
        data = get_json(GYFTR_DETAIL.format(slug=target["slug"]))["data"]
        brand = data["brand"]
        raw["important_instruction"] = untag(brand.get("important_instruction"))
        raw["checkout_instruction"] = untag(brand.get("checkout_instruction"))
        raw["faqs"] = untag(brand.get("faqs"))
        raw["long_description"] = untag(brand.get("long_description"))
        # ON / OFF / B — the platform's own online-vs-in-store flag, which is
        # cleaner than inferring it from prose.
        raw["redemption_type"] = brand.get("redemption_type")

        # --- the money side ---
        # The rate is per payment method, not per brand: Nykaa pays 5% on UPI
        # and 3% on Credit Card. Recommending the wrong method quietly costs the
        # difference, so every method is stored with its own rate rather than
        # collapsing to a single headline number.
        #
        # processing_charge_apply matters just as much: Gyftr adds a fee on some
        # methods, so the best-looking rate is not always the cheapest route.
        modes = {}
        for m in (data.get("pgmodes") or []) + (data.get("pgdis") or []):
            name = m.get("pg_name")
            if not name:
                continue
            entry = modes.setdefault(name, {"pg_slug": m.get("pg_slug")})
            rate = m.get("pg_discount", m.get("brand_pg_discount"))
            if rate is not None:
                entry["discount_pct"] = rate
            if m.get("processing_charge_apply") is not None:
                entry["processing_charge_apply"] = m["processing_charge_apply"]
            if m.get("pg_offer"):
                entry["pg_offer"] = m["pg_offer"]
        raw["payment_methods"] = modes

        raw["denominations"] = [
            {"name": p.get("product_name"), "value": p.get("mrp"),
             "discount": p.get("discount"), "discount_type": p.get("discount_type"),
             "offer_type": p.get("offer_type"),
             # max_value is the per-voucher ceiling on custom-amount brands
             "max_value": p.get("max_value"), "stock_left": p.get("stock_left")}
            for p in (data.get("products") or [])
        ]
        raw["default_discount_pct"] = brand.get("defaut_pg_dis")
        raw["processing_charge"] = brand.get("processing_charge")
        raw["promocodes"] = data.get("promocodes") or []
    except Exception as exc:
        raw["api_error"] = str(exc)[:200]

    await page.goto(target["url"], wait_until="domcontentloaded", timeout=60000)

    # Three elements carry the "T&C*" label (desktop div, desktop span, mobile
    # button), so a plain text= selector trips Playwright's strict mode and the
    # terms silently never load. Target the span that actually opens the panel.
    #
    # Waiting a fixed number of milliseconds after the click is not enough: under
    # concurrency the panel can take several seconds to populate, and a run at 5
    # workers captured the terms for only 9% of brands while the same code
    # single-threaded got 100%. Wait for the text itself to arrive instead, and
    # re-click if the first one landed before the handler was bound.
    tc = page.locator("span.cursor-pointer:has-text('T&C')").first
    for attempt in range(3):
        try:
            await tc.click(timeout=8000)
            await page.wait_for_function(
                "() => /terms\\s*&\\s*conditions/i.test(document.body.innerText)",
                timeout=8000)
            break
        except Exception:
            if attempt == 2:
                break  # no T&C tab, or it never populated — API fields still stand
            await page.wait_for_timeout(1200)

    body = await page.inner_text("body")
    idx = body.lower().find("terms & conditions")
    raw["full_terms"] = body[idx:idx + 20000].strip() if idx > -1 else ""
    raw["page_text"] = body[:6000]
    return raw


async def scrape_buyhatke(page, target: dict) -> dict:
    """Everything lives in the rendered page: restrictions block, how-to-redeem,
    then the numbered terms."""
    await page.goto(target["url"], wait_until="domcontentloaded", timeout=60000)
    # Client-rendered, so the terms arrive well after domcontentloaded. A fixed
    # 3.2s sleep held up single-threaded but caught only a third of listings at 5
    # workers — wait for the heading itself, and fall back to a sleep for the
    # handful of listings that genuinely carry no terms block.
    try:
        await page.wait_for_function(
            "() => /TERMS AND CONDITIONS/i.test(document.body.innerText)", timeout=15000)
    except Exception:
        await page.wait_for_timeout(3000)
    body = await page.inner_text("body")

    def section(start_pat: str, end_pats: tuple[str, ...]) -> str:
        m = re.search(start_pat, body, re.I)
        if not m:
            return ""
        rest = body[m.start():]
        ends = [e.start() for e in (re.search(p, rest[80:], re.I) for p in end_pats) if e]
        return rest[:min(ends) + 80].strip() if ends else rest[:12000].strip()

    # BuyHatke prices each denomination separately — Myntra runs 3.51% on ₹250
    # but 4.26% on ₹5,000 — so a single headline rate misstates the saving on
    # most basket sizes. Values are written as ₹1.5K / ₹10K on the page.
    def rupees(token: str) -> float | None:
        t = token.replace("₹", "").replace(",", "").strip()
        mult = 1000 if t[-1:].upper() == "K" else 1
        try:
            return float(t[:-1] if mult == 1000 else t) * mult
        except ValueError:
            return None

    # Read the "Select Amount" block itself rather than only amounts that carry
    # their own discount label. Most brands price every denomination the same
    # and print the rate once as a headline, so pairing on "₹X … N% OFF" found
    # nothing and left 320 live brands with no denominations at all — which is
    # how a wrong purchase ceiling gets recommended. The per-denomination rate
    # is still kept where the page does show one, and the label is kept with it
    # because "CASHBACK" is not the same promise as "OFF".
    denoms = []
    block = re.search(r"Select Amount(.*?)(?:Continue|Need help)", body, re.S | re.I)
    if block:
        for m in re.finditer(
                r"₹\s*([\d.,]+\s*[Kk]?)\s*(?:\n\s*([\d.]+)%\s*(OFF|CASHBACK))?",
                block.group(1), re.I):
            value = rupees("₹" + m.group(1))
            if value is None:
                continue
            entry = {"value": value}
            if m.group(2):
                entry["discount_pct"] = float(m.group(2))
                entry["label"] = m.group(3).upper()
            denoms.append(entry)

    return {
        "restrictions": section(r"VOUCHER RESTRICTIONS", (r"REFER & EARN", r"HOW TO REDEEM")),
        "how_to_redeem": section(r"HOW TO REDEEM", (r"TERMS AND CONDITIONS", r"Frequently Asked")),
        "full_terms": section(r"TERMS AND CONDITIONS", (r"Frequently Asked Questions",)),
        "denominations": denoms,
        # Headline range as the site advertises it, kept to cross-check the
        # per-denomination figures above.
        # Some brands advertise CASHBACK rather than OFF (Amazon Pay, BookMyShow);
        # matching only OFF recorded no rate at all for them.
        "headline_discount": (headline.group(1) if (headline := re.search(
            r"([\d.]+%\s*-\s*[\d.]+%\s*(?:OFF|CASHBACK)|[\d.]+%\s*(?:OFF|CASHBACK))",
            body, re.I)) else None),
        "custom_amount": "Enter Custom Amount" in body,
        # The site says so outright. Worth storing rather than inferring it from
        # a missing rate: an unavailable brand still lists its amounts, so it
        # otherwise looks like a live listing that simply has no discount.
        # Requires the amount block too: a delisted brand still returns a page,
        # but it is only nav and footer, which would otherwise pass the
        # "not unavailable" test and read as a live listing.
        "available": bool(denoms) and "currently unavailable" not in body.lower(),
        "page_text": body[:8000],
    }


async def scrape_maximize(page, target: dict) -> dict:
    """Page carries labelled answer boxes ("Multi-Use or Single Use?", "Can the
    cards be clubbed?") that answer several fields outright; the fuller terms sit
    behind a modal. Both are collected."""
    await page.goto(target["url"], wait_until="domcontentloaded", timeout=60000)
    # A fixed wait silently under-runs on a slow load: eleven brands, Zomato and
    # Lenskart among them, came back with only the site chrome captured — no
    # amounts and no rates — which is indistinguishable from a brand that has
    # nothing on sale. Wait for the amount picker itself, and record the miss
    # rather than returning a page that only looks empty.
    try:
        await page.wait_for_function(
            "() => /Select your Shopping Amount/i.test(document.body.innerText)",
            timeout=20000)
    except Exception:
        await page.wait_for_timeout(3800)
    body = await page.inner_text("body")
    if "Select your Shopping Amount" not in body:
        return {"load_incomplete": True, "page_text": body[:2000]}

    boxes: dict[str, str] = {}
    lines = [ln.strip() for ln in body.split("\n") if ln.strip()]
    for i, ln in enumerate(lines[:-1]):
        if ln.endswith("?") or ln in ("Validity",):
            boxes[ln] = lines[i + 1]

    # The URL says only "Amazon" for five different products — a shopping
    # voucher, AmazonPay, Amazon Fresh, and two Prime memberships that discount
    # 15%. Ranking those together would offer a Prime subscription to someone
    # buying groceries. The page states the real name just above the Share
    # button.
    product_name = next((lines[i - 1] for i, ln in enumerate(lines)
                         if ln == "Share" and i), None)

    raw = {"info_boxes": boxes, "page_text": body[:8000], "full_terms": "",
           "how_to_redeem": "", "product_name": product_name}

    # --- the money side ---
    # Scoped to the amount picker. Taking every rupee figure on the page swept
    # in the credit-card promo above it ("Apply and get ₹2000 cashback"), so
    # ₹2000, ₹2000 and ₹1500 were recorded as denominations of every single
    # brand — none of them real.
    picker = re.search(r"Select your Shopping Amount(.*?)(?:Quantity|You Pay)",
                       body, re.S | re.I)
    raw["denominations"] = [
        {"value": float(v.replace(",", ""))}
        for v in re.findall(r"₹\s*([\d,]+(?:\.\d+)?)", picker.group(1))
    ] if picker else []
    # "Max: 4" caps how many this seller will sell in one checkout — distinct
    # from how many the shop will accept at redemption.
    if (m := re.search(r"Max:\s*(\d+)", body)):
        raw["max_quantity_per_order"] = int(m.group(1))

    # Maximize quotes two competing routes on the same card — an instant
    # discount ("₹159.00 20.5% Off") versus paying full and earning MaxCoins
    # ("₹200.00 20.75% Earn"). They are not interchangeable: only the first
    # lowers what you actually pay today, so they are captured separately
    # rather than as one "discount".
    raw["instant_discount"] = instant_offer(body)
    raw["maxcoins_earn"] = [
        {"pay": p, "pct": float(pct)} for p, pct in
        re.findall(r"₹([\d,]+(?:\.\d+)?)\s*\n?\s*([\d.]+)%\s*Earn", body, re.I)
    ]
    # Which methods this brand offers at all. Per-method rates appear only once
    # a method is selected, so the list is recorded here and the rates are read
    # per method below.
    raw["payment_methods_offered"] = [
        m for m in ("UPI", "Debit Card", "Credit Card", "Amazon pay", "CC on UPI",
                    "Pay With Rewards", "Diners Club", "Wallets", "Amex")
        if m.lower() in body.lower()
    ]

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

    # Per-method rates are not printed on load — the quoted price only updates
    # once a method is selected, so each has to be clicked and the resulting
    # "You Pay" figure read back. This is the difference between recommending
    # UPI and recommending a credit card, so it is worth the extra clicks.
    # The page has no input[type=radio] at all — the methods are styled labels
    # wrapping a role=radio, so the old "label containing a radio input" filter
    # matched nothing and every method timed out. Match the label by its exact
    # method text instead, and skip a method with no label rather than spending
    # the timeout on it.
    per_method: dict[str, dict] = {}
    for method in raw.get("payment_methods_offered", []):
        try:
            opt = page.locator(f"label:has(p:text-is('{method}'))").first
            if await opt.count() == 0:
                per_method[method] = {"error": "no selector on page"}
                continue
            await opt.scroll_into_view_if_needed(timeout=4000)
            try:
                await opt.click(timeout=4000)
            except Exception:
                await opt.dispatch_event("click")
            await page.wait_for_timeout(1200)
            after = await page.inner_text("body")
            # Read the "You Pay" figure rather than the "N% Off" badge: on a
            # method that earns no discount the badge is not rendered at all, so
            # keying off it recorded a blank — indistinguishable from a failed
            # read — where the true answer is 0%. The price is always shown.
            per_method[method] = instant_offer(after)
        except Exception as exc:
            per_method[method] = {"error": str(exc)[:100]}
    raw["payment_method_rates"] = per_method
    return raw


SCRAPERS = {"gyftr": scrape_gyftr, "buyhatke": scrape_buyhatke, "maximize": scrape_maximize}


# --------------------------------------------------------------------------
# runners
# --------------------------------------------------------------------------

def load_out(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_out(out: dict, path: Path) -> None:
    """Write via a temp file so an interrupted run cannot leave a half-written
    file behind — this is the only copy of a scrape that takes an hour."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


async def run_headless(source: str, targets: list[dict], out: dict, workers: int, out_path: Path) -> None:
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
                    save_out(out, out_path)
                    print(f"  {source}: {done}/{len(targets)}", flush=True)

        await asyncio.gather(*(one(t) for t in targets))
        await browser.close()
    save_out(out, out_path)


async def run_maximize(targets: list[dict], out: dict, out_path: Path) -> None:
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
                save_out(out, out_path)
                print(f"  maximize: {i}/{len(targets)}", flush=True)
        await ctx.close()
    save_out(out, out_path)


async def main_async(args) -> None:
    sources = [args.source] if args.source else ["gyftr", "buyhatke", "maximize"]

    for source in sources:
        # One file per source. The three runs are long enough that they want to
        # go in parallel, and a shared file means whichever saves last wins and
        # silently discards the others' work. merge_voucher_terms.py joins them.
        out_path = Path(args.out) if args.out else OUT_PATH.with_name(f"voucher_terms_raw_{source}.json")
        out = load_out(out_path)
        targets = {"gyftr": gyftr_targets, "buyhatke": buyhatke_targets,
                   "maximize": maximize_targets}.get(
            source, lambda: master_targets(source))()
        if not args.refresh:
            # Match on the URL as well as the key: switching Maximize to the
            # harvested catalog renamed its slugs, and matching on slug alone
            # would re-collect all 410 listings to gain 26.
            collected = {rec.get("url") for rec in out.values()}
            targets = [t for t in targets
                       if f"{source}:{t['slug']}" not in out and t["url"] not in collected]
        if args.limit:
            targets = targets[: args.limit]
        if not targets:
            print(f"{source}: nothing to do")
            continue

        print(f"\n{source}: {len(targets)} listings", flush=True)
        if source == "maximize":
            print("  (opens a real Chrome window — Cloudflare rejects anything else)", flush=True)
            await run_maximize(targets, out, out_path)
        else:
            await run_headless(source, targets, out, args.workers, out_path)

        ok = sum(1 for v in out.values() if "error" not in v)
        print(f"  {source}: {ok} of {len(out)} listings usable -> {out_path}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=list(SCRAPERS))
    ap.add_argument("--limit", type=int, help="first N per source, for a smoke test")
    ap.add_argument("--workers", type=int, default=4, help="parallel pages (headless sources)")
    ap.add_argument("--refresh", action="store_true", help="re-scrape listings already collected")
    ap.add_argument("--out", help="write here instead of the per-source default")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
