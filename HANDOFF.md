# Checkout Assistant — Handoff

Indian e-commerce price comparison engine. Give it a product URL or a text
query; it finds the same (or similar) product across other merchants, ranks
by price, and surfaces Gyftr gift-card voucher stacking deals on top of the
cheapest listings.

## 1. What's been built

### Layer 1 — Core price comparison pipeline (`main.py`, 5 steps)

1. **Extract** (`step1_extract`) — Zyte Extract API pulls structured product
   data (name, price, brand, availability) from a source URL. Has fallback
   chains for sites where structured extraction is unreliable:
   - Myntra: retries without `/buy` suffix, then derives name from the URL
     slug, then recovers price via `browserHtml` + JSON-LD parsing if the
     slug fallback left price empty.
   - Nykaa / AJIO: derives name from URL slug when structured extraction
     returns nothing.
   - Amazon: falls back to `browserHtml` regex parsing (title/price/brand)
     when structured extraction has low confidence.
   - `amzn.in` short links: resolved Zyte's low-confidence response to the
     canonical `amazon.in` URL and retries extraction against that.
   - Text-query mode (non-URL input) skips this step entirely — there's no
     source product to extract, just a search string.

2. **Discover & match** (`step2_discover_and_match` for URLs,
   `step2_discover_only` for text queries) — builds a `brand + model` search
   query and calls SerpAPI Google Shopping. For URL mode, runs results
   through `engine/matcher.py` to classify each as Exact Match / Similar
   Match / No Match (dropped) based on token similarity and conflict
   detection (submodel keywords, color, storage, size). For text-query mode,
   there's no source product to match against, so all results are labeled
   `"Listed"` and a **price-outlier filter** removes anything below 40% of
   the median price (catches mismatched/bait listings — e.g. a non-Meta
   Ray-Ban result showing up under a "Ray-Ban Meta" search).

3. **Resolve direct URLs** (`step3_resolve`) — SerpAPI's immersive product
   API resolves each Google Shopping result to direct seller URLs. Filters
   out out-of-stock sellers, foreign-marketplace domains (eBay, AliExpress,
   StockX, etc.), and sellers whose URL path references a different brand
   than the source product (catches mis-linked listings).

4. **Ranked table** (`step4_output`) — prints all results sorted
   Exact-first-then-Similar, then by price.

   **4b. Size/quantity comparison** (`step4b_size_comparison`) — when 2+
   distinct weight/volume sizes are detected across result titles (e.g. 9g
   vs 30g), normalizes to grams/ml and prints a unit-price comparison so a
   "cheaper" small size doesn't look like a better deal than a larger one.
   Silently skipped when fewer than 2 distinct sizes exist (e.g. electronics
   with no weight/volume spec).

5. **Gyftr vouchers** (`step5_vouchers`) — for each unique merchant among
   Exact Match / Listed results, looks up a matching Gyftr voucher and
   prints the best payment-method discount, recommended voucher purchase
   amount (using greedy denomination fill or full custom-amount loading),
   and the effective price after discount.

### Layer 2 — Gyftr voucher database

`db/gyftr_vouchers.json` — 379 brands scraped from Gyftr, each with:
denominations (fixed and/or custom-range), payment-method discount
percentages (UPI, card, net banking, etc.), redemption type (online/offline/
both), and T&Cs. `db/voucher_lookup.py` matches a merchant name to a voucher
brand (exact → prefix → substring, with a minimum-length guard to stop short
brand names like "W" from fuzzy-matching everything) and computes the
effective price for a given payment method.

### Hardening / reliability work (post-Layer-2)

- SQLite disk cache (`db/cache.py`) for SerpAPI search results, 24h TTL —
  avoids re-querying SerpAPI for repeated/recent searches.
- Top-level exception handling in `run()` — prints a friendly error instead
  of a raw traceback on any unexpected failure.
- Case-insensitive merchant dedup in Step 5 (was treating "AJIO.com" and
  "ajio.com" as different merchants).
- Word-boundary submodel-keyword matching in the matcher (was substring —
  "pro" matched inside "professional").
- Mixed fixed/custom denomination handling in voucher math (some vouchers
  have both fixed-value and custom-range products; fixed ones take
  priority since they're real purchase options).

## 2. File structure

```
main.py                      Entry point — all 5 pipeline steps + run()
engine/
  matcher.py                 Product matching: token similarity, submodel/
                              color/storage/size conflict detection,
                              foreign-marketplace filtering
extractor/
  zyte_client.py             Zyte Extract API wrapper + all per-site
                              fallback chains (Myntra/Nykaa/AJIO/Amazon/
                              amzn.in short links)
  discovery.py                SerpAPI Google Shopping discovery, immersive
                              seller resolution, search query builder,
                              out-of-stock/foreign-domain/brand-conflict
                              filtering
  shopping.py                 ⚠️ LEGACY / UNUSED. Earlier Google-Shopping-
                              scraping + direct-merchant-search approach
                              (pre-SerpAPI). Not imported anywhere. Kept
                              for reference only — safe to delete.
db/
  cache.py                    SQLite cache for SerpAPI results (24h TTL)
  voucher_lookup.py           Gyftr voucher matching + effective-price math
  gyftr_vouchers.json         Voucher database (379 brands), used at runtime
  models.py                   ⚠️ LEGACY / UNUSED. Old SQLite schema for
                              caching price comparisons (checkout_assistant.db).
                              Not imported by main.py. Superseded by cache.py.
  queries.py                  ⚠️ LEGACY / UNUSED. Query helpers for models.py's
                              schema. Same status — dead code.
scripts/
  scrape_gyftr.py              One-off scraper that built gyftr_vouchers.json
  gyftr_to_csv.py / _v2.py     One-off export scripts (JSON → CSV) used for
                              manually inspecting the voucher data during
                              Layer 2 development. Not part of the runtime
                              pipeline.
checkout_assistant.db         ⚠️ LEGACY. SQLite db created by db/models.py.
                              Unused by the current pipeline.
gyftr_vouchers.csv /
gyftr_vouchers_v2.csv         CSV exports of the voucher DB (debugging aid,
                              not read by any code).
test_results.csv              Manual test log from early Layer 1 development.
README.md                     ⚠️ STALE. Describes the pre-SerpAPI architecture
                              (extractor/shopping.py based). Does not reflect
                              the current pipeline — needs a rewrite.
SUMMARY.md                     Likely also stale; not reviewed/updated this
                              session — check before trusting it.
.env / .env.example            ZYTE_API_KEY, SERPAPI_KEY
```

**Active runtime dependency graph** (what actually executes when you run
`main.py`):
`main.py` → `db/cache.py`, `db/voucher_lookup.py` (+`gyftr_vouchers.json`),
`engine/matcher.py`, `extractor/discovery.py`, `extractor/zyte_client.py`.
Everything marked ⚠️ above is not on this path.

## 3. Last commit / pending

Last commit: `fafab2c` — "Resolve amzn.in short links to canonical Amazon
URL before extraction". Pushed to `origin/main`. Working tree is otherwise
clean except two long-standing untracked files that have never been staged
or committed in any session:
- `gyftr_vouchers.csv`
- `scripts/gyftr_to_csv.py`

These are debugging/export artifacts, not required by the runtime pipeline.
No action taken on them — flagging for whoever picks this up to decide
whether to commit, gitignore, or delete.

Regression-tested and confirmed working as of the last commit:
- boAt Airdopes 141 (text query) — cache hit, outlier filter, vouchers OK.
- Myntra Nike sneakers URL — full extraction, matching, vouchers OK.
- Ray-Ban Meta Wayfarer Gen 2 (text query) — outlier filter correctly drops
  a mismatched non-Meta listing.
- Lakme CC Cream (text query) — Step 4b size comparison correctly compares
  9g vs 20g variants.
- `amzn.in` short link — now extracts successfully (previously failed
  outright).

## 4. What's next: web interface

Planned: wrap the existing `main.py` pipeline in a **FastAPI** backend with
a simple **HTML frontend** (no SPA framework planned/discussed yet — keep it
plain unless told otherwise). Not started. Likely shape, to confirm with
the user before building:
- A POST endpoint that takes a URL or text query and runs the same 5(+1)
  steps, returning structured JSON instead of console prints — meaning the
  step functions in `main.py` will need to separate "compute" from "print"
  (currently they're interleaved), or the API layer wraps `run()` and
  parses captured output, or (cleaner) refactor each step to return data and
  have a separate console-formatting layer for the CLI. **This refactor
  question is unresolved — surface it before writing API code.**
- A minimal HTML page with an input box and a results table/voucher list.
- Caching (`db/cache.py`) and voucher lookups stay as-is; only the
  presentation layer changes.

## 5. Known issues / pending items

- **Text-query mode has no real identity verification.** The matcher
  (`engine/matcher.py`) only runs when there's a source product from a URL.
  For text queries, the price-outlier filter catches the worst mismatches
  (wrong product entirely, wrong size) but there's no brand/model
  verification — a same-brand-different-model result could still rank
  highly if its price happens to fall within the outlier threshold.
- **`_KNOWN_BRANDS` in `main.py` is a small hardcoded list.** Brands not in
  it won't be inferred from product name/brand metadata, which weakens
  brand-conflict filtering (`_seller_url_conflicts`) and voucher matching
  for any product outside that list.
- **Only `amzn.in` short links are handled.** Other shorteners (e.g.
  Flipkart's `fkrt.co`, generic `bit.ly` links) aren't resolved and will
  likely fail extraction the same way `amzn.in` did before the fix.
- **No automated test suite.** All verification so far has been manual
  `main.py` runs against a fixed set of test products (boAt Airdopes 141,
  Myntra Nike sneakers, Ray-Ban Meta Wayfarer, Lakme CC Cream, Qubo dashcam,
  amzn.in short link). Worth writing real tests before the API refactor,
  since web-layer changes will be much riskier to verify by hand.
- **`README.md` is stale** and describes an earlier architecture
  (`extractor/shopping.py`-based discovery, SQLite caching via
  `db/models.py`) that's been replaced by SerpAPI + `db/cache.py`. Should be
  rewritten to match the current pipeline before/alongside the web UI work.
- **Legacy files not yet cleaned up**: `db/models.py`, `db/queries.py`,
  `extractor/shopping.py`, `checkout_assistant.db`, `gyftr_vouchers.csv`,
  `gyftr_vouchers_v2.csv`, `test_results.csv`. None are imported by the
  active pipeline; safe candidates for deletion once confirmed unneeded.
- **Step 5 voucher eligibility** is gated on `match_type in ("Exact Match",
  "Listed")` — Similar Match results never get voucher suggestions, by
  design (since they're a different variant, not confirmed to be the exact
  product). Worth keeping in mind if API consumers expect vouchers on every
  result.
