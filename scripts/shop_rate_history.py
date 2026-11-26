#!/usr/bin/env python3
"""The "history" of every entry in react/src/data/shopPages.json: how each
seller's gift card discount has moved for that shop, as Dealo read it.

Why (26 Nov 2026): the shop pages share most of their wording, and Google's
updates go after pages where only the name changes. A shop's own rate
history is something no other page (and no other site) has.

Shape: page["history"] = {"dealo": {date: pct, ...}, "gyftr": {...}, ...},
oldest first. A point is written only when the rate differs from the one before
it, so a list reads "17% from 2 Jul, 15% from 28 Sep, 12% from 19 Oct".
Only what was really read: no guessing between readings.

- Other sellers: voucher_history.csv (every voucher refresh since July),
  matched to the page by the exact listing link, never by name.
- Dealo: build_shop_pages.py calls add_history() on each run (every morning)
  and carries the earlier points over from the previous file, so a new point
  lands the day the rate changes.

One-off, to fill Dealo's past from the saved daily files:
    python3 scripts/shop_rate_history.py --backfill
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "react" / "src" / "data" / "shopPages.json"
HISTORY_CSV = ROOT / "voucher_history.csv"


def _key(url: str) -> str:
    return unquote(url or "").rstrip("/").lower()


def _changes(readings: list[tuple[str, float]]) -> dict[str, float]:
    """Readings (date, pct) -> only the days the rate changed, oldest first."""
    out: dict[str, float] = {}
    last = None
    for day, pct in sorted(readings):
        if pct != last:
            out[day] = last = pct
    return out


def _seller_readings() -> dict[tuple[str, str], list[tuple[str, float]]]:
    """(seller, listing link) -> every day that listing was on sale, with its rate."""
    by_listing: dict[tuple[str, str], dict[str, float]] = {}
    if not HISTORY_CSV.exists():
        return {}
    with open(HISTORY_CSV, newline="") as f:
        for r in csv.DictReader(f):
            try:
                pct = float(r["Best Saving %"])
            except (TypeError, ValueError):
                continue
            if r["Status"] != "active" or pct <= 0:
                continue
            days = by_listing.setdefault((r["Platform"], _key(r["Listing URL"])), {})
            days[r["Scrape Date"]] = max(pct, days.get(r["Scrape Date"], 0))
    return {k: sorted(v.items()) for k, v in by_listing.items()}


def add_history(pages: list[dict], previous: dict[str, dict], dealo_past: dict[str, list] | None = None) -> None:
    """Set page["history"] on each of today's pages. `previous` is the last
    saved shopPages.json by slug: Dealo's earlier points live only there."""
    sellers = _seller_readings()
    for page in pages:
        slug = page["slug"]
        entry = {}
        dealo = list(previous.get(slug, {}).get("history", {}).get("dealo", {}).items()) + (dealo_past or {}).get(slug, [])
        if page.get("hubble") and page["hubble"].get("pct"):
            dealo.append((page["checked"], page["hubble"]["pct"]))
        if dealo:
            entry["dealo"] = _changes(dealo)
        for row in page.get("sellers", []):
            readings = list(sellers.get((row["source"], _key(row["url"])), []))
            if row.get("checked") and row.get("pct"):
                readings.append((row["checked"], row["pct"]))
            if readings:
                entry[row["source"]] = _changes(readings)
        page["history"] = entry


def _backfill() -> None:
    """Dealo's rate on each day a shopPages.json was saved to main."""
    shas = subprocess.run(
        ["git", "log", "--format=%H", "origin/main", "--", str(PAGES.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    past: dict[str, list[tuple[str, float]]] = {}
    for sha in shas:
        blob = subprocess.run(
            ["git", "show", f"{sha}:{PAGES.relative_to(ROOT)}"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        for page in json.loads(blob):
            h = page.get("hubble")
            if h and h.get("pct") and page.get("checked"):
                past.setdefault(page["slug"], []).append((page["checked"], h["pct"]))
    # Only the run that ends today: the rate Dealo sells at now and the first
    # day it was read. Older values came from hand rebuilds, not daily reads,
    # and cannot be vouched for (PVR's first card was the wrong one).
    past = {slug: list(_changes(r).items())[-1:] for slug, r in past.items()}
    pages = json.load(open(PAGES))
    for page in pages:
        page.pop("history", None)
    add_history(pages, {}, past)
    PAGES.write_text(json.dumps(pages, indent=2, ensure_ascii=False) + "\n")
    print(f"history added to {len(pages)} shops from {len(shas)} saved days -> {PAGES.relative_to(ROOT)}")


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        _backfill()
    else:
        sys.exit("run scripts/build_shop_pages.py (it adds the history), or pass --backfill")
