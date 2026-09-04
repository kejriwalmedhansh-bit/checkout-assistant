# Reading voucher terms

You are reading gift-card terms for a shopping assistant that tells people which
voucher to buy and how to use it. Someone will act on what you write, standing at
a till. Accuracy matters more than completeness.

Read every listing in your assigned chunk file and produce one JSON object per
listing.

## Rules

- **Report only what the text states.** Never infer, never fill a gap with what is
  usually true. Anything the text does not address is `"not_stated"` (or `[]` for
  `excludes`).
- **Quote your evidence.** For every field you do not mark `not_stated`, put the
  exact sentence that supports it in `quotes`, copied verbatim from the source.
  No sentence, no claim.
- `max_vouchers_per_bill` — how many gift vouchers the shop accepts in ONE bill.
  - "10 vouchers can be used in a single transaction" → `10`
  - "Multiple Gift Vouchers CAN be used in one bill" → `"unlimited"`
  - "Only one Gift Card can be used per booking" → `1`
  - A percentage ("up to 45% off on vouchers") is NOT a voucher count → `"not_stated"`
- `spend_scope` — what the voucher may be spent on, when narrower than the brand
  as a whole: "Seat Selection, Extra Baggage and Sports Equipment", "Food &
  Non-Alcoholic beverages", "Gold Jewellery only". If it buys anything the brand
  sells, `"not_stated"`.
- `monthly_purchase_cap` limits BUYING vouchers. `max_spend_per_purchase` limits
  SPENDING them. Keep them apart.
- `partial_redemption` — whether unused balance survives. "Unused balance will be
  forfeited" → `"no"`. "Valid for partial redemption" → `"yes"`.
- Terms are written by three platforms and are often repetitive or contradictory.
  Where a page contradicts itself, prefer the more specific statement and quote
  that one.

## Output

Write a JSON object mapping each listing's `key` to:

```json
{
  "works_online": "yes|no|not_stated",
  "works_in_store": "yes|no|not_stated",
  "one_time_use": "yes|no|not_stated",
  "partial_redemption": "yes|no|not_stated",
  "max_vouchers_per_bill": 10,
  "can_combine_with_store_offers": "yes|no|not_stated",
  "spend_scope": "Gold Jewellery only",
  "excludes": ["Titan Nebula collection of Watches"],
  "min_order_value": "not_stated",
  "max_spend_per_purchase": "not_stated",
  "monthly_purchase_cap": 10000,
  "validity": "12 months from purchase",
  "delivery_wait": "not_stated",
  "quotes": {
    "max_vouchers_per_bill": "10 vouchers can be used in a single transaction.",
    "spend_scope": "Gift Vouchers are ACCEPTED only on Gold Coins/Jewellery."
  }
}
```

Numbers as numbers, not strings. Write the file with the Write tool. Do not
summarise or comment — the file is the whole deliverable.
