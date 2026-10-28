"""Record and replay a whole search + comparison offline.

Everything the routes stage asks the outside world for goes through four
doors: SearchApi (`searchapi_repository._get`), Flipkart's own search page
(`flipkart_repository.search`), the pasted link's page
(`search_service._fetch_url_page`) and rendered store pages
(`context_dev_repository` / `crawlbase_repository.fetch_rendered_html`, used
only for the live price re-check and bank-card offers). Recording the first
three and switching the fourth off makes a comparison repeatable for free.

Capture (SearchApi credits: ~25-30 per case):
    .venv/bin/python tests/routes_replay.py capture            # every case below
    .venv/bin/python tests/routes_replay.py capture "<query or link>"

Replay is what tests/test_routes_replay.py does.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import threading
from contextlib import contextmanager
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "tests" / "fixtures" / "routes"

# What a shopper typed or pasted. The comparison follows whatever the
# search picks for them (the auto-pick, else the first picker card).
CASES = [
    "Adidas Originals Women Handball Spezial Sneakers",
    "Adidas Originals Women Handball Spezial",
    "https://www.nykaafashion.com/nike-charcoal-men-s-downshifter-14-running-shoes/p/27579262",
    "nike downshifter 14 men black",
    "philips hl7756 mixer grinder 750w",
    "boat rockerz 550 headphones",
    "realme buds t310 earbuds",
    "samsung galaxy m35 5g 8gb 128gb",
]


def slug(text: str) -> str:
    text = re.sub(r"^https?://(www\.)?", "", text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:70]


def _key(door: str, *args) -> str:
    return door + " " + json.dumps(args, sort_keys=True, ensure_ascii=False)


class Tape:
    """Recorded answers, keyed by door and arguments."""

    def __init__(self, calls: dict | None = None):
        self.calls: dict[str, object] = calls or {}
        self.lock = threading.Lock()
        self.missed: list[str] = []
        self.soft_missed: list[str] = []

    def record(self, key: str, value):
        with self.lock:
            self.calls[key] = value
        return value

    def play(self, key: str, default, soft: bool = False):
        """`soft`: a store-list page or Flipkart search that never came back
        within the budget at capture time isn't on the tape; replay treats
        it as still too slow rather than as a hole in the recording."""
        with self.lock:
            if key in self.calls:
                return self.calls[key]
            (self.soft_missed if soft else self.missed).append(key)
        return default


@contextmanager
def recording(tape: Tape):
    from src.repositories import searchapi_repository, flipkart_repository
    from src.services import search_service

    real_get, real_fk, real_page = searchapi_repository._get, flipkart_repository.search, search_service._fetch_url_page

    def get(params: dict) -> dict:
        return tape.record(_key("searchapi", params), real_get(params))

    def fk(query: str) -> list[dict]:
        return tape.record(_key("flipkart", query), real_fk(query))

    def page(url: str):
        return tape.record(_key("page", url), list(real_page(url)))

    with mock.patch.object(searchapi_repository, "_get", get), \
            mock.patch.object(flipkart_repository, "search", fk), \
            mock.patch.object(search_service, "_fetch_url_page", page):
        yield


@contextmanager
def replaying(tape: Tape):
    from src.repositories import searchapi_repository, flipkart_repository, context_dev_repository, crawlbase_repository
    from src.services import search_service

    def get(params: dict) -> dict:
        # Store lists that were too slow at capture, and the extra
        # "<product> <store>" gap searches (their wording follows the ID
        # card, which the matcher may phrase differently now), are soft.
        q = (params.get("q") or "").lower()
        soft = params.get("engine") == "google_product_offers" or any(
            q.endswith(" " + m.lower()) for m in search_service._MARKETPLACES)
        return tape.play(_key("searchapi", params), {"error": "not on the tape"}, soft)

    def fk(query: str) -> list[dict]:
        return tape.play(_key("flipkart", query), [], soft=True)

    def page(url: str):
        return tuple(tape.play(_key("page", url), [None, None, None, None, url]))

    with mock.patch.object(searchapi_repository, "_get", get), \
            mock.patch.object(flipkart_repository, "search", fk), \
            mock.patch.object(search_service, "_fetch_url_page", page), \
            mock.patch.object(context_dev_repository, "fetch_rendered_html", lambda *a, **k: None), \
            mock.patch.object(crawlbase_repository, "fetch_rendered_html", lambda *a, **k: None):
        yield


def run_case(text: str, chosen: str | None = None) -> dict:
    """Search, follow the pick, compare. Returns what the shopper would see.
    `chosen` is the product_token the shopper tapped when the journey was
    recorded; a typed search always shows the picker, so a replay taps the
    same card rather than the first one."""
    from src.services import search_service

    found = search_service.search_candidates(text)
    products = found.get("products") or []
    pick = found.get("auto_pick") or next((p for p in products if p.get("product_token") == chosen), None) or (
        products[0] if products else None)
    if not pick:
        return {"search": found, "pick": None, "routes": None}
    routes = search_service.routes_without_waiting_on_check(
        pick["product_token"], text, pick.get("title") or "", pick.get("price"), pick.get("source") or "")
    return {"search": {k: v for k, v in found.items() if k != "products"} | {"products": found.get("products", [])[:8]},
            "pick": {k: pick.get(k) for k in ("title", "price", "source", "product_token")},
            "routes": routes}


def shops(result: dict) -> list[tuple[str, float, float]]:
    """(store, listed price, final cost) for the recommended route and
    alternatives, then every other verified store at its listed price. The
    routes show at most four stores, so a fifth shop at the same price lives
    only in the verified list."""
    out = result.get("routes") or {}
    rt = out.get("routes") or {}
    rows = [rt.get("recommended")] + list(rt.get("alternatives") or [])
    seen = [(r["merchant"], r["listed_price"], r["final_cost"]) for r in rows if r]
    names = {m for m, _, _ in seen}
    for r in out.get("results") or []:
        if r.get("merchant") not in names and r.get("price") is not None:
            seen.append((r["merchant"], r["price"], r["price"]))
            names.add(r["merchant"])
    return seen


def capture(cases: list[str]) -> int:
    from dotenv import load_dotenv
    load_dotenv()
    OUT.mkdir(parents=True, exist_ok=True)
    for text in cases:
        path = OUT / f"{slug(text)}.json"
        if path.exists():
            print(f"  kept  {path.name}")
            continue
        tape = Tape()
        with recording(tape):
            result = run_case(text)
        path.write_text(json.dumps({"input": text, "pick": result["pick"], "shops_at_capture": shops(result),
                                    "must_include": [], "calls": tape.calls}, indent=1, ensure_ascii=False))
        print(f"  saved {path.name}: {len(tape.calls)} calls, shops {shops(result)}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["capture"]:
        sys.exit(capture(sys.argv[2:] or CASES))
    print(__doc__)
