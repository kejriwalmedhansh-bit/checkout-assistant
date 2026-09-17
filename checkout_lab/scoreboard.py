"""The scoreboard: runs Dealo's real detection code on every saved checkout page.

For each page the robot saved, it opens the saved copy offline (the shop's own
scripts removed, nothing fetched from the internet, at the page's original
address), loads the extension's config.js, popup.js and content.js exactly as
Chrome would, and asks Dealo what it decided:

  * loads:     would the extension's background worker load Dealo here?
               (background.js looksLikeCheckout on the address and title)
  * speaks:    does content.js call this page a checkout? (isCheckoutPage)
  * total:     which order total Dealo reads (labelled total, then fallbacks),
               compared with Shopify's own cart total where the robot saved it
  * gift box:  does "show me where" find a gift-card or voucher box?

The extension code is scored as it is on disk, so any branch can be scored:
    uv run --with playwright python -m checkout_lab.scoreboard ~/checkout-lab-library/2026-09-17
    uv run --with playwright python -m checkout_lab.scoreboard <run> --extension path/to/extension

Nothing in the extension changes for this. A test hook is added to the copy of
content.js loaded here, never to the shipped file.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]

HOOK = """
  if (self.__dealoTestHook) {
    self.__dealoTestHook({
      urlLooksLikeCheckout, isCheckoutPage, hasCommerceSignal, labelledTotal, extractPrice, findGiftCardField, readPrice,
      urlMightBeCheckout: typeof urlMightBeCheckout === "function" ? urlMightBeCheckout : null,
      looksLikePaymentStep: typeof looksLikePaymentStep === "function" ? looksLikePaymentStep : null,
    });
    return;
  }
  check();
})();"""

CHROME_STUB = """
self.chrome = { runtime: { id: "scoreboard", sendMessage: (m, cb) => cb && cb(null), onMessage: { addListener() {} }, lastError: null },
                storage: { local: { get: (k, cb) => cb && cb({}), set() {} } } };
"""

def without_shop_scripts(html: str) -> str:
    """The saved page, minus the shop's own scripts (structured data stays:
    Dealo reads it)."""
    return re.sub(
        r"<script\b(?![^>]*application/ld\+json)[^>]*>.*?</script>",
        "",
        html,
        flags=re.S | re.I,
    )


def background_gate(extension: Path) -> str:
    src = (extension / "src" / "background.js").read_text()
    match = re.search(r"function looksLikeCheckout\(url, title\) \{.*?\n\}\n", src, re.S)
    if not match:
        raise SystemExit("background.js has no looksLikeCheckout(url, title)")
    return match.group(0)


def score_run(run_dir: Path, extension: Path) -> list[dict]:
    config_js = (extension / "src" / "config.js").read_text()
    popup_js = (extension / "src" / "popup.js").read_text()
    content_js = (extension / "src" / "content.js").read_text()
    if "  check();\n})();" not in content_js:
        raise SystemExit("content.js no longer ends with check(); })(); - update the scoreboard hook")
    content_js = content_js.replace("  check();\n})();", HOOK)
    gate_js = background_gate(extension)

    rows: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for shop_dir in sorted(d for d in run_dir.iterdir() if d.is_dir()):
            stages_file = shop_dir / "stages.json"
            if not stages_file.exists():
                continue
            result = json.loads((shop_dir / "result.json").read_text())
            for stage in json.loads(stages_file.read_text()):
                name = stage.get("stage", "")
                if not re.match(r"[234]-", name):
                    continue  # home pages aren't scored
                saved = shop_dir / f"{name}.html.gz"
                if not saved.exists():
                    continue
                html = without_shop_scripts(gzip.decompress(saved.read_bytes()).decode("utf-8", "ignore"))
                url = stage["url"]
                context = browser.new_context(viewport={"width": 1366, "height": 900})
                page = context.new_page()

                shopify_total = stage.get("shopify_cart_total")

                def serve(route, request, html=html, url=url, shopify_total=shopify_total):
                    # The address without its #part is what the browser requests.
                    if request.url.split("#")[0] == url.split("#")[0] and request.resource_type == "document":
                        route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
                    elif request.url.split("?")[0].endswith("/cart.js") and shopify_total:
                        # What Shopify answered when the robot saved the page, so
                        # Dealo's platform read of the total works offline too.
                        route.fulfill(status=200, content_type="application/json",
                                      body=json.dumps({"item_count": 1, "total_price": round(shopify_total * 100)}))
                    else:
                        route.abort()

                page.route("**/*", serve)
                row = {"shop": shop_dir.name, "stage": name, "url": url, "robot_outcome": result.get("outcome"),
                       "platform": result.get("platform"), "shopify_cart_total": stage.get("shopify_cart_total")}
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    loads = page.evaluate(
                        "([gate, config, url, title]) => { const self = {}; eval(config); "
                        "return new Function('self', gate + '; return looksLikeCheckout;')(self)(url, title); }",
                        [gate_js, config_js, url, stage.get("title", "")],
                    )
                    page.add_script_tag(content=CHROME_STUB + config_js)
                    page.add_script_tag(content=popup_js)
                    # Arm the hook, then load content.js, which calls it.
                    page.evaluate("""() => { self.__dealoAnswer = new Promise((resolve) => {
                        self.__dealoTestHook = (api) => { self.__dealoApi = api; resolve(true); }; }); }""")
                    page.add_script_tag(content=content_js)
                    page.evaluate("() => self.__dealoAnswer")
                    answer = page.evaluate("""async () => {
                        const api = self.__dealoApi;
                        const safe = (f) => { try { return f(); } catch (e) { return 'error: ' + e.message; } };
                        const gift = safe(() => api.findGiftCardField());
                        return {
                          urlLooksLikeCheckout: safe(() => api.urlLooksLikeCheckout()),
                          urlMightBeCheckout: api.urlMightBeCheckout ? safe(() => api.urlMightBeCheckout()) : null,
                          hasCommerceSignal: safe(() => api.hasCommerceSignal()),
                          looksLikePaymentStep: api.looksLikePaymentStep ? safe(() => api.looksLikePaymentStep()) : null,
                          isCheckoutPage: safe(() => api.isCheckoutPage()),
                          labelledTotal: safe(() => api.labelledTotal()),
                          extractPrice: safe(() => api.extractPrice()),
                          readPrice: await api.readPrice().catch((e) => 'error: ' + e.message),
                          giftBox: gift && typeof gift === 'object' ? (gift.label || 'found') : (gift || null),
                        };
                    }""")
                    row.update({"loads": loads, **answer})
                except Exception as e:  # a page that won't load offline is recorded, not fatal
                    row["error"] = str(e).splitlines()[0][:200]
                finally:
                    context.close()
                rows.append(row)
                print(f"{row['shop']:28s} {name:14s} loads={row.get('loads')} speaks={row.get('isCheckoutPage')} "
                      f"total={row.get('readPrice')} (shop says {row.get('shopify_cart_total')}) gift={row.get('giftBox')} {row.get('error', '')}", flush=True)
        browser.close()
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="a robot run folder, e.g. ~/checkout-lab-library/2026-09-17")
    ap.add_argument("--extension", type=Path, default=REPO / "extension")
    args = ap.parse_args()
    rows = score_run(args.run.expanduser(), args.extension)
    out = args.run.expanduser() / "scoreboard.csv"
    fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ("shop", "stage"), k))
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} pages scored -> {out}")


if __name__ == "__main__":
    sys.exit(main())
