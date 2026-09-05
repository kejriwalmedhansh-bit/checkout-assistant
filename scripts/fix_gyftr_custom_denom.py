"""One-off migration: clear the bogus custom-amount flag on Gyftr brands.

`build_master.py` used to call any SKU with `max_value != min_value` a
custom-amount voucher. Every Gyftr brand lists a ₹100 SKU reporting
min_value=100/max_value=10000, so 145 brands were recorded as "buy any amount
between ₹100 and ₹10,000" when Gyftr sells no such thing. `calculate_effective_price`
prefers a custom range over fixed denominations, so those brands were quoted
vouchers that cannot be bought — a ₹154 Netmeds voucher against a real
catalogue starting at ₹250 (reported by a shopper comparing against gyftr.com,
2026-09-05).

build_master.py is fixed, so a fresh scrape is already correct; this repairs
the master in place for anyone not re-scraping. Verified before writing: every
affected brand's `denominations` list already contains the mis-flagged SKU's
own price, so clearing the flag loses no purchasable denomination.

    .venv/bin/python scripts/fix_gyftr_custom_denom.py --check   # report only
    .venv/bin/python scripts/fix_gyftr_custom_denom.py           # apply
"""
from __future__ import annotations

import json
import pathlib
import sys

MASTER = pathlib.Path(__file__).resolve().parent.parent / "data" / "gyftr_master.json"


def main() -> int:
    check_only = "--check" in sys.argv
    data = json.loads(MASTER.read_text())

    fixed = []
    skipped = []
    for slug, rec in data.items():
        for prod in rec.get("products") or []:
            if not prod.get("is_custom_denom"):
                continue
            denoms = sorted({int(d) for d in (prod.get("denominations") or []) if d})
            if not denoms:
                # Nothing to fall back on — clearing the flag would leave the
                # brand unable to quote anything at all. Leave it and report.
                skipped.append((rec.get("brand_name"), slug))
                continue
            fixed.append((rec.get("brand_name"), prod.get("custom_min"), prod.get("custom_max"), denoms))
            prod["is_custom_denom"] = False
            prod["custom_min"] = None
            prod["custom_max"] = None

    print(f"brands corrected: {len(fixed)}")
    for name, lo, hi, denoms in fixed[:10]:
        print(f"   {str(name)[:28]:<28} was custom ₹{lo}-{hi}  ->  fixed denominations {denoms[:6]}")
    if len(fixed) > 10:
        print(f"   ... and {len(fixed) - 10} more")
    if skipped:
        print(f"\nleft alone (custom-flagged but no denominations to fall back on): {len(skipped)}")
        for name, slug in skipped:
            print(f"   {name} ({slug})")

    if check_only:
        print("\n--check given, nothing written.")
        return 0
    MASTER.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {MASTER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
