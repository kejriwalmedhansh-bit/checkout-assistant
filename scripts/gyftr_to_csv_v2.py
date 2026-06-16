"""
gyftr_to_csv_v2.py — Flatten db/gyftr_vouchers.json into gyftr_vouchers_v2.csv.

Per-payment-method discount columns instead of a single "best discount" column,
and full (untruncated) T&Cs / redemption instructions.

Usage:  .venv/bin/python scripts/gyftr_to_csv_v2.py
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "db" / "gyftr_vouchers.json"
OUTPUT_PATH = ROOT / "gyftr_vouchers_v2.csv"

REDEMPTION_LABELS = {"ON": "Online", "OFF": "Offline", "B": "Both"}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip()


def _pg_discount_map(brand: dict) -> dict[str, float]:
    return {pg.get("pg_name"): pg.get("brand_pg_discount") for pg in brand.get("pgdis", [])}


def _credit_debit_discount(pg_map: dict[str, float]) -> str:
    cc, dc = pg_map.get("Credit Card"), pg_map.get("Debit Card")
    if cc is not None and dc is not None and cc != dc:
        return f"{cc}/{dc}"
    val = cc if cc is not None else dc
    return "" if val is None else str(val)


def _denominations(brand: dict) -> str:
    products = brand.get("products") or []
    values = []
    for p in products:
        mrp, max_value = p.get("mrp"), p.get("max_value")
        if max_value and max_value != mrp:
            values.append(f"{mrp}-{max_value} (custom)")
        elif mrp is not None:
            values.append(str(mrp))
    fixed = sorted({v for v in values if v.isdigit()}, key=int)
    custom = list(dict.fromkeys(v for v in values if not v.replace(".", "", 1).isdigit()))
    return " / ".join(fixed + custom)


def main() -> None:
    with open(INPUT_PATH) as f:
        brands = json.load(f)

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Brand Name", "Slug", "Redemption Type",
            "Discount % (Credit/Debit Card)", "Discount % (Net Banking)",
            "Discount % (UPI)", "Discount % (Paytm UPI)", "Discount % (Amazon Pay)",
            "Denominations Available", "Online/Offline",
            "How to Redeem", "T&Cs Summary",
        ])

        for brand in brands:
            pg_map = _pg_discount_map(brand)
            redemption = brand.get("redemption_type", "")

            def pct(name: str) -> str:
                val = pg_map.get(name)
                return "" if val is None else str(val)

            writer.writerow([
                brand.get("brand_name", ""),
                brand.get("slug", ""),
                redemption,
                _credit_debit_discount(pg_map),
                pct("Net Banking"),
                pct("UPI"),
                pct("PAYTM UPI"),
                pct("Amazon Pay"),
                _denominations(brand),
                REDEMPTION_LABELS.get(redemption, redemption),
                _strip_html(brand.get("checkout_instruction", "")),
                _strip_html(brand.get("important_instruction", "")),
            ])

    print(f"Wrote {len(brands)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
