"""Turn db/maximize_master.json (raw scrape) into data/maximize_master.json
(what the app actually reads), the way data/gyftr_master.json was hand-cleaned
from the raw Gyftr scrape.

This is a manually-verified override table, not runtime guessing — every
exclusion below was checked against the listing's own terms and conditions
in a real working session, the same standard Gyftr's own override table
(wallet-detection fix) was held to. See CLAUDE.md / project notes for the
brand-by-brand reasoning; this file just encodes the conclusions.

Run: .venv/bin/python scripts/clean_maximize_master.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / "db" / "maximize_master.json"
OUT_PATH = ROOT / "data" / "maximize_master.json"

# Listings that are a different product entirely, not a pricing choice —
# excluded outright rather than treated as a tier.
EXCLUDE_PRODUCT_IDS = {
    "547": "Amazon Prime Lite — subscription, not shopping credit",
    "548": "Amazon Prime Shopping Edition — subscription, not shopping credit",
    "549": "Amazon Prime membership — subscription, not shopping credit",
    "448": "Amazon Fresh Voucher — groceries-only, narrower than Gyftr's general voucher",
    "1089": "Air India Ancillary Pass — seat/baggage add-ons only, not a fare voucher",
    "471": "Wonderchef Online — different redemption channel than Gyftr's in-store",
    "507": "Domino's listing that never finished scraping — no rate data",
}

# Maximize's raw redemption_type wording -> Gyftr's existing vocabulary, so
# both sources describe the same channel the same way everywhere (this is
# also what fixed the inflated "redemption type differs" count in the
# comparison sheet — most of that gap was label mismatch, not a real
# difference).
REDEMPTION_MAP = {
    "Online + In-store": "Both",
    "In-store": "Offline",
    "Store Locator": "Offline",
    "Online": "Online",
    None: "",
}


def normalize_redemption(raw):
    return REDEMPTION_MAP.get(raw, raw or "")


def flatten_discounts(raw_discounts):
    """Maximize's discounts are {method: {instant_discount_pct, maxcoins_earn_pct}}.
    Only instant_discount_pct is a real checkout discount — MaxCoins is a
    loyalty-points earn rate, never blended into effective-price math, same
    as card reward points are kept separate from voucher discounts elsewhere
    in this codebase."""
    flat = {}
    for method, rates in (raw_discounts or {}).items():
        pct = (rates or {}).get("instant_discount_pct")
        if pct is not None:
            flat[method] = pct
    return flat


def dedupe_denoms(denoms):
    return sorted(set(int(d) for d in (denoms or []) if d is not None))


def clean():
    with open(IN_PATH) as f:
        raw = json.load(f)

    out = {}
    excluded_count = 0
    dropped_brands = 0

    for slug, brand in raw.items():
        tiers = []
        for var in brand.get("variants", []):
            pid = str(var.get("maximize_product_id"))
            if pid in EXCLUDE_PRODUCT_IDS:
                excluded_count += 1
                continue

            discounts = flatten_discounts(var.get("discounts"))
            best_pct = var.get("best_discount_pct")
            if best_pct is None or not discounts:
                # No usable rate data (either a genuine 0%/no-offer listing,
                # or a scrape that never finished) — still keep the tier so
                # the brand isn't silently dropped, but it will naturally
                # never win a price comparison since calculate_effective_price
                # requires a non-zero discount_pct and voucher_amount.
                pass

            tiers.append({
                "maximize_product_id": var.get("maximize_product_id"),
                "product_name": var.get("product_name"),
                "voucher_platform": "Maximize",
                "voucher_url": var.get("url"),
                "redemption_type": normalize_redemption(var.get("redemption_type")),
                "denominations": dedupe_denoms(var.get("denominations")),
                "is_custom_denom": bool(var.get("custom_amount")),
                "custom_min": var.get("custom_amount_min"),
                "custom_max": var.get("custom_amount_max"),
                "stack_limit": var.get("quantity_cap_per_order"),
                "value_cap": None,
                "purchase_cap_per_txn": None,
                "discounts": discounts,
                "best_payment_method": var.get("best_payment_method"),
                "best_discount_pct": best_pct,
                "redemption_instructions": var.get("how_to_redeem_steps") or [],
                "how_to_redeem_short": None,
                "status": var.get("status"),
                "last_scraped": var.get("last_scraped"),
            })

        if not tiers:
            dropped_brands += 1
            continue

        out[slug] = {
            "brand_name": brand.get("brand_name"),
            "slug": slug,
            "tiers": tiers,
        }

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    total_tiers = sum(len(v["tiers"]) for v in out.values())
    print(f"Cleaned master written: {OUT_PATH}")
    print(f"Brands in: {len(raw)}  Brands out: {len(out)}  Dropped (no tiers left): {dropped_brands}")
    print(f"Tiers excluded (different product, not a pricing choice): {excluded_count}")
    print(f"Total tiers kept: {total_tiers}")


if __name__ == "__main__":
    clean()
