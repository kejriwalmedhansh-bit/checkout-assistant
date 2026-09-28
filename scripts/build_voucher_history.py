#!/usr/bin/env python3.11
"""One row per voucher per scrape, across every scrape in git — for trends.

voucher_offers.csv is the catalogue as it is today; this is how it got here.
Every version of the three price masters ever committed is read back from git
(plus the working tree, so a refresh that is not committed yet is included),
and each product is filed under the date it was scraped (`last_scraped`, or the
commit date where an early master did not record one). When several commits
carry the same scrape — a scrape followed by fixes to it — the latest commit
wins, because the fixes are corrections to that same day's figures.

Rebuilt from scratch every time, so it cannot drift: run it after each refresh.
The Google Sheet reads it from GitHub like voucher_offers.csv.

  python3.11 scripts/build_voucher_history.py      -> voucher_history.csv
"""
import csv
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "voucher_history.csv"
MASTERS = {  # platform -> paths it has lived at, oldest first
    "gyftr": ["db/gyftr_master.json", "data/gyftr_master.json"],
    "buyhatke": ["db/buyhatke_master.json", "data/buyhatke_master.json"],
    "maximize": ["db/maximize_master.json", "data/maximize_master.json"],
}
COLUMNS = ["Scrape Date", "Platform", "Brand", "Product", "Listing URL", "Status",
           "Best Saving %", "Best Method", "UPI Saving %", "Saving By Method",
           "Denominations", "Custom Min", "Custom Max", "Typed Min", "Typed Max",
           "Stack Limit", "From Commit"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout


def versions(path: str):
    """(commit date, short hash, parsed json) for every commit of `path`, oldest first."""
    for line in reversed(git("log", "--format=%as %h", "--", path).splitlines()):
        date, sha = line.split()
        try:
            yield date, sha, json.loads(git("show", f"{sha}:{path}"))
        except json.JSONDecodeError:
            continue


def products(master: dict):
    """(brand, product) pairs; early masters kept one flat product per brand."""
    if not isinstance(master, dict):
        return
    for slug, entry in master.items():
        if not isinstance(entry, dict):
            continue
        brand = entry.get("brand_name") or slug
        # "variants" (db/, July) and "tiers" (data/, late July) are the same
        # thing under the names the early Maximize masters used.
        for p in entry.get("products") or entry.get("tiers") or entry.get("variants") or [entry]:
            if isinstance(p, dict):
                yield slug, brand, p


def row(platform: str, slug: str, brand: str, p: dict, date: str, sha: str) -> dict:
    rates = p.get("discounts") if isinstance(p.get("discounts"), dict) else {}
    # The first Maximize master kept both routes per method; only the instant
    # discount is a saving (MaxCoins are cashback).
    rates = {m: (v.get("instant_discount_pct") if isinstance(v, dict) else v) for m, v in rates.items()}
    best = p.get("best_discount_pct", p.get("best_discount"))
    if best is None and rates:
        best = max((v for v in rates.values() if isinstance(v, (int, float))), default=None)
    upi = rates.get("UPI", rates.get("any"))
    return {
        "Scrape Date": (p.get("last_scraped") or date)[:10],
        "Platform": platform,
        "Brand": brand,
        "Product": p.get("product_name") or brand,
        "Listing URL": (p.get("source_url") or p.get("voucher_url") or p.get("url")
                        or (f"https://www.gyftr.com/{slug}" if platform == "gyftr" else "")),
        "Status": p.get("status") or "",
        "Best Saving %": best,
        "Best Method": p.get("best_payment_method") or "",
        "UPI Saving %": upi,
        "Saving By Method": json.dumps(rates, ensure_ascii=False) if rates else "",
        "Denominations": " ".join(str(d) for d in p.get("denominations") or []),
        "Custom Min": p.get("custom_min", p.get("custom_amount_min")),
        "Custom Max": p.get("custom_max", p.get("custom_amount_max")),
        "Typed Min": p.get("typed_min"),
        "Typed Max": p.get("typed_max"),
        "Stack Limit": p.get("stack_limit"),
        "From Commit": sha,
    }


def main() -> None:
    rows: dict[tuple, dict] = {}
    for platform, paths in MASTERS.items():
        snaps = [v for path in paths for v in versions(path)]
        live = REPO / paths[-1]
        if live.exists():
            snaps.append(("working-tree", "uncommitted", json.loads(live.read_text())))
        for date, sha, master in snaps:
            if date == "working-tree":
                date = git("log", "-1", "--format=%as").strip()
            for slug, brand, p in products(master):
                r = row(platform, slug, brand, p, date, sha)
                # Later commits overwrite earlier ones for the same scrape date.
                rows[(r["Scrape Date"], platform, r["Listing URL"] or slug, r["Product"])] = r

    ordered = sorted(rows.values(), key=lambda r: (r["Platform"], r["Brand"].lower(), r["Product"].lower(), r["Scrape Date"]))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(ordered)
    dates = sorted({r["Scrape Date"] for r in ordered})
    print(f"{len(ordered)} rows, {len(dates)} scrape dates ({dates[0]} .. {dates[-1]}) -> {OUT.name}")
    for platform in MASTERS:
        ds = sorted({r["Scrape Date"] for r in ordered if r["Platform"] == platform})
        print(f"  {platform:9} {len(ds):3} dates: {', '.join(ds)}")


if __name__ == "__main__":
    main()
