#!/usr/bin/env python3.11
"""
Normalize existing GyFTR and Maximize data into the canonical schema.
For Maximize, restores dropped fields from the raw db/maximize_master.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clean_maximize_master import EXCLUDE_PRODUCT_IDS  # noqa: E402

GYFTR_RAW = Path(__file__).parent.parent / "data" / "gyftr_master.json"
MAXIMIZE_RAW = Path(__file__).parent.parent / "db" / "maximize_master.json"
MAXIMIZE_CLEANED = Path(__file__).parent.parent / "data" / "maximize_master.json"

GYFTR_OUT = Path(__file__).parent.parent / "data" / "gyftr_master.json"
MAXIMIZE_OUT = Path(__file__).parent.parent / "data" / "maximize_master.json"

def normalize_gyftr(gyftr_data: dict) -> dict:
    """Normalize GyFTR data into canonical schema."""
    normalized = {}

    for slug, brand in gyftr_data.items():
        normalized[slug] = {
            "brand_name": brand.get("brand_name"),
            "slug": slug,
            "source": "GyFTR",
            "products": [
                {
                    "product_name": brand.get("brand_name"),
                    "source_url": None,
                    "redemption_type": brand.get("redemption_type"),
                    "denominations": brand.get("denominations", []),
                    "is_custom_denom": brand.get("is_custom_denom", False),
                    "custom_min": brand.get("custom_min"),
                    "custom_max": brand.get("custom_max"),
                    "discounts": brand.get("discounts", {}),
                    "best_payment_method": brand.get("best_payment_method"),
                    "best_discount_pct": brand.get("best_discount_pct"),
                    "stack_limit": brand.get("stack_limit"),
                    "value_cap": brand.get("value_cap"),
                    "purchase_cap_per_txn": brand.get("purchase_cap_per_txn"),
                    "status": brand.get("status", "active"),
                    "last_scraped": brand.get("last_scraped"),
                }
            ],
            "description": None,  # GyFTR doesn't have this
            "important_instructions_raw": brand.get("important_instructions_raw"),
            "how_to_redeem_steps": brand.get("how_to_redeem_steps"),
            "full_terms_and_conditions": brand.get("full_terms_and_conditions"),
            "redemption_restrictions": brand.get("redemption_restrictions"),
            "notes": brand.get("notes"),
            "stack_limit_confidence": brand.get("stack_limit_confidence"),
            "can_club_with_offers": brand.get("can_club_with_offers"),
            "one_time_use": brand.get("one_time_use"),
        }

    return normalized

def normalize_maximize(raw_data: dict) -> dict:
    """Normalize Maximize data into canonical schema.
    Restores fields from raw db/maximize_master.json that were dropped in the cleaned version.
    """
    normalized = {}

    for slug, brand in raw_data.items():
        brand_name = brand.get("brand_name", slug)
        products = []

        for variant in brand.get("variants", []):
            # Same manually-verified exclusions clean_maximize_master.py
            # applies (e.g. Amazon Prime Lite/Shopping Edition/membership —
            # subscription top-ups, not spendable shopping credit) — this
            # script reads straight from the raw scrape, so without this it
            # silently reintroduces every listing that override table exists
            # to drop, including into the live data/ file (found 2026-08-08:
            # Prime Lite's inflated 15% headline rate was winning "best
            # tier" over the real ~1.25-1.5% Amazon Pay gift card).
            if str(variant.get("maximize_product_id")) in EXCLUDE_PRODUCT_IDS:
                continue

            # Restore full_terms_and_conditions from raw data
            tnc = variant.get("full_terms_and_conditions") or variant.get("tnc", {})
            if isinstance(tnc, dict):
                tnc_text = tnc.get("content")
            else:
                tnc_text = tnc

            # Restore can_club_with_offers and one_time_use from raw data
            can_club = variant.get("can_club_with_offers")
            one_time_use = not variant.get("multi_use", False)  # inverse of multi_use

            products.append({
                "product_name": variant.get("product_name"),
                "source_url": variant.get("url"),
                "redemption_type": variant.get("redemption_type", "Both"),
                "denominations": variant.get("denominations", []),
                "is_custom_denom": variant.get("custom_amount", False),
                "custom_min": variant.get("custom_amount_min"),
                "custom_max": variant.get("custom_amount_max"),
                "discounts": normalize_maximize_discounts(variant.get("discounts")),
                "best_payment_method": variant.get("best_payment_method"),
                "best_discount_pct": variant.get("best_discount_pct"),
                "stack_limit": variant.get("quantity_cap_per_order"),
                "value_cap": variant.get("value_cap"),
                "purchase_cap_per_txn": None,
                "status": variant.get("status", "active"),
                "last_scraped": variant.get("last_scraped"),
            })

        if not products:
            # Every variant was an excluded subscription/different-product
            # listing (e.g. a brand that's Maximize-only for a top-up type
            # we don't treat as a voucher) — nothing left to offer.
            continue

        # Get first *kept* variant's T&Cs/description (they should be the
        # same for all real variants of a brand) — must skip excluded
        # variants here too, or an excluded one sitting first in the raw
        # list (as Amazon's Prime Lite did) leaks its own description/T&Cs
        # onto the brand record even after its own tier was dropped above.
        first_variant = next(
            (v for v in brand.get("variants", [])
             if str(v.get("maximize_product_id")) not in EXCLUDE_PRODUCT_IDS),
            {},
        )
        tnc = first_variant.get("full_terms_and_conditions") or first_variant.get("tnc", {})
        if isinstance(tnc, dict):
            tnc_text = tnc.get("content")
        else:
            tnc_text = tnc

        can_club = first_variant.get("can_club_with_offers")
        one_time_use = not first_variant.get("multi_use", False)

        normalized[slug] = {
            "brand_name": brand_name,
            "slug": slug,
            "source": "Maximize",
            "products": products,
            "description": first_variant.get("description"),
            "important_instructions_raw": None,  # Maximize never scraped this
            "how_to_redeem_steps": first_variant.get("how_to_redeem_steps"),
            "full_terms_and_conditions": tnc_text,
            "redemption_restrictions": None,
            "notes": None,
            "stack_limit_confidence": None,
            "can_club_with_offers": can_club,
            "one_time_use": one_time_use,
        }

    return normalized

def normalize_maximize_discounts(discount_obj: dict) -> dict:
    """Extract just the percentage discount from Maximize's nested discount structure."""
    if not discount_obj:
        return {}

    result = {}
    for method, details in discount_obj.items():
        if isinstance(details, dict):
            pct = details.get("instant_discount_pct")
        else:
            pct = details

        if pct is not None:
            try:
                result[method] = float(pct)
            except (ValueError, TypeError):
                pass

    return result

def main():
    print("Normalizing GyFTR...")
    if GYFTR_RAW.exists():
        with open(GYFTR_RAW) as f:
            gyftr_data = json.load(f)
        gyftr_normalized = normalize_gyftr(gyftr_data)
        print(f"  Normalized {len(gyftr_normalized)} brands")

        with open(GYFTR_OUT, "w") as f:
            json.dump(gyftr_normalized, f, indent=2)
        print(f"  Saved to {GYFTR_OUT}")
    else:
        print(f"  WARNING: {GYFTR_RAW} not found, skipping")

    print("\nNormalizing Maximize...")
    if MAXIMIZE_RAW.exists():
        with open(MAXIMIZE_RAW) as f:
            maximize_data = json.load(f)
        maximize_normalized = normalize_maximize(maximize_data)
        print(f"  Normalized {len(maximize_normalized)} brands")

        with open(MAXIMIZE_OUT, "w") as f:
            json.dump(maximize_normalized, f, indent=2)
        print(f"  Saved to {MAXIMIZE_OUT}")
    else:
        print(f"  WARNING: {MAXIMIZE_RAW} not found, skipping")

if __name__ == "__main__":
    main()
