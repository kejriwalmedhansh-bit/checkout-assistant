# Dealo (Checkout Assistant)

Pre-checkout purchase optimization engine for Indian e-commerce. Give it a product URL or a text query; it answers **"What's the smartest way to buy this right now?"** by combining cross-merchant price discovery, Gyftr gift-voucher stacking, and cashback card recommendations into ranked purchase routes.

The engine returns one **Recommended Route** (lowest final cost, always executable without any credit card) plus up to 3 **Alternative Routes**. Users see final cost, savings, and what to do — never the backend math.

## Architecture

Three optimization layers feed a route builder, served through two interfaces.

```
Input (URL or text query)
        │
  pipeline.py — run_pipeline()          pure compute, no printing
        │
  ┌─ L1: Price discovery ──────────────────────────────────┐
  │  step1_extract        Zyte Extract API + per-site      │
  │                       fallbacks (extractor/zyte_client) │
  │  step2_discover_*     SerpAPI Google Shopping           │
  │                       (extractor/discovery, 24h SQLite  │
  │                       cache in db/cache.py)             │
  │                       + relevance/trusted/outlier       │
  │                       filters, matcher (engine/matcher) │
  │  step3_resolve        Direct seller URLs via SerpAPI    │
  │                       immersive API; drops OOS/foreign/ │
  │                       brand-conflicting sellers         │
  │  step4 / step4b       Ranked table + unit-price size    │
  │                       comparison                        │
  └──────────────────────────────────────────────────────────┘
  ┌─ L2: Gyftr vouchers ───────────────────────────────────┐
  │  step5_vouchers       Matches merchants to 379 Gyftr    │
  │                       brands (db/gyftr_master.json via  │
  │                       db/voucher_lookup.py).            │
  │                       Denomination-aware greedy fill,   │
  │                       stack limits, per-txn caps,       │
  │                       category-restriction filtering    │
  │                       (engine/category_classifier.py)   │
  └──────────────────────────────────────────────────────────┘
  ┌─ L3: Cashback cards ───────────────────────────────────┐
  │  _build_routes        Best single card by actual saving │
  │                       after cap (db/card_lookup.py +    │
  │                       db/cashback_cards.json), shown as │
  │                       a "card FOMO" row on the          │
  │                       recommended route only            │
  └──────────────────────────────────────────────────────────┘
        │
  routes: {recommended, alternatives[≤3]}
        │
   ├── Web UI      api.py (FastAPI) + templates/index.html
   └── WhatsApp    whatsapp/ (Meta Cloud API webhook)
```

### Route rules

- Recommended Route = lowest `final_cost` (voucher-discounted UPI price when a voucher exists, otherwise listed price). Always card-free.
- Card savings never affect ranking; they appear only as an optional extra-savings row.
- Similar Match results never receive voucher suggestions — vouchers apply only to Exact Match / Listed results.
- Routes identical in merchant + final cost are deduplicated.

## Repository structure

```
api.py                      FastAPI app: /  /search  /health, mounts WhatsApp router
pipeline.py                 Compute layer — all pipeline steps + run_pipeline()
templates/index.html        Single-file web frontend (vanilla JS, no framework)
engine/
  matcher.py                Product matching: brand gate, refurb/submodel/color/
                            storage/size conflict detection, token similarity,
                            subset matching, foreign-marketplace filter
  category_classifier.py    Keyword product categorization + voucher
                            category-restriction check
extractor/
  zyte_client.py            Zyte Extract wrapper + per-site fallback chains
                            (Amazon browserHtml, amzn.in resolution, Myntra
                            /buy retry + slug + browser price, Nykaa/AJIO slugs)
  discovery.py              SerpAPI Google Shopping + immersive seller
                            resolution + search query builder + seller filters
db/
  cache.py                  SQLite cache for SerpAPI results (cache.db, 24h TTL)
  voucher_lookup.py         Gyftr brand matching + effective-price math
  gyftr_master.json         379-brand Gyftr voucher database
  card_lookup.py            L3 card selection (rate, cap, best card)
  cashback_cards.json       Card definitions: SBI Cashback, Flipkart Axis,
                            BOB Cashback
whatsapp/
  webhook.py                Meta Cloud API webhook (verify + receive),
                            async pipeline dispatch, alternatives button
  classifier.py             Input triage: url / product_name / unparseable
  session_store.py          SQLite-backed sessions, 10-min sliding TTL per phone
  formatter.py              WhatsApp message formatting
.env                        API keys and WhatsApp credentials (never commit)
```

## Setup

Requires Python 3.11 (`/usr/local/bin/python3.11` on the dev machine — the system `python3` is 3.9 and will not work).

```bash
pip3.11 install fastapi uvicorn jinja2 httpx requests beautifulsoup4 python-dotenv pydantic
```

`.env` in the repo root:

```
ZYTE_API_KEY=...
SERPAPI_KEY=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...        # 24h dev token; regenerate daily until production
WHATSAPP_VERIFY_TOKEN=dealo_webhook_2026
```

## Running

```bash
cd ~/checkout-assistant
uvicorn api:app --host 0.0.0.0 --port 8000
```

- Web UI: http://localhost:8000
- API: `POST /search` with `{"query": "<url or product name>"}` → full pipeline JSON
- WhatsApp: expose the webhook with `ngrok http 8000`, then point the Meta app's webhook to `<ngrok-url>/webhook` (the ngrok URL changes on every restart and must be re-registered).

Start the server from the repo root — `whatsapp/webhook.py` opens `db/whatsapp_sessions.db` via a relative path.

## External services

| Service | Use | Notes |
|---|---|---|
| Zyte Extract API | Source-product extraction from URLs | Per-site fallback chains in `zyte_client.py` |
| SerpAPI | Google Shopping discovery + seller resolution | $25/mo, 1,000 credits; 24h cache reduces spend |
| Gyftr public API | Voucher DB source (`api.gyftr.com/gyftrapi/api`) | No auth; scraped into `gyftr_master.json` |
| Meta Cloud API | WhatsApp messaging | Graph API v20.0 |
| Cuelinks | Affiliate link wrapping (web UI only) | `cid=297179`; approval pending. Gyftr "Buy voucher" links intentionally not wrapped |

## Known issues

Verified against the code as of 2026-07-07:

1. **WhatsApp voucher block renders empty values.** `whatsapp/formatter.py` reads `voucher.brand` / `best_discount` / `recommended_denomination` / `gyftr_url`, but pipeline voucher objects expose `merchant` / `upi.pct` / `upi.voucher_amount` / `voucher_url`. WhatsApp users with a voucher route see "Buy ₹0 voucher at 0% off" and no link. Final cost is unaffected. The web UI uses the correct keys.
2. **L3 ignores `earns_on_gyftr`.** `card_lookup.py` never reads the field, so a card that doesn't earn on Gyftr purchases (Flipkart Axis) can be recommended on a Gyftr-voucher route at its retail-merchant override rate.
3. **Card FOMO has no display threshold.** Shows for any saving > ₹0 (an intended ₹200-or-3% minimum was never implemented).
4. **Cap periods not normalized.** Monthly and quarterly `cap_amount` values are compared raw when picking the best card.
5. **Text-query mode has no identity verification.** The matcher only runs in URL mode; the price-outlier filter (drop < 40% of median) catches gross mismatches only.
6. **WhatsApp access token is a 24h dev token** — manual regeneration required; permanent token deferred to production.
7. **Only `amzn.in` short links are resolved.** `fkrt.co`, `bit.ly`, etc. will fail extraction.
8. **WhatsApp links skip Cuelinks wrapping** (web wraps merchant links; WhatsApp sends raw URLs).
9. **Dead code** in `whatsapp/webhook.py`: unused inner `_headers()` definitions inside both send functions.
10. **No automated tests.** All verification is manual against a fixed product set.
11. **`refresh_gyftr.py`** voucher-staleness checker not yet built — `gyftr_master.json` is a point-in-time scrape.
