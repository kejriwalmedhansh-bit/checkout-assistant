"""One-off migration: clear the bogus custom-amount flag on BuyHatke brands.

The 2026-09-04 rate refresh also rewrote `is_custom_denom` from
`voucher_offers.json`, whose BuyHatke value came from a scraped flag that reads
True on 695 of 721 listings — including every brand that plainly sells fixed
amounts. `calculate_effective_price` prices a custom listing off `custom_max`,
and none of these carry one, so 364 brands stopped producing a deal at all.
151 of them are the best rate on any platform (Times Prime Power at 44.09%,
Live Mint at 58.88%), so the app was quietly recommending a worse route, or
none.

Rebuilding from `normalize_buyhatke_master.py` would fix the flag but roll the
file back to the 2026-08-20 raw scrape, undoing two weeks of rate updates on 53
brands. This repairs the flag in place and leaves every rate alone.

`build_voucher_offers.py` now derives the flag with one shared rule, and
`update_masters_from_scrape.py` refuses to set it without a usable range, so a
future refresh cannot reintroduce this.

    .venv/bin/python scripts/fix_buyhatke_custom_denom.py --check   # report only
    .venv/bin/python scripts/fix_buyhatke_custom_denom.py           # apply
"""
from __future__ import annotations

import json
import pathlib
import sys

MASTER = pathlib.Path(__file__).resolve().parent.parent / "data" / "buyhatke_master.json"


def main() -> int:
    check_only = "--check" in sys.argv
    data = json.loads(MASTER.read_text())

    fixed, kept, stranded = [], [], []
    for slug, rec in data.items():
        for prod in rec.get("products") or []:
            if not prod.get("is_custom_denom"):
                continue
            denoms = sorted({int(d) for d in (prod.get("denominations") or []) if d})
            if denoms:
                # Sells fixed amounts, so it was never custom whatever the flag said.
                fixed.append((rec.get("brand_name"), prod.get("best_discount_pct"), denoms[:5]))
                prod["is_custom_denom"] = False
                prod["custom_min"] = None
                prod["custom_max"] = None
            elif prod.get("custom_max"):
                kept.append(rec.get("brand_name"))          # a real custom listing
            else:
                # No amounts and no range: nothing here is priceable either way.
                # Left untouched rather than guessed at — flag for a re-scrape.
                stranded.append((rec.get("brand_name"), slug))

    print(f"brands corrected (fixed amounts, flag cleared): {len(fixed)}")
    for name, rate, denoms in fixed[:10]:
        print(f"   {str(name)[:28]:<28} {rate or 0:>6.2f}%  denominations {denoms}")
    if len(fixed) > 10:
        print(f"   ... and {len(fixed) - 10} more")
    print(f"\ngenuine custom listings left alone: {len(kept)}")
    if stranded:
        print(f"no amounts and no range — needs a re-scrape, untouched: {len(stranded)}")
        for name, slug in stranded[:10]:
            print(f"   {name} ({slug})")

    if check_only:
        print("\n--check given, nothing written.")
        return 0
    MASTER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {MASTER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
