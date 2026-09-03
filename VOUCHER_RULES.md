# Voucher T&C Rules Standardization

## Overview

This system standardizes how voucher T&Cs are interpreted, eliminating hallucination and ensuring Dealo's logic never invents rules that don't exist.

## The Rules File

**Location:** `data/voucher_rules.json`

Each entry is keyed `{source}:{slug}` and contains:

```json
{
  "gyftr:titan": {
    "brand_name": "Titan",
    "source": "gyftr",
    "slug": "titan",
    "rules": {
      "can_combine": {"value": "yes", "evidence": "..."},
      "max_cards_per_order": {"value": 5, "evidence": "..."},
      "one_time_use": {"value": "yes", "evidence": "..."},
      "works_online": {"value": "no", "evidence": "..."},
      "works_in_store": {"value": "yes", "evidence": "..."},
      "works_on_sale_items": {"value": "no", "evidence": "..."},
      "combines_with_store_offers": {"value": "no", "evidence": "..."},
      "ceiling_amount": {"value": 50000, "evidence": "..."},
      "ceiling_period": {"value": "calendar month", "evidence": "..."},
      "min_order_value": {"value": null, "evidence": ""},
      "excludes": {"value": ["Titan Nebula Watches"], "evidence": "..."},
      "max_spend_per_purchase": {"value": null, "evidence": ""},
      "delivery_wait_days": {"value": 0, "evidence": "..."}
    }
  }
}
```

## Three-State Logic

Every field uses three states:
- **"yes"** — explicitly stated in T&Cs (with quote)
- **"no"** — explicitly prohibited in T&Cs (with quote)
- **"not_stated"** — T&Cs don't mention this (never guesses)
- **null** — numeric field where no value applies

This prevents both:
- False negatives (assuming "not mentioned = no")
- False positives (assuming "not mentioned = yes")

## Using in Code

```python
from src.services.voucher_service import validate_voucher_against_rules

# Check if a voucher can be used for a specific scenario
valid, reason = validate_voucher_against_rules(
    source="gyftr",
    slug="titan",
    use_case={
        "on_sale_item": True,
        "combine_with_other": False,
    }
)

if not valid:
    print(f"Cannot use: {reason}")
```

## Curating New Rules

To add or update a brand's rules:

1. Read its full T&Cs in `data/{source}_master.json`
2. For each field, answer one of:
   - Quote the exact sentence that states this rule (value = yes/no)
   - Leave evidence empty (value = "not_stated" / null)
3. Never invent or interpret — every non-empty value must cite a real sentence

## Current Coverage

**Pilot (8 core brands, basic rules):** 8 entries across Gyftr/Maximize/BuyHatke

- Titan, Myntra, Amazon, Bata, Nykaa, AJIO, Fastrack, Croma

**Full extraction planned:** 1,350+ brands when API credits allow.

Until then, the 8-brand pilot rules are live and prevent the most common mistakes (sale items, combining, per-order caps).

## Integration Status

- ✅ `voucher_service.py`: Loads rules and provides validation API
- ⏳ `build_deals()`: Can use `validate_voucher_against_rules()` to filter out invalid deals
- ⏳ `pipeline.py`: Can check rules before recommending routes
- ⏳ `whatsapp/formatter.py`: Can explain why a voucher can't be used

See `src/services/voucher_service.py` for the validation function.
