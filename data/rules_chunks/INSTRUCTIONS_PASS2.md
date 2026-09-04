# Second reading — sweep for everything stated

Same job as the first pass, one difference in emphasis: **completeness**.

A measured sample showed a single reading finds most of a page's rules but not
all of them — roughly one listing in three had a rule stated plainly that the
first reading walked past. Missing a restriction is the expensive failure: the
shopper is told nothing, buys, and is refused at the till.

So work through every sentence of every listing rather than stopping once a
field is filled. Sentences that carry rules but are easy to skim past:

- "can only be redeemed at select X Stores" — that answers works_online (no)
- "Valid only for dine-in and takeaway" — that answers works_online (no)
- "not applicable on discounted products" — that answers combining with offers
- "no refund or credit note for the unused amount" — that answers partial redemption
- "Multiple GVs can be combined & added to the e-Pay balance" — that DOES answer
  vouchers per bill: it means several can be used ("unlimited")
- "valid only on products on discount up to 30%" — a ceiling on how deeply
  discounted the item may be, NOT a rule that it must be discounted

Everything else is unchanged:

- Report only what the text states. Anything it does not address is
  "not_stated" (or `[]` for excludes). Never infer.
- Every field you do not mark not_stated carries the exact sentence in `quotes`,
  copied verbatim. No sentence, no claim.
- `monthly_purchase_cap` limits BUYING or loading vouchers; a limit on SPENDING
  them goes in `max_spend_per_purchase` with the period in the value.
- `excludes` covers products and categories; put location and date restrictions
  there too, prefixed "location: " or "date: ".
- Where a page contradicts itself, prefer the more specific statement and quote
  that one.

Output shape and field names are exactly as in INSTRUCTIONS.md — read it for the
schema.
