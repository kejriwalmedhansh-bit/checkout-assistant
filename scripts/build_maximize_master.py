"""Merge scripts/scrape_maximize.py's raw per-product output into a single
maximize_master.json.

Unlike GyFTR, Maximize's product pages already expose stacking/clubbing rules
as structured yes/no fields (no free-text T&C regex parsing needed for that).
The one real grouping decision is: some catalog entries are genuinely
different products under the same brand (e.g. "Amazon Fresh Voucher" vs
"Amazon Prime Voucher - 12 months Membership" have different redemption
types and T&Cs entirely) while others are just denomination variants of the
identical card (e.g. "Croma" vs "Croma (Custom)"). Only the latter — an exact
name match after stripping a "(Custom)" suffix — are grouped together; every
other distinct product_name stays its own top-level entry, keyed by its own
slug. This mirrors gyftr_master.json's field names where the concept matches.
"""
import json, re

PROGRESS_FILE = "db/maximize_scrape_progress.json"
OUT_FILE = "db/maximize_master.json"


def slugify(name):
    s = re.sub(r"\(custom\)", "", name, flags=re.IGNORECASE).strip()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def build():
    with open(PROGRESS_FILE) as f:
        scraped = json.load(f)

    groups = {}
    for pid, rec in scraped.items():
        product_name = rec.get("product_name") or rec.get("brand_name") or pid
        key = slugify(product_name)
        groups.setdefault(key, []).append(rec)

    master = {}
    for key, variants in groups.items():
        base_name = re.sub(r"\s*\(custom\)\s*", "", variants[0].get("product_name", ""),
                            flags=re.IGNORECASE).strip() or variants[0].get("brand_name")

        variant_records = []
        for rec in variants:
            status = "scrape_failed" if rec.get("error") else \
                     ("active" if rec.get("brand_name") else "not_scraped")
            variant_records.append({
                "product_name": rec.get("product_name"),
                "maximize_product_id": rec.get("maximize_product_id"),
                "url": rec.get("url"),
                "description": rec.get("description"),
                "redemption_type": rec.get("redemption_type"),
                "denominations": rec.get("denominations", []),
                "custom_amount": rec.get("custom_amount", False),
                "custom_amount_min": rec.get("custom_amount_min"),
                "custom_amount_max": rec.get("custom_amount_max"),
                "quantity_cap_per_order": rec.get("quantity_cap_per_order"),
                "discounts": rec.get("discounts", {}),
                "best_payment_method": rec.get("best_payment_method"),
                "best_discount_pct": rec.get("best_discount_pct"),
                "multi_use": rec.get("multi_use"),
                "can_club_with_offers": rec.get("can_club_with_offers"),
                "cards_stackable": rec.get("cards_stackable"),
                "validity": rec.get("validity"),
                "how_to_redeem_steps": rec.get("how_to_redeem_steps"),
                "full_terms_and_conditions": rec.get("full_terms_and_conditions"),
                "rates_source": "logged_in" if rec.get("logged_in") else "logged_out",
                "status": status,
                "error": rec.get("error"),
                "last_scraped": rec.get("last_scraped"),
            })

        master[key] = {
            "brand_name": base_name,
            "maximize_product_ids": [v.get("maximize_product_id") for v in variants],
            "variants": variant_records,
        }

    with open(OUT_FILE, "w") as f:
        json.dump(master, f, indent=2, ensure_ascii=False)

    total_variants = sum(len(v["variants"]) for v in master.values())
    active = sum(1 for v in master.values() for p in v["variants"] if p["status"] == "active")
    failed = sum(1 for v in master.values() for p in v["variants"] if p["status"] != "active")

    print(f"Master file written: {OUT_FILE}")
    print(f"Brand groups: {len(master)}")
    print(f"Total product variants: {total_variants}")
    print(f"Active: {active}  Failed/incomplete: {failed}")


if __name__ == "__main__":
    build()
