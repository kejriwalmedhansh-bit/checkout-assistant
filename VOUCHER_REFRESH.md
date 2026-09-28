# Refreshing the voucher data

The first build took most of a day. A refresh should take about an hour of
machine time plus the reading, and a few minutes of yours (logging in to
Maximize and allowing one download), because almost nothing that is expensive
to produce actually changes between runs.

**Work in a fresh worktree off `origin/main`**, never in whatever branch
`~/checkout-assistant` happens to be on: on 2026-09-28 that folder was on an old
branch missing four merged PRs, and a refresh built there would have undone them.

    git fetch origin && git worktree add -b data/voucher-refresh-MMDD ~/dealo-voucher-refresh origin/main

What moves, and how fast:

| Layer | Changes | Cost to rebuild | Do it |
|---|---|---|---|
| Rates, denominations, stock | Constantly | Gyftr ~20 min, BuyHatke ~30 min, Maximize ~10 min | Every run |
| The rules in the terms | Sometimes | ~15 min per 100 listings, two readings | Only for listings whose terms changed |
| Maximize's brand catalogue | Barely | ~3 h of search probing | Monthly, or when a brand is missing |

## The run

**1. Collect.** Gyftr and BuyHatke run headless and can go together. `--refresh`
re-collects everything; without it a listing already in the file is skipped.

    python3.11 scripts/scrape_voucher_terms.py --source gyftr    --workers 4 --refresh
    python3.11 scripts/scrape_voucher_terms.py --source buyhatke --workers 3 --refresh

Gyftr's full terms come from the feed its own "T&C" tab calls, not from the page
(the page-reading route saved the price table as terms for 100 brands). Every
answer is checked to be the brand asked for.

Maximize: in a **logged-in** maximize.money tab, run
`scripts/maximize_feed_collector.js` (instructions at its top), download the
file it makes, then:

    python3.11 scripts/import_maximize_feed.py ~/Downloads/maximize_feed_DATE.json --compare
    python3.11 scripts/import_maximize_feed.py ~/Downloads/maximize_feed_DATE.json

`--compare` must show nearly every card's per-method rates unchanged; on
2026-09-28 it was 349 of 355, and the other 6 were real price moves checked on
the live page.

**Check the collection before reading anything.** Any BuyHatke listing with no
amounts and no "currently unavailable" notice is a page that did not load, not a
card that has gone — re-collect those (six on 2026-09-28, Nykaa, Zomato and PVR
among them; they would otherwise have been switched off).

**2. See what actually changed.**

    python3.11 scripts/refresh_vouchers.py --plan

Terms are compared on their words, not their wrapping: Gyftr's page furniture,
BuyHatke's footer menu, Maximize's pop-up "Close" and link prefixes are all
ignored, so a listing counts as changed only when its terms did.

**3. Queue only the changed listings for reading.**

    python3.11 scripts/refresh_vouchers.py

Writes `data/rules_chunks/refresh_*.json`, 50 listings each. Copy them to
`chunk_rMMDD_NNN.json` (the next run deletes `refresh_*`), then give two chunks
to each reader: first readings to `out_rMMDD_NNN.json` from `INSTRUCTIONS.md`,
independent second readings to `out2_rMMDD_NNN.json` with `INSTRUCTIONS_PASS2.md`
added. Every quote must be verbatim; the gate checks it.

**4. Rebuild.** Stop at the first failure (`set -e`).

    python3.11 scripts/verify_rule_quotes.py              # must report 0 unsupported
    python3.11 scripts/merge_two_readings.py --tag rMMDD  # two readings, stricter wins
    python3.11 scripts/build_voucher_offers.py            # raw -> one standard record
    python3.11 scripts/merge_read_rules.py                # readings -> offers
    python3.11 scripts/apply_offer_policy.py              # the product decisions
    python3.11 scripts/build_service_rules.py             # what the app reads
    python3.11 scripts/sync_master_listings.py            # add new brands, retire gone ones
    python3.11 scripts/update_masters_from_scrape.py      # prices, amounts, stock, status
    python3.11 scripts/export_offers_csv.py               # the Sheet's current-catalogue tab
    python3.11 scripts/build_voucher_history.py           # the Sheet's History tab: every scrape, for trends

`build_service_rules.py` stops if a hand-listed wallet sentence
(`WALLET_COMBINES`) is no longer in the terms — read the new wording and update
or drop the entry; never silence it.

The Sheet reads both CSVs from GitHub with IMPORTDATA, so merging to main is
the upload. `voucher_history.csv` is rebuilt from every committed master, one
row per voucher per scrape date — nothing to append by hand.

Then run the tests (`~/checkout-assistant/.venv/bin/python -m pytest -q tests`)
and compare with the same run on `origin/main`: only differences count.

**5. Monthly only.** Rebuild Maximize's catalogue, then collect anything new:

    python3.11 scripts/harvest_maximize_catalog_v2.py

## Rules that hold across runs

- A rule Dealo states must carry the seller's own sentence. `verify_rule_quotes.py`
  is the gate; it must report zero unsupported before anything ships. A quote
  made of several verbatim sentences joined together passes only when every
  part is on the page.
- Where the platform's summary box and the brand's terms disagree, the more
  restrictive wins.
- Where a rule differs online and in store, store the online answer — Dealo's
  shoppers are buying online.
- Cashback is not a saving, and nothing out of stock is recommended.
- A listing publishing another merchant's terms is hidden, not corrected — and
  only when several unrelated listings share that document.
- Maximize cards with both fixed amounts and a Custom box keep the box: the feed
  says so outright (type "range" with a minimum and maximum).
- A listing is retired only when its platform's live catalogue no longer has it
  (Gyftr, BuyHatke) or the platform itself says it is gone (Maximize's "Gift Card
  not found"). A listing that moved address keeps its entry.
