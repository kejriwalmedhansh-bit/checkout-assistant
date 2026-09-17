"""The checkout robot: saves real checkout pages so Dealo can be scored on them.

For each shop it opens the website, finds a cheap product, adds it to the cart,
opens the cart, presses checkout, and stops. At each step it saves what the
page looked like: address, title, full page content (including checkout
pop-ups that load in frames) and a small screenshot. Those saved pages are the
library the scoreboard runs Dealo's detection against.

Hard rules, enforced in code rather than hoped for:
  * It never pays, never places an order, never logs in or signs up.
  * It never types into any form, not even fake details, so no shop gets a
    junk order or lead. A checkout that needs details before the pay screen is
    recorded as far as it goes.
  * A login or OTP wall stops the shop and marks it "needs a person" (plan
    step 1: those shops are saved by hand).
  * No shop-specific code. Shopify shops add to cart through Shopify's own
    cart endpoint; everything else goes through the same generic steps.

Run:
    uv run --with playwright python -m checkout_lab.robot giva.co boat-lifestyle.com
    uv run --with playwright python -m checkout_lab.robot --all
Saved to ~/checkout-lab-library/<run date>/<shop>/ unless --out says otherwise.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout, sync_playwright

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path.home() / "checkout-lab-library"

SHOP_BUDGET_S = 150          # a shop that takes longer is stopped and recorded as far as it got
SETTLE_MS = 3500             # time for a page, drawer or pop-up checkout to draw

# Words on a control the robot must never press, whatever else it says.
NEVER_PRESS = re.compile(
    r"\b(pay|payment|place\s*(my\s*)?order|confirm\s*(order|booking|and|&)|complete\s*(purchase|order|payment)|"
    r"submit|continue\s*shopping|sign\s*up|signup|register|log\s*in|login|sign\s*in|otp|verify|subscribe|donate|book\s*now)\b",
    re.I,
)
ADD_TO_CART = re.compile(r"^\s*(add\s*to\s*(cart|bag|basket)|add\s*to\s*shopping\s*bag|buy\s*now|add)\s*$", re.I)
# On a CART page only: many shops label the button that opens checkout "Pay
# now" (boAt) or "Proceed to pay". Nothing can be charged from a cart the robot
# filled without an account, card or saved payment method, so these are allowed
# there. "Place order" and "confirm" stay forbidden everywhere.
CART_ONLY_ALLOWED = re.compile(r"^\s*(pay\s*now|proceed\s*to\s*pay(ment)?|continue\s*to\s*pay(ment)?)\s*$", re.I)
GO_TO_CHECKOUT = re.compile(r"\b(check\s*out|checkout|proceed(\s*to\s*(checkout|buy|shipping|pay(ment)?))?|continue(\s*to\s*(checkout|pay(ment)?))?|buy\s*now|pay\s*now)\b", re.I)
DISMISS = re.compile(r"^\s*(close|×|✕|x|no,?\s*thanks|not\s*now|maybe\s*later|skip|dismiss|reject(\s*all)?|decline|continue\s*shopping|stay\s*here)\s*$", re.I)
SIZE_LIKE = re.compile(r"^\s*(xxs|xs|s|m|l|xl|xxl|3xl|free\s*size|one\s*size|uk\s*\d{1,2}(\.\d)?|us\s*\d{1,2}|\d{1,2}(\.\d)?|\d{2,3}\s*(ml|g|gm|cm))\s*$", re.I)
LOGIN_WALL = re.compile(r"\b(enter\s*(your\s*)?(mobile|phone)\s*(number|no)|login\s*to\s*continue|sign\s*in\s*to\s*continue|log\s*in\s*to\s*(continue|proceed|checkout)|enter\s*otp|verify\s*otp|get\s*otp|send\s*otp)\b", re.I)
RUPEE = re.compile(r"(₹|\brs\.?\s|\binr\s)\s?\d", re.I)
POPUP_CHECKOUTS = ("gokwik", "fastrr", "shiprocket", "shopflo", "razorpay", "simpl", "juspay", "zecpe")


# ---------------------------------------------------------------- saving ----

class Recorder:
    def __init__(self, out_dir: Path, site: str):
        self.dir = out_dir / site
        self.dir.mkdir(parents=True, exist_ok=True)
        self.stages: list[dict] = []

    def save(self, page: Page, stage: str, note: str = "") -> dict:
        """One snapshot: the page and every frame in it, compressed, plus a small screenshot."""
        try:
            page.wait_for_timeout(600)
            frames = []
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    html = frame.content()
                except PlaywrightError:
                    html = ""
                frames.append({"url": frame.url, "html_bytes": len(html)})
                if html and any(k in frame.url for k in POPUP_CHECKOUTS):
                    (self.dir / f"{stage}.frame-{len(frames)}.html.gz").write_bytes(gzip.compress(html.encode()))
            html = page.content()
            (self.dir / f"{stage}.html.gz").write_bytes(gzip.compress(html.encode()))
            page.screenshot(path=str(self.dir / f"{stage}.jpg"), type="jpeg", quality=45, full_page=False)
            text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
            # The shop's own cart total, where the platform publishes it: the
            # true answer the scoreboard compares Dealo's reading against.
            shopify_total = page.evaluate(
                "async () => { if (!window.Shopify && !document.querySelector('script[src*=\"cdn.shopify.com\"]')) return null;"
                " try { const c = await fetch('/cart.js').then(r => r.json()); return c.item_count ? c.total_price / 100 : null; } catch (e) { return null; } }"
            )
            info = {
                "stage": stage,
                "url": page.url,
                "title": page.title(),
                "has_rupee_amount": bool(RUPEE.search(text)),
                "shopify_cart_total": shopify_total,
                "login_wall": looks_like_login_wall(page, text),
                "popup_checkout_frames": [f["url"] for f in frames if any(k in f["url"] for k in POPUP_CHECKOUTS)],
                "frames": len(frames),
                "note": note,
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        except PlaywrightError as e:
            info = {"stage": stage, "url": page.url, "error": str(e)[:300], "note": note}
        self.stages.append(info)
        return info

    def finish(self, site: str, outcome: str, notes: list[str], started: float, platform: str) -> dict:
        result = {
            "site": site,
            "outcome": outcome,
            "platform": platform,
            "stages": [s["stage"] for s in self.stages],
            "notes": notes,
            "seconds": round(time.time() - started, 1),
        }
        (self.dir / "stages.json").write_text(json.dumps(self.stages, indent=1, ensure_ascii=False))
        (self.dir / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
        return result


# ---------------------------------------------------------------- helpers ---

def looks_like_login_wall(page: Page, text: str) -> bool:
    try:
        has_password = page.locator("input[type=password]:visible").count() > 0
    except PlaywrightError:
        has_password = False
    path = urlparse(page.url).path.lower()
    return has_password or bool(re.search(r"/(login|signin|sign-in|account/login)", path)) or bool(LOGIN_WALL.search(text[:20000]))


def settle(page: Page, ms: int = SETTLE_MS) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except PlaywrightTimeout:
        pass
    page.wait_for_timeout(ms)


def clear_popups(page: Page) -> None:
    """Close newsletter and cookie pop-ups: Escape, then a close-looking control.
    Cookie banners get the least-permissive button available."""
    try:
        page.keyboard.press("Escape")
        for el in page.locator("button:visible, [role=button]:visible, a:visible").all()[:400]:
            label = (el.get_attribute("aria-label") or el.inner_text(timeout=300) or "").strip()
            if label and len(label) <= 24 and DISMISS.match(label):
                try:
                    el.click(timeout=1500)
                    page.wait_for_timeout(400)
                except PlaywrightError:
                    pass
    except PlaywrightError:
        pass


def press(page: Page, pattern: re.Pattern, *, allow: re.Pattern | None = None,
          within: str = "button:visible, a:visible, [role=button]:visible, input[type=submit]:visible") -> str | None:
    """Presses the first visible, enabled control whose words match `pattern`
    and never one whose words match NEVER_PRESS, unless the whole label is one
    `allow` names. Returns what it pressed."""
    try:
        controls = page.locator(within).all()[:600]
    except PlaywrightError:
        return None
    for el in controls:
        try:
            label = (el.inner_text(timeout=300) or el.get_attribute("value") or el.get_attribute("aria-label") or "").strip()
        except PlaywrightError:
            continue
        label = re.sub(r"\s+", " ", label)
        if not label or len(label) > 40 or not pattern.search(label):
            continue
        if NEVER_PRESS.search(label) and not (allow and allow.match(label)):
            continue
        try:
            if el.is_disabled():
                continue
            el.scroll_into_view_if_needed(timeout=2000)
            el.click(timeout=4000)
            return label
        except PlaywrightError:
            continue
    return None


def detect_platform(page: Page) -> str:
    try:
        return page.evaluate(
            """() => {
              const h = document.documentElement.outerHTML.slice(0, 400000);
              if (window.Shopify || /cdn\\.shopify\\.com/.test(h)) return 'shopify';
              if (/woocommerce/i.test(h)) return 'woocommerce';
              if (/text\\/x-magento-init|Magento_/i.test(h)) return 'magento';
              if (/demandware|salesforce/i.test(h)) return 'salesforce';
              if (/__NEXT_DATA__|_next\\/static/.test(h)) return 'nextjs';
              return 'other';
            }"""
        )
    except PlaywrightError:
        return "unknown"


# ---------------------------------------------------------------- steps -----

def shopify_add_to_cart(page: Page) -> str | None:
    """Shopify's own cart endpoint: the cheapest available product over ₹200."""
    return page.evaluate(
        """async () => {
          try {
            const res = await fetch('/products.json?limit=250', {credentials: 'same-origin'});
            if (!res.ok) return null;
            const {products} = await res.json();
            const options = products.flatMap(p => p.variants.map(v => ({title: p.title, id: v.id, price: +v.price, ok: v.available})))
              .filter(v => v.ok && v.price >= 200).sort((a, b) => a.price - b.price);
            for (const v of options.slice(0, 5)) {
              const add = await fetch('/cart/add.js', {method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'}, body: JSON.stringify({items: [{id: v.id, quantity: 1}]})});
              if (add.ok) return `${v.title} at ₹${v.price}`;
            }
            return null;
          } catch (e) { return null; }
        }"""
    )


# Links that are never the way to a product.
NOT_SHOPPING = re.compile(r"(login|signin|sign-in|register|account|customer|wishlist|help|support|contact|faq|blog|stories|"
                          r"career|jobs|about|policy|privacy|terms|track|order|store-?locator|stores/|franchise|partner|"
                          r"form/|forbusiness|corporate|gift-?card|press|investor|sitemap|app\.|apps\.|play\.google|javascript:|mailto:|tel:)", re.I)


def is_product_page(page: Page) -> bool:
    """The shop's own label for a product page (structured data or og:type),
    or an add-to-cart button. Addresses are no guide: Wakefit ends in a code,
    DailyObjects uses /dp?, Myntra /buy."""
    try:
        labelled = page.evaluate(
            """() => {
              const ld = [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent).join(' ');
              return /"@type"\s*:\s*"Product"/i.test(ld)
                || !!document.querySelector('meta[property="og:type"][content*="product" i]');
            }"""
        )
    except PlaywrightError:
        labelled = False
    if labelled:
        return True
    try:
        for el in page.locator("button:visible, a:visible, [role=button]:visible").all()[:300]:
            if ADD_TO_CART.match((el.inner_text(timeout=200) or "").strip()):
                return True
    except PlaywrightError:
        pass
    return False


def shop_links(page: Page, site: str) -> list[str]:
    """This shop's own links, most product-looking first: long paths with codes or numbers."""
    try:
        hrefs = page.eval_on_selector_all("a[href]", "els => els.map(a => a.href)")
    except PlaywrightError:
        return []
    own = []
    for h in dict.fromkeys(hrefs):
        u = urlparse(h)
        if not u.netloc.endswith(site) or NOT_SHOPPING.search(h) or u.path in ("", "/"):
            continue
        own.append(h)

    def productish(h: str) -> int:
        path = urlparse(h).path + "?" + urlparse(h).query
        score = len(path.strip("/").split("/"))
        score += 3 if re.search(r"\d{4,}|[A-Z0-9]{8,}|/p/|/dp|/buy|/product|\.html|pid", path) else 0
        return -score

    return sorted(own, key=productish)


def sitemap_products(page: Page) -> list[str]:
    try:
        return page.evaluate(
            """async () => {
              const pick = (xml) => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1].trim());
              try {
                const idx = await fetch('/sitemap.xml').then(r => r.ok ? r.text() : '');
                let locs = pick(idx);
                const productMaps = locs.filter(u => /product/i.test(u) && /\.xml/.test(u));
                if (!productMaps.length) return [];
                return pick(await fetch(productMaps[0]).then(r => r.ok ? r.text() : '')).filter(u => !/\.xml/.test(u)).slice(0, 10);
              } catch (e) { return []; }
            }"""
        ) or []
    except PlaywrightError:
        return []


def choose_a_size(page: Page) -> None:
    try:
        for sel in page.locator("select:visible").all()[:6]:
            options = sel.locator("option").all()
            real = [o for o in options if (o.get_attribute("value") or "").strip() and not o.is_disabled()
                    and not re.search(r"select|choose|size\s*$", (o.inner_text() or ""), re.I)]
            if real and re.search(r"size|variant|option", (sel.get_attribute("name") or "") + (sel.get_attribute("id") or "") + (sel.get_attribute("aria-label") or ""), re.I):
                sel.select_option(value=real[0].get_attribute("value"))
                page.wait_for_timeout(700)
    except PlaywrightError:
        pass
    try:
        for el in page.locator("button:visible, label:visible, li:visible, [role=radio]:visible").all()[:300]:
            text = (el.inner_text(timeout=200) or "").strip()
            if text and SIZE_LIKE.match(text):
                cls = (el.get_attribute("class") or "") + (el.get_attribute("aria-disabled") or "")
                if re.search(r"disabled|unavailable|sold|oos|true", cls, re.I):
                    continue
                el.click(timeout=2000)
                page.wait_for_timeout(700)
                return
    except PlaywrightError:
        pass


def generic_add_to_cart(page: Page, site: str, notes: list[str], started: float) -> str | None:
    """Walks from the home page to a product page (through a category page if
    needed), picks a size if asked, and presses add to cart. At most 8 pages."""
    queue = sitemap_products(page)[:3] + shop_links(page, site)[:6]
    seen: set[str] = set()
    visits = 0
    while queue and visits < 8 and time.time() - started < SHOP_BUDGET_S - 40:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightError:
            continue
        visits += 1
        settle(page, 2500)
        clear_popups(page)
        if not is_product_page(page):
            # A category page: its most product-looking links go to the front.
            queue = [h for h in shop_links(page, site)[:5] if h not in seen] + queue
            continue
        choose_a_size(page)
        pressed = press(page, ADD_TO_CART)
        if pressed:
            settle(page, 3000)
            return f"{pressed} on {urlparse(url).path[:60]}"
    notes.append(f"no product page with an add-to-cart button found ({visits} pages tried)")
    return None


CART_PATHS = ("/cart", "/checkout/cart", "/bag", "/cart/", "/shopping-bag", "/basket", "/viewcart")


def open_cart(page: Page, base: str) -> bool:
    """The header's cart link first, then the addresses shops commonly use."""
    try:
        link = page.locator("a[href*='cart' i]:visible, a[href*='bag' i]:visible, a[href*='basket' i]:visible").first
        if link.count():
            href = link.get_attribute("href")
            if href and not NEVER_PRESS.search(href):
                page.goto(urljoin(page.url, href), wait_until="domcontentloaded", timeout=30000)
                settle(page)
                if cart_has_items(page):
                    return True
    except PlaywrightError:
        pass
    for path in CART_PATHS:
        try:
            response = page.goto(base + path, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightError:
            continue
        if response and response.status >= 400:
            continue
        settle(page)
        if cart_has_items(page):
            return True
    return False


def cart_has_items(page: Page) -> bool:
    try:
        text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 60000) : ''") or ""
    except PlaywrightError:
        return False
    if re.search(r"\b(your\s*(cart|bag|basket)\s*is\s*empty|no\s*items\s*in\s*(your\s*)?(cart|bag))\b", text, re.I):
        return False
    # Prices alone aren't a cart: a product listing has them too (Skechers,
    # after an add that silently didn't happen). A cart also says cart things.
    cart_words = re.search(r"\b(sub\s*total|order\s*summary|price\s*details|cart\s*total|bag\s*total|total\s*mrp|grand\s*total|your\s*(cart|bag|basket)|shopping\s*(cart|bag)|proceed\s*to\s*(checkout|pay)|check\s*out|pay\s*now)\b", text, re.I)
    return bool(RUPEE.search(text)) and bool(cart_words)


# ---------------------------------------------------------------- one shop --

def record_shop(context, site: str, out_dir: Path) -> dict:
    started = time.time()
    notes: list[str] = []
    rec = Recorder(out_dir, site)
    page = context.new_page()
    base = f"https://www.{site}" if site.count(".") == 1 else f"https://{site}"
    platform = "unknown"

    def out_of_time() -> bool:
        return time.time() - started > SHOP_BUDGET_S

    def stop(outcome: str) -> dict:
        try:
            page.close()
        except PlaywrightError:
            pass
        return rec.finish(site, outcome, notes, started, platform)

    try:
        try:
            response = page.goto(base, wait_until="domcontentloaded", timeout=45000)
        except PlaywrightError:
            base = f"https://{site}"
            response = page.goto(base, wait_until="domcontentloaded", timeout=45000)
        settle(page)
        base = f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}"
        platform = detect_platform(page)
        home = rec.save(page, "1-home", f"HTTP {response.status if response else '?'}")
        if response and response.status in (401, 403, 429, 503) and not home.get("has_rupee_amount"):
            notes.append(f"shop refused the robot (HTTP {response.status})")
            return stop("blocked")
        clear_popups(page)

        added = shopify_add_to_cart(page) if platform == "shopify" else None
        if added:
            notes.append(f"added through Shopify's cart: {added}")
        else:
            added = generic_add_to_cart(page, site, notes, started)
            if added:
                notes.append(f"added on the product page: {added}")
                rec.save(page, "2-after-add", "state right after pressing add to cart (drawers often open here)")
        if not added:
            return stop("no_product_added")
        if out_of_time():
            notes.append("ran out of time after adding")
            return stop("added_only")

        if platform == "shopify" and added:
            # Shopify says itself whether the item is in: the cart page is
            # /cart, and cart.js holds the count. No guessing from page words
            # (GIVA's cart didn't use any the check knew).
            page.goto(base + "/cart", wait_until="domcontentloaded", timeout=30000)
            settle(page)
            in_cart = page.evaluate("async () => { try { return (await fetch('/cart.js').then(r => r.json())).item_count } catch (e) { return 0 } }")
            if not in_cart:
                notes.append("Shopify's cart is empty after adding")
                return stop("added_only")
        elif not open_cart(page, base):
            notes.append("couldn't find a cart page showing the item")
            return stop("added_only")
        cart = rec.save(page, "3-cart")
        if cart.get("login_wall"):
            # A phone-OTP pop-up over a cart that still shows its prices
            # (Birkenstock, Jockey, Matrix) is not a wall: the cart is saved and
            # scoreable, so carry on to checkout.
            notes.append("cart shows a login or phone-OTP pop-up")
            if not cart.get("has_rupee_amount"):
                return stop("needs_person")
        if out_of_time():
            return stop("reached_cart")

        before = page.url
        pressed = press(page, GO_TO_CHECKOUT, allow=CART_ONLY_ALLOWED)
        if not pressed and platform == "shopify":
            # The cart's button is one the robot won't press ("Place order" on
            # Levi's) or is locked behind a terms tick (Blue Tokai). Shopify's
            # own checkout address gets there without pressing anything. The
            # button comes first because it is what shoppers see: on boAt it
            # opens GoKwik's pop-up checkout, not Shopify's page.
            page.goto(base + "/checkout", wait_until="domcontentloaded", timeout=30000)
            settle(page, 5000)
            notes.append("opened Shopify's checkout address (cart button not pressable)")
            checkout = rec.save(page, "4-checkout")
            if checkout.get("login_wall"):
                notes.append("checkout asks for a login or phone OTP before the pay screen")
                if not checkout.get("has_rupee_amount"):
                    return stop("needs_person")
            return stop("reached_checkout")
        if not pressed:
            notes.append("no checkout button found on the cart")
            return stop("reached_cart")
        notes.append(f"pressed '{pressed}' on the cart")
        settle(page, 5000)
        checkout = rec.save(page, "4-checkout", "same address, checkout opened over the page" if page.url == before else "")
        if checkout.get("popup_checkout_frames"):
            notes.append("checkout opened as a pop-up: " + ", ".join(sorted({urlparse(u).netloc for u in checkout["popup_checkout_frames"]})))
        if checkout.get("login_wall"):
            notes.append("checkout asks for a login or phone OTP before the pay screen")
            if not checkout.get("has_rupee_amount"):
                return stop("needs_person")
        return stop("reached_checkout")
    except PlaywrightError as e:
        notes.append("robot error: " + str(e).splitlines()[0][:200])
        try:
            rec.save(page, "9-at-error")
        except Exception:
            pass
        return stop("error")


# ---------------------------------------------------------------- run -------

def shops_in_scope() -> list[str]:
    """Every website where an active voucher brand can be spent online (plan scope)."""
    two_part = {"co", "com", "net", "org", "gov", "edu", "ac"}

    def site(h: str) -> str:
        parts = h.lower().replace("www.", "").split("/")[0].split(".")
        return ".".join(parts[-3:]) if len(parts) >= 3 and parts[-2] in two_part else ".".join(parts[-2:])

    rows = csv.DictReader(open(REPO / "audits" / "brand_websites_all.csv"))
    sites = sorted({site(r["website"]) for r in rows if r["where_voucher_works"] == "website" and r["listing_active"] == "yes" and r["website"]})
    left_out = {"holidaytribe.com", "luxegiftcard.com", "luluhypermarket.in"}  # see audits/brand_websites_all.csv notes
    return [s for s in sites if s not in left_out]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("shops", nargs="*", help="shop websites, e.g. giva.co boat-lifestyle.com")
    ap.add_argument("--all", action="store_true", help="every website in scope")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--skip-done", action="store_true", help="skip shops already saved in this run folder")
    args = ap.parse_args()

    shops = shops_in_scope() if args.all else args.shops
    if not shops:
        ap.error("name some shops, or pass --all")
    run_dir = args.out / date.today().isoformat()
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "summary.csv"
    new_file = not summary_path.exists()
    with sync_playwright() as p, open(summary_path, "a", newline="") as summary:
        writer = csv.writer(summary)
        if new_file:
            writer.writerow(["site", "outcome", "platform", "stages", "seconds", "notes"])
        browser = p.chromium.launch(channel="chrome", headless=True, args=["--disable-blink-features=AutomationControlled"])
        for i, site in enumerate(shops, 1):
            if args.skip_done and (run_dir / site / "result.json").exists():
                continue
            context = browser.new_context(
                viewport={"width": 1366, "height": 900},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
            )
            try:
                result = record_shop(context, site, run_dir)
            finally:
                context.close()
            writer.writerow([site, result["outcome"], result["platform"], " > ".join(result["stages"]), result["seconds"], " | ".join(result["notes"])])
            summary.flush()
            print(f"[{i}/{len(shops)}] {site}: {result['outcome']} ({result['seconds']}s) {' | '.join(result['notes'])[:160]}", flush=True)
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
