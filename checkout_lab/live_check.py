"""Live check: the real Dealo extension, in a real Chrome, on real shop carts.

Loads an extension folder into Playwright's own Chromium, adds a product to
each shop's cart (Shopify's cart endpoint, nothing typed, nothing bought),
opens the cart the way a shopper would and waits to see whether Dealo's panel
appears by itself. Records how long it took and Dealo's own decision log.

A copy of the extension is loaded with site access granted up front, since a
robot can't press "Start saving" on the welcome page. That is the only
difference from what shoppers install.

    uv run --with playwright python -m checkout_lab.live_check ~/Desktop/dealo-extension-0.2.2 \
        chicco.in/cart boat-lifestyle.com/cart levi.in/cart
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ADD_CHEAPEST_OVER_4000 = """async () => {
  try {
    const {products} = await fetch('/products.json?limit=250').then(r => r.json());
    const v = products.flatMap(p => p.variants.map(x => ({t: p.title, id: x.id, price: +x.price, ok: x.available})))
      .filter(x => x.ok && x.price >= 4000).sort((a, b) => a.price - b.price)[0]
      || products.flatMap(p => p.variants.map(x => ({t: p.title, id: x.id, price: +x.price, ok: x.available})))
      .filter(x => x.ok).sort((a, b) => b.price - a.price)[0];
    const res = await fetch('/cart/add.js', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({items: [{id: v.id, quantity: 1}]})});
    return res.ok ? `${v.t} at ₹${v.price}` : null;
  } catch (e) { return null; }
}"""


def test_copy(extension: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="dealo-live-"))
    copy = tmp / "extension"
    shutil.copytree(extension, copy)
    manifest = json.loads((copy / "manifest.json").read_text())
    manifest["host_permissions"] = manifest.pop("optional_host_permissions", ["http://*/*", "https://*/*"])
    (copy / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return copy


def main() -> None:
    extension = Path(sys.argv[1]).expanduser()
    targets = sys.argv[2:]
    copy = test_copy(extension)
    profile = tempfile.mkdtemp(prefix="dealo-profile-")
    with sync_playwright() as p:
        # Chrome for Testing: branded Chrome no longer loads unpacked extensions
        # from the command line. The newest one Playwright has installed is used.
        testing = sorted(Path.home().glob("Library/Caches/ms-playwright/chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"))
        context = p.chromium.launch_persistent_context(
            profile, headless=False, viewport={"width": 1366, "height": 900}, locale="en-IN",
            executable_path=str(testing[-1]) if testing else None,
            args=["--headless=new", f"--disable-extensions-except={copy}", f"--load-extension={copy}"],
        )
        t0 = time.time()
        worker_log: list[str] = []

        def watch(worker):
            worker.on("console", lambda m: worker_log.append(f"{time.time() - t0:6.1f}s {m.text}"))

        for w in context.service_workers:
            watch(w)
        context.on("serviceworker", watch)
        if not context.service_workers:
            context.wait_for_event("serviceworker", timeout=15000)
        sites_file = __import__("os").environ.get("SHOP_SITES_JSON")
        if sites_file:
            # The backend's /shop-websites list, given straight to the extension
            # (for testing before that endpoint is deployed).
            sites = json.loads(Path(sites_file).read_text())
            context.service_workers[0].evaluate(
                "(sites) => chrome.storage.local.set({dealo_shop_sites: {sites, fetchedAt: Date.now()}})", sites)
        for t in [pg for pg in context.pages]:
            if "welcome" in t.url:
                t.close()
        for target in targets:
            host, _, path = target.partition("/")
            base = f"https://www.{host}" if host.count(".") == 1 else f"https://{host}"
            page = context.new_page()
            logs: list[str] = []
            page.on("console", lambda m, logs=logs: logs.append(f"{time.time() - t0:6.1f}s {m.type}: {m.text}") if ("Dealo" in m.text or "chrome-extension" in str(m.location)) else None)
            try:
                page.goto(base, wait_until="domcontentloaded", timeout=45000)
                added = page.evaluate(ADD_CHEAPEST_OVER_4000)
                worker_log.clear()
                started = time.time()
                print(f"\n{target}: opening cart at {started - t0:.1f}s")
                page.goto(f"{base}/{path}", wait_until="commit", timeout=45000)
                seen_at = None
                text = ""
                for _ in range(int(__import__("os").environ.get("WAIT_TICKS", "40"))):
                    page.wait_for_timeout(500)
                    try:
                        if page.locator("#dealo-popup-root .dealo-card").count():
                            seen_at = round(time.time() - started, 1)
                            text = page.locator("#dealo-popup-root").inner_text()[:160].replace("\n", " | ")
                            break
                    except Exception:
                        pass
                print(f"\n{target}: added {added}")
                print(f"  panel appeared: {'after ' + str(seen_at) + 's' if seen_at else 'NO (waited 20s)'}  {text}")
                print(f"  address now: {page.url}")
                for line in logs[-20:]:
                    print(f"  page log: {line[:180]}")
                for line in worker_log[-25:]:
                    print(f"  worker log: {line[:180]}")
            except Exception as e:
                print(f"\n{target}: error {str(e).splitlines()[0][:160]}")
            finally:
                page.close()
        context.close()


if __name__ == "__main__":
    main()
