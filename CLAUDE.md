# Dealo — Project Instructions

Read this before doing anything. It replaces HANDOFF.md, which described the pre-refactor architecture and is now deleted/stale. Everything below was verified against the actual codebase on 2026-07-07.

## What this is

Dealo is a pre-checkout purchase optimization engine for Indian e-commerce. Input: product URL or text query. Output: the smartest way to buy — one Recommended Route plus up to 3 alternatives. It is NOT a cashback platform, coupon site, or credit card business. It generates **routes, not discounts**.

## Non-negotiable product rules

1. **Trust is the core product value.** A wrong result is worse than no result. Prefer targeted, high-confidence fixes over broad pattern matchers. Regex-based soft-signal parsing hits diminishing returns fast — know when to stop patching.
2. **Recommended Route = lowest final cost, always card-free, executable by anyone.** Card savings never affect ranking.
3. **Alternatives (max 3)** appear only behind "Recommended route not working for you?". No "Fastest Route" or "Maximum Savings" buckets.
4. **L3 cards: direct cashback only** (never points/miles). Show the single best card by **actual saving after cap**, not headline rate. SBI Cashback beats BOB Cashback on ties.
5. **Never expose backend mechanics in user-facing copy** — no layer names, stacking math, or reward-point arithmetic. Users see: final cost, savings, what to do. Understandable in under 10 seconds.
6. **Gyftr's UPI discount rate consistently beats its credit-card rate** — this is the core recommendation signal; voucher deals are computed at UPI rates.
7. Users may not have premium credit cards. Do not assume they do.

## Working style (follow strictly)

- **Plan before code.** Explain decisions and get sign-off before writing anything. Challenge assumptions that look wrong — the user wants pushback, not agreement.
- **One step at a time**, with a checkpoint after each step to verify it worked before proceeding.
- The user is not a terminal expert. Give exact, copy-pasteable commands with plain-English explanations of what they do. Ask to see complete terminal output before assessing whether something worked.
- **Concise responses.** No multi-step over-explanation, no sycophancy.
- Commit all progress to git before starting a new work stream.
- Python is `/usr/local/bin/python3.11` (or `pip3.11`). Never bare `python3` — that's macOS system 3.9.
- Run the server from the repo root (`~/checkout-assistant`) — `whatsapp/webhook.py` uses a relative path to `db/whatsapp_sessions.db`.

## Current state (code-verified)

**L1 — price discovery: complete.** `pipeline.py` is the pure-compute layer (the old main.py print-refactor is done). Zyte extraction with per-site fallbacks (Amazon browserHtml, amzn.in resolution, Myntra /buy retry + slug + browser-render price recovery, Nykaa/AJIO slugs) in `extractor/zyte_client.py`. SerpAPI discovery + immersive seller resolution in `extractor/discovery.py`, 24h SQLite cache in `db/cache.py`. Matching in `engine/matcher.py`: brand gate → refurb/submodel/color/storage/size conflict detection → noise-stripped token subset/Jaccard. Trusted-merchant whitelist (manual list + all Gyftr brands), price-outlier filter (< 40% of median), accessory/model-number relevance filter, per-merchant dedup, priority-merchant sort.

**L2 — Gyftr vouchers: complete.** 379 brands in `db/gyftr_master.json`. `db/voucher_lookup.py` does exact→prefix→substring brand matching (short-name guard, reseller exclusion), greedy denomination fill respecting `stack_limit` / `value_cap` / `purchase_cap_per_txn`, custom-amount vouchers, UPI vs card discount rates. Category restrictions enforced via `engine/category_classifier.py` against `redemption_restrictions`.

**L3 — cards: built, has known correctness gaps (see bugs).** `db/cashback_cards.json`: SBI Cashback, Flipkart Axis, BOB Cashback. `db/card_lookup.py` picks best card by capped saving; surfaced as `card_fomo` on the recommended route only.

**Route builder** (`pipeline._build_routes`): merges results + vouchers, final_cost = voucher UPI effective price or listed price, sorts, dedups on (merchant, final_cost), returns `{recommended, alternatives[≤3]}`.

**Web UI: functional.** `api.py` (FastAPI: `/`, `POST /search`, `/health`) + `templates/index.html` (single file, vanilla JS). Product identity box, savings bar, journey visualization, how-to steps with cleaned redemption instructions, card FOMO row with embedded base64 card images, alternatives toggle, unverified-sellers warning. Cuelinks affiliate wrapping on merchant links (`linksredirect.com/?cid=297179`), deliberately NOT on Gyftr voucher links. Not yet deployed (target: Railway or Render).

**WhatsApp: end-to-end wired, one display bug.** `whatsapp/webhook.py` (Meta Graph v20.0, verify + receive, async pipeline dispatch, "See other routes" button), `classifier.py` (url / product_name / unparseable triage with noise-phrase list), `session_store.py` (SQLite, 10-min sliding TTL per phone), `formatter.py`. Access token is a 24h dev token needing daily regeneration; ngrok URL changes on restart and must be re-registered in Meta.

## Known bugs and discrepancies (fix before trusting output)

1. **`whatsapp/formatter.py` key mismatch — live bug.** Reads `voucher.brand` / `best_discount` / `recommended_denomination` / `gyftr_url`; pipeline vouchers expose `merchant` / `upi.pct` / `upi.voucher_amount` / `voucher_url`. WhatsApp renders "Buy ₹0 voucher at 0% off" with no link. Fix formatter to the pipeline schema (web UI in index.html shows the correct keys).
2. **`card_lookup.py` ignores `earns_on_gyftr`.** Flipkart Axis (`earns_on_gyftr: false`) can be recommended at its 7.5% Myntra override on a Gyftr-voucher route where it earns nothing. When the route includes a voucher, only cards with `earns_on_gyftr: true` should qualify, at `gyftr_rate`.
3. **No card FOMO display threshold.** Intended rule (₹200 or 3% minimum saving) is not implemented; any saving > ₹0 shows.
4. **Cap periods not normalized** — monthly vs quarterly `cap_amount` compared raw when selecting the best card.
5. **Dead code**: unused inner `_headers()` in both send functions in `whatsapp/webhook.py`.
6. **Text-query mode identity verification — largely fixed 2026-07-12/13.** `search_service.py`'s `_matches_required_tokens` now rejects "/"-bundled multi-SKU listings (e.g. a seller title like "AirPods Pro 3/AirPods 3" no longer passes a "Pro 3" search) and is ordinal-aware (a query's bare "2" now also matches a title's "2nd" — previously genuine "2nd Generation" listings were silently rejected while sloppy clones repeating a bare "2" passed through). `_filter_trusted_only` now runs at the picker stage (`_filter_and_group_candidates`), not just at route-building. Residual gap: a segment that contains all required tokens plus an extra unstripped distinguishing word can still slip through (pre-existing limitation of the whole-title check, not introduced by this fix) — real submodel-conflict detection (what the old, now-deleted `engine/matcher.py` used to do) would be needed to close this fully.
7. **Marketplace-attributed clones — largely mitigated 2026-07-13 via price anchor.** Google Shopping attributes third-party marketplace listings to the platform ("Flipkart"), not the actual seller, so a merchant-whitelist check alone can't catch a clone sold *through* a trusted platform. Fix: `_filter_and_group_candidates` now anchors the price-outlier check on the highest price quoted by any of the small `PRIORITY_MERCHANTS` set (Croma, Vijay Sales, Reliance Digital, Tata CLiQ, Flipkart, Amazon) when one is present, instead of the survivor pool's own median — verified this drops all 39 clone/junk listings for "Apple Airpods Pro 2" down to the single genuine Reliance Digital ₹18,900 listing. Residual gap: if a query has **no** priority-merchant listing at all (only JioMart/Zepto/Apple/Myntra/Nykaa/AJIO/BigBasket/Pepperfry/Lenskart), there's no anchor and the weaker median-based filter is all that applies — don't attempt to close this with title-keyword heuristics ("Oem", "king edition", etc.), that's the kind of ad hoc special-casing rule #1 warns against.
8. `_KNOWN_BRANDS` (pipeline.py) and `_BRAND_SLUGS` (discovery.py) are small hardcoded lists — brands outside them weaken brand inference and conflict filtering.
9. Only `amzn.in` short links resolve; `fkrt.co` / `bit.ly` will fail extraction.
10. WhatsApp links are not Cuelinks-wrapped (web links are). Decide whether that's intentional before production.
11. No automated tests. Regression set is manual: boAt Airdopes 141, Myntra Nike sneakers URL, Ray-Ban Meta Wayfarer Gen 2, Lakme CC Cream, amzn.in short link.

## Live price-on-paste vendor coverage (for Karan — flagged 2026-07-22)

Bug: pasting a merchant link only ever searched Google's Shopping index by title/slug — the real price on the page you're looking at could be missing, stale, or simply never offered as a picker option, so the "Recommended Route" could end up pricier than the page you pasted (hit in testing: an Amazon link at ₹336 recommended Myntra at ₹500). Root cause: the react migration deleted the old Zyte-based live-page scraper and nothing replaced it. Fixed for two vendors so far, in `src/services/search_service.py` (`_fetch_url_page` / `_extract_amazon_price` / `_extract_jsonld_price`) — each pasted link's real price, when readable, is read once (same request that already fetches the page title) and pinned so it can never lose to a stale index entry.

**Live now, hand-verified against real product pages, not just "a request succeeded":**
- **Amazon** (`amazon.in`/`amazon.com`) — hand-rolled regex on the page's own buybox markup (Amazon doesn't expose a standard price tag). Confirmed the matched element's own CSS class is literally `priceToPay`, not the struck-through MRP.
- **Myntra** (`myntra.com`) — reads the page's own schema.org `Product` → `offers.price` structured data (the same block search engines use for rich results — a standard field, not custom scraping). Confirmed the value matched the page's own `discountedPrice` field (₹1,289), not its `mrp` field (₹1,499).

**Scoped but not built — needs your call: Tata CLiQ.** Its product pages load fine (200 OK, not blocked), but they're an empty JS shell — the price only appears after the page runs its own JavaScript, which a plain page fetch can't do. This is a *free* fix (no paid service, just more engineering): run a real but invisible browser on our own server (e.g. Playwright — open-source, no subscription) to open the page, let it load, and read the price the way a person would. Tradeoffs: meaningfully more code than the regex/JSON-LD approach above, slower per lookup (a few seconds instead of well under one), and a bigger server footprint (an actual browser has to run in the background for every one of these lookups). Worth doing, but bigger than what's shipped so far — didn't want to build it without your sign-off given the footprint/deploy impact.

**Can't be fixed for free — needs a real decision, not more engineering time:**
- **Flipkart** — its product pages specifically return 403 (forbidden) to a plain fetch, even though its homepage loads fine.
- **Nykaa, AJIO, Croma** — block every page tested, including their homepages.

All three/four look like IP- or network-level bot detection (the kind that checks whether a request is coming from a real residential internet connection vs. a data-center server), not something a better user-agent string or extra headers reliably gets around. The only real fix is routing requests through a paid proxy/scraping service — which is exactly the category of tool the old, deleted Zyte integration was. That's a budget decision, not a code one — flagging it here rather than silently deciding either way.

## Pending work

- Fix bugs 1–4 above (1 and 2 are user-facing correctness — highest priority).
- Deploy web interface (Railway or Render); permanent WhatsApp access token at that point.
- Cuelinks approval pending (publisher 256146, cid 297179) — links are pre-wired.
- `refresh_gyftr.py` staleness checker for `gyftr_master.json`.
- L1 matching fine-tune (dedicated replanning session).
- Gyftr partnership: ongoing meetings with Simran / Anjali (SVP); demo-led framing since Dealo is pre-revenue.

## Environment

- Repo: `github.com/kejriwalmedhansh-bit/checkout-assistant` (private), branch `main`.
- `.env` in repo root: `ZYTE_API_KEY`, `SERPAPI_KEY`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN=dealo_webhook_2026`. Never commit it, never print its values.
- Run: `uvicorn api:app --host 0.0.0.0 --port 8000` from repo root; `ngrok http 8000` for WhatsApp.
- SerpAPI: $25/mo, 1,000 credits — the 24h cache exists to protect this budget; don't bypass it casually.
