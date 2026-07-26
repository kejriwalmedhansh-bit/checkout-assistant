"""maximize_to_csv.py — Flatten db/maximize_master.json into
maximize_database.csv for manual review, one row per product variant.

Usage:  .venv/bin/python scripts/maximize_to_csv.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "db" / "maximize_master.json"
OUTPUT_PATH = ROOT / "maximize_database.csv"

PAYMENT_MODES = ["UPI", "Debit Card", "Credit Card", "CC on UPI", "Diners Club", "Amex"]


def discount_col(discounts, mode):
    d = (discounts or {}).get(mode)
    if not d or d.get("instant_discount_pct") is None:
        return ""
    return f"{d['instant_discount_pct']}% off / {d.get('maxcoins_earn_pct', '')}% earn"


def main():
    with open(INPUT_PATH) as f:
        master = json.load(f)

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Brand Group", "Product Name", "Maximize ID", "URL", "Status",
            "Redemption Type", "Denominations", "Custom Amount", "Custom Range", "Qty Cap/Order",
            *[f"Discount ({m})" for m in PAYMENT_MODES],
            "Best Method", "Best Discount %",
            "Multi-Use", "Can Club w/ Offers", "Cards Stackable", "Validity",
            "How To Redeem", "Terms & Conditions", "Last Scraped",
        ])

        rows = 0
        for key, group in master.items():
            for v in group.get("variants", []):
                writer.writerow([
                    group.get("brand_name", ""),
                    v.get("product_name", ""),
                    v.get("maximize_product_id", ""),
                    v.get("url", ""),
                    v.get("status", ""),
                    v.get("redemption_type", ""),
                    " / ".join(str(d) for d in v.get("denominations", [])),
                    "Yes" if v.get("custom_amount") else "No",
                    f"{v.get('custom_amount_min', '')}-{v.get('custom_amount_max', '')}" if v.get("custom_amount") and v.get("custom_amount_min") else "",
                    v.get("quantity_cap_per_order", ""),
                    *[discount_col(v.get("discounts"), m) for m in PAYMENT_MODES],
                    v.get("best_payment_method", ""),
                    v.get("best_discount_pct", ""),
                    "Yes" if v.get("multi_use") else "No",
                    "Yes" if v.get("can_club_with_offers") else "No",
                    "Yes" if v.get("cards_stackable") else "No",
                    v.get("validity", ""),
                    " | ".join(v.get("how_to_redeem_steps") or []),
                    (v.get("full_terms_and_conditions") or "").replace("\n", " | "),
                    v.get("last_scraped", ""),
                ])
                rows += 1

    print(f"Wrote {rows} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
