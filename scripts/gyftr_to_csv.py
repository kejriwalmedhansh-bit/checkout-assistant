"""
gyftr_to_csv.py — Flatten db/gyftr_vouchers.json into gyftr_vouchers.csv.

Usage:  .venv/bin/python scripts/gyftr_to_csv.py
"""

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "db" / "gyftr_vouchers.json"
OUTPUT_PATH = ROOT / "gyftr_vouchers.csv"

REDEMPTION_LABELS = {"ON": "Online", "OFF": "Offline", "B": "Both"}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip()


def _best_discount(brand: dict) -> tuple[float, str]:
    pgdis = brand.get("pgdis") or []
    if not pgdis:
        return brand.get("defaut_pg_dis") or 0, ""
    best = max(pgdis, key=lambda pg: pg.get("brand_pg_discount") or 0)
    return best.get("brand_pg_discount") or 0, best.get("pg_name") or ""


def _denominations(brand: dict) -> str:
    products = brand.get("products") or []
    values = []
    for p in products:
        mrp, max_value = p.get("mrp"), p.get("max_value")
        if max_value and max_value != mrp:
            values.append(f"{mrp}-{max_value} (custom)")
        elif mrp is not None:
            values.append(str(mrp))
    # De-dupe fixed denominations (sorted numerically) and custom ranges
    # (insertion order) — the API returns duplicate product entries for some brands.
    fixed = sorted({v for v in values if v.isdigit()}, key=int)
    custom = list(dict.fromkeys(v for v in values if not v.replace(".", "", 1).isdigit()))
    return " / ".join(fixed + custom)


def main() -> None:
    with open(INPUT_PATH) as f:
        brands = json.load(f)

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Brand Name", "Slug", "Redemption Type", "Default Discount %",
            "Best Discount %", "Payment Method for Best Discount",
            "Denominations Available", "Online/Offline", "T&Cs Summary",
        ])

        for brand in brands:
            best_pct, best_pg = _best_discount(brand)
            redemption = brand.get("redemption_type", "")
            tcs = _strip_html(brand.get("important_instruction", ""))[:100]

            writer.writerow([
                brand.get("brand_name", ""),
                brand.get("slug", ""),
                redemption,
                brand.get("defaut_pg_dis") or 0,
                best_pct,
                best_pg,
                _denominations(brand),
                REDEMPTION_LABELS.get(redemption, redemption),
                tcs,
            ])

    print(f"Wrote {len(brands)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
