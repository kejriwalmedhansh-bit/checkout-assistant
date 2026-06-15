# checkout-assistant

A price comparison engine for Indian e-commerce. Give it any product URL from a supported merchant; it finds the same product on other Indian retailers and returns a ranked price table.

## How it works

- **Step 1 — Extract:** Zyte API scrapes the source URL and returns structured product data (name, price, brand, SKU, availability, condition)
- **Step 2 — Discover:** Builds a clean `brand + model` search query, fetches Google Shopping price signals, then searches Flipkart, Croma, Reliance Digital, TataCLiQ, and Vijay Sales directly for verifiable product URLs
- **Step 3 — Verify:** Runs Zyte product extraction on each candidate URL (up to 8) to get live prices and availability
- **Step 4 — Match:** Token-level name similarity + spec conflict detection (color, storage, screen size, model number) classifies each result as Exact Match, Similar Match, or No Match
- **Step 5 — Output:** Prints a ranked price table sorted cheapest first; saves results to SQLite with a 30-minute cache

## Usage

```bash
uv run python main.py <product_url>
```

Example:

```bash
uv run python main.py "https://www.amazon.in/dp/B0CS6XNBZN"
```

## Output

```
  #   Merchant                            Price Match            Condition    Avail    Name
  ---------------------------------------------------------------------------------------------------------------------------------
  1   Fonezone                        ₹    27,699 Exact Match      Refurbished   ✓       Google Pixel 8A 128GB 8GB Ram Obsidian
  2   Flipkart                     ₹    49,999 (-6%) Exact Match      New           ✓       Google Pixel 8a (Obsidian, 128 GB) (8 GB RAM)
  3   Flipkart                     ₹    49,999 (-6%) Similar Match    New           ✓       Google Pixel 8a (Porcelain, 128 GB) (8 GB RAM)
  4   Flipkart                     ₹    49,999 (-6%) Similar Match    New           ✓       Google Pixel 8a (Aloe, 128 GB) (8 GB RAM)

  ──────────────────────────────────────────────────
  ★  Cheapest: Fonezone  at  ₹    27,699
```

## Current limitations

- **Google Shopping has no verifiable URLs** — Zyte's `productList` extractor returns empty `url` fields for Google Shopping results; discovery uses it for price signals only, not as a source of merchant links
- **Merchant search coverage is sparse** — of the five configured merchants, only Flipkart returns reliable results for most queries; Croma, Reliance Digital, and Vijay Sales frequently return zero results; TataCLiQ sometimes falls back to unrelated categories (caught and dropped automatically)
- **Refurbished detection is opportunistic** — condition is inferred from product name, `additionalProperties`, and description text; listings that don't expose a structured condition field may be misclassified as new

## Tech stack

| Component | Tool |
|---|---|
| Runtime | Python 3.14, [uv](https://github.com/astral-sh/uv) |
| Scraping | [Zyte API](https://www.zyte.com/zyte-api/) (`product`, `productList`, `browserHtml`) |
| Matching | `difflib.SequenceMatcher` (token-level) |
| Storage | SQLite via `sqlite3` |
| HTTP | `httpx` |
| HTML parsing | `beautifulsoup4` |
