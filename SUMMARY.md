# Checkout Assistant

Indian e-commerce price comparison engine. Given any Amazon India product URL, it finds the same (or similar) product across major Indian retailers and ranks results by price.

## How to run

```bash
uv run python main.py <amazon-india-url>
```

Example:

```bash
uv run python main.py "https://www.amazon.in/Apple-2026-MacBook-Laptop-chip/dp/B0GR1HPR1W"
```

Requires a `ZYTE_API_KEY` in `.env`.

## What it does

Five sequential steps:

**Step 1 — Extract** Calls Zyte's Extract API (`product: true`) on the source URL to get structured product data: name, brand, SKU/ASIN, MPN, price, regular price, currency, availability. Amazon India URLs get `?language=en_IN` appended automatically to force English content.

**Step 2 — Discover** Builds a search query from the product data, then runs two parallel searches:
- Google Shopping (`google.com/search?tbm=shop&gl=in&hl=en`) via Zyte `productList` — used as price intelligence only (80+ INR signals); Google does not expose merchant URLs for Indian results.
- Direct search on Flipkart, Croma, Reliance Digital, TataCLiQ, and Vijay Sales via Zyte `productList` — returns real product URLs for verification.

**Step 3 — Verify** Calls Zyte `product` extraction on each candidate URL (up to 8) to get authoritative name, price, and availability directly from the merchant page.

**Step 4 — Match** Classifies each verified result against the original using a tiered matcher:
- **Exact Match** — SKU match, or MPN/GTIN match, or strong brand + name similarity (≥ 78%) with no spec conflicts
- **Similar Match** — same product family but a different variant (color, storage, screen size) or moderate name similarity (60–77%) with same brand
- **No Match** — dropped from output

Conflict detection reads both the product name and Zyte `additionalProperties` (catches color and screen size differences that merchants omit from titles, e.g. Flipkart's `selected color` and `variant` fields). Apple part-number codes (e.g. `MDHC4HN/A`) are extracted and compared when present.

**Step 5 — Output** Saves results to SQLite (`checkout_assistant.db`) and prints a table sorted cheapest first. Results are cached for 30 minutes; a second run on the same URL within that window returns instantly from cache.

## Sample output

```
  #   Merchant                            Price Match            Avail    Name
  ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
  1   Amazon India                 ₹   110,290 (-8%) Exact Match       ✓       Apple 2026 MacBook Air 13″ …
  2   Flipkart                     ₹   110,290 (-8%) Exact Match       ✓       Apple MacBook Air (M5, 2026) …
  3   Flipkart                     ₹   138,990 (-4%) Similar Match     ✓       Apple MacBook Air (M5, 2026) … [Silver, 15″]

  ★  Cheapest: Amazon India  at  ₹   110,290
```

## Known limitations

- **Only Flipkart returns results consistently** from the direct merchant search. Croma, Reliance Digital, TataCLiQ, and Vijay Sales search pages currently return zero results — their page structures are not reliably parsed by Zyte `productList`.
- **Google Shopping merchant URLs unavailable for Indian results.** INR-priced items in Google Shopping `productList` have empty URL fields; only USD (US merchant) listings carry `aclk` redirect URLs. The Google Shopping data is therefore display-only price intelligence, not a source of verifiable merchant URLs.
- **No size matching for footwear/apparel.** Shoe size is not extracted, so a size-6 listing and a size-10 listing of the same shoe both show as Similar Match. The original Amazon URL's selected size is not propagated into the comparison.
- **MPN format inconsistency across marketplaces.** Amazon often returns a descriptive MPN (e.g. `"13-inch MacBook Air (M5, 2026)"`) rather than the manufacturer's part number (e.g. `MDHC4HN/A`), so cross-platform MPN matching rarely fires; matching falls back to brand + name similarity + spec conflict detection.
- **30-minute cache is per product URL.** Changing query parameters on the same product (e.g. selecting a different size or color on Amazon) creates a new cache entry.
- **Zyte `productList` timeout set to 120 s.** Some merchant search pages are slow; occasional timeouts may silently drop a merchant from Step 2 results.
