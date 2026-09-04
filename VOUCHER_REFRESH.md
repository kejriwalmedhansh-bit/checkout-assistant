# Refreshing the voucher data

The first build took most of a day. A fortnightly refresh should take about an
hour of machine time and a few minutes of yours, because almost nothing that is
expensive to produce actually changes between runs.

What moves, and how fast:

| Layer | Changes | Cost to rebuild | Do it |
|---|---|---|---|
| Rates, denominations, stock | Constantly | Gyftr minutes, BuyHatke ~30 min, Maximize ~3 h | Every run |
| The rules in the terms | Rarely | 10 reading agents | Only for listings whose terms changed |
| Maximize's brand catalogue | Barely | ~3 h of search probing | Monthly, or when a brand is missing |

The middle row is the one that used to dominate, and it is now skipped for the
~95% of listings whose terms are byte-identical to last time.

## The run

**1. Collect.** Gyftr and BuyHatke are headless and can run together; Maximize
needs a real Chrome window with the saved profile and no other Chrome open.

    .venv/bin/python scripts/scrape_voucher_terms.py --source gyftr    --workers 4
    .venv/bin/python scripts/scrape_voucher_terms.py --source buyhatke --workers 3
    .venv/bin/python scripts/scrape_voucher_terms.py --source maximize

All three resume: a listing already collected is skipped, so an interruption
costs only what was in flight. Re-run the same command after a crash.

**2. See what actually changed.**

    .venv/bin/python scripts/refresh_vouchers.py --plan

Reports new brands, changed terms, and listings that have gone. Nothing is
written. If "terms changed" is small — it usually will be — the expensive step
is small too.

**3. Queue only the changed listings for reading.**

    .venv/bin/python scripts/refresh_vouchers.py

Writes `data/rules_chunks/refresh_*.json`, 50 listings per file, and updates the
manifest. Hand three chunk files to each reading agent, pointing them at
`INSTRUCTIONS.md` for the schema and `INSTRUCTIONS_PASS2.md` for the emphasis.
Read every listing twice, independently — a measured sample showed one pass
misses a stated rule on about a third of listings, and two passes merged with
"the restriction wins" closes most of that.

**4. Rebuild.**

    .venv/bin/python scripts/merge_read_rules.py       # readings -> offers
    .venv/bin/python scripts/apply_offer_policy.py     # the product decisions
    .venv/bin/python scripts/verify_rule_quotes.py     # must report 0 unsupported
    .venv/bin/python scripts/build_service_rules.py    # what the app reads
    .venv/bin/python scripts/export_offers_csv.py      # what the Sheet reads

Then commit. The Sheet pulls `voucher_offers.csv` from GitHub, so committing is
the upload.

**5. Monthly only.** Rebuild Maximize's catalogue, then collect anything new:

    .venv/bin/python scripts/harvest_maximize_catalog_v2.py
    .venv/bin/python scripts/scrape_voucher_terms.py --source maximize

## Rules that hold across runs

- A rule Dealo states must carry the seller's own sentence. `verify_rule_quotes.py`
  is the gate; it must report zero unsupported before anything ships.
- Where the platform's summary box and the brand's terms disagree, the more
  restrictive wins.
- Where a rule differs online and in store, store the online answer — Dealo's
  shoppers are buying online.
- Cashback is not a saving, and nothing out of stock is recommended.
- A listing publishing another merchant's terms is hidden, not corrected.

## Known cost

Maximize is the slow one: a real Chrome window, one brand at a time, because the
per-payment-method rates only appear after each method is clicked. That is ~3
hours for 410 listings and cannot be parallelised — the profile opens once.

Its own page calls a JSON endpoint (`savemax.maximize.money/api/savemax/giftcard/
details-max-coins`). If that serves the same per-method rates, the whole Maximize
collection drops from hours to minutes. Not yet investigated.
