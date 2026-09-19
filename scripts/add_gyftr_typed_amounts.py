"""One-off: record Gyftr's "type any amount" box, and drop the ₹100 cards
that are not cards.

Gyftr's brand feed marks each item with a service_type. 1 is a fixed card. 3
is the box on the same page where the shopper types any amount — Croma, Titan,
Domino's: "100 - 10000" — with mrp as the minimum and max_value the maximum.
2 is e-Pay, a wallet top-up sold on a separate page.

fix_gyftr_custom_denom.py (2026-09-05) saw that 2 and 3 report the same
₹100-10,000 and concluded Gyftr sells no custom amount, because Netmeds (type
2 only) has no box. That holds for type 2 and not for type 3: 128 brands have
the box, and matching the feed against the live page agreed on all 16 brands
checked (2026-09-19). The same misreading also left their ₹100 minimum in
`denominations`, so Dealo could plan "3x₹100" cards that do not exist.

Reads the live feed, so run it on a fresh day; brands the feed fails to return
are left untouched and listed.

    .venv/bin/python scripts/add_gyftr_typed_amounts.py --check   # report only
    .venv/bin/python scripts/add_gyftr_typed_amounts.py           # apply
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import sys
import urllib.request

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
MASTER = DATA / "gyftr_master.json"
OFFERS = DATA / "voucher_offers.json"
DETAIL = "https://api.gyftr.com/gyftrapi/api/v1/brand/detail/{slug}"


def fetch(slug: str) -> tuple[str, list | None]:
    req = urllib.request.Request(DETAIL.format(slug=slug), headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://www.gyftr.com/"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return slug, json.load(r)["data"]["products"] or []
    except Exception:
        return slug, None


def main() -> int:
    check_only = "--check" in sys.argv
    master = json.loads(MASTER.read_text())
    offers = json.loads(OFFERS.read_text())

    with cf.ThreadPoolExecutor(8) as pool:
        feed = dict(pool.map(fetch, master))

    failed, typed, dropped = [], [], []
    for slug, rec in master.items():
        items = feed.get(slug)
        if items is None:
            failed.append(slug)
            continue
        cards = {int(p["mrp"]) for p in items if p.get("service_type") == 1 and p.get("mrp")}
        not_cards = {int(p["mrp"]) for p in items if p.get("service_type") in (2, 3) and p.get("mrp")}
        box = [p for p in items if p.get("service_type") == 3 and p.get("max_value")]
        lo = min(int(p["mrp"]) for p in box) if box else None
        hi = max(int(p["max_value"]) for p in box) if box else None
        if box:
            typed.append((slug, lo, hi))

        # Only an amount the feed positively says is a box or e-Pay minimum,
        # and not also a real card, is removed. Anything else unexplained (a
        # card since sold out) is the refresh's business, not this script's.
        for product in rec.get("products") or []:
            product["typed_min"], product["typed_max"] = lo, hi
            old = product.get("denominations") or []
            keep = [d for d in old if not (d in not_cards and d not in cards)]
            if keep != old and (keep or box):
                dropped.append((slug, sorted(set(old) - set(keep))))
                product["denominations"] = keep

        offer = offers.get(f"gyftr:{slug}")
        if offer is not None:
            offer["typed_range"] = [lo, hi] if box else None
            offer["denominations"] = [d for d in offer.get("denominations") or []
                                      if not (d.get("value") in not_cards and d.get("value") not in cards)
                                      ] or ([] if box else offer.get("denominations"))

    print(f"brands with a type-any-amount box: {len(typed)}")
    for slug, lo, hi in typed[:8]:
        print(f"   {slug:<28} ₹{lo:,}-₹{hi:,}")
    print(f"brands losing an amount that is not a card: {len(dropped)}")
    for slug, gone in dropped[:8]:
        print(f"   {slug:<28} {gone}")
    if failed:
        print(f"feed did not answer, left untouched: {failed}")

    if check_only:
        print("\n--check given, nothing written.")
        return 0
    MASTER.write_text(json.dumps(master, indent=2, ensure_ascii=False) + "\n")
    OFFERS.write_text(json.dumps(offers, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {MASTER.name} and {OFFERS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
