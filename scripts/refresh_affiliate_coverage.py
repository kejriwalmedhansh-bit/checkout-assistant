"""Builds data/affiliate_coverage.json — which network (Cuelinks vs INRDeals)
each brand should be affiliate-wrapped through, and why.

Only brands that already have a verified domain in data/domain_brand_map.json
are considered — those are the only ones /go can ever look up a brand for in
the first place (see domain_brand_repository.brand_for_domain), so checking
anything wider would just be dead data.

For each of those brands:
  - If only Cuelinks has it live (access_status "open"), or only INRDeals has
    it live (status "ACTIVE"), use that one.
  - If both have it live, compare their current percentage-of-sale payout
    and use whichever pays more today.
  - If neither has it live, "none" — /go's existing default (Cuelinks wrap
    regardless) is unchanged, so this is a strict improvement with no
    regression risk.

Cuelinks side is live (cuelinks_repository calls their real API with
CUELINKS_API_KEY). INRDeals side is NOT live yet — their publisher API
access was requested 2026-08-31 and is still pending approval, so this reads
a manually-exported CSV snapshot instead (data/inrdeals_snapshot_*.csv, the
newest one by filename date). Once an INRDEALS_API_KEY exists, replace
_load_inrdeals_snapshot() with a real API call the same way Cuelinks' side
works — everything downstream (matching, comparison, output shape) stays
the same.

Re-run whenever the coverage list needs refreshing (rates and live/paused
status drift over time — this is a snapshot, not a self-updating value):
    python3.11 scripts/refresh_affiliate_coverage.py
"""
from __future__ import annotations

import csv
import glob
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.repositories.cuelinks_repository import fetch_all_india_campaigns  # noqa: E402

DOMAIN_BRAND_MAP_PATH = REPO_ROOT / "data" / "domain_brand_map.json"
OUT_PATH = REPO_ROOT / "data" / "affiliate_coverage.json"

# Coincidental word-overlap false matches surfaced by hand during the
# 2026-08-31 research pass (e.g. "Credit Masterclass" fuzzy-matching the
# unrelated US "MasterClass" campaign on the shared word "masterclass").
# Keyed by the normalized campaign name to exclude from fuzzy matching.
BAD_CUELINKS_MATCHES = {
    "apollo io", "og beauty", "moms home", "audible only for dd",
    "organic mandya", "kama ayurveda", "sbi prime credit card cpl",
    "trading view only dd", "times prime coupon redemption", "hp india",
}
BAD_INRDEALS_MATCHES = {"royal sundaram insurance", "hdfc pixel card"}


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def _words(s: str) -> set[str]:
    return {w for w in s.split() if len(w) >= 3}


def _fuzzy_find(brand: str, catalog_by_norm: dict, bad: set[str]):
    nb = _norm(brand)
    wb = _words(nb)
    if nb in catalog_by_norm:
        return catalog_by_norm[nb][0]
    for k, items in catalog_by_norm.items():
        if k == nb or k in bad:
            continue
        wk = _words(k)
        if not wb or not wk:
            continue
        smaller, larger = (wb, wk) if len(wb) <= len(wk) else (wk, wb)
        if smaller and smaller.issubset(larger) and any(len(w) >= 4 for w in smaller):
            return items[0]
    return None


def _load_inrdeals_snapshot() -> list[dict]:
    snapshots = sorted(glob.glob(str(REPO_ROOT / "data" / "inrdeals_snapshot_*.csv")))
    if not snapshots:
        print("WARNING: no data/inrdeals_snapshot_*.csv found — INRDeals side will be empty.")
        return []
    path = snapshots[-1]
    print(f"Using INRDeals snapshot: {Path(path).name}")
    with open(path, newline="", encoding="utf-8") as f:
        return [
            {
                "name": row["Merchant"].strip(),
                "status": row["Campaign Status"].strip(),
                "payout_raw": row["Payout Structure"].strip(),
                "campaign_type": row["Campaign Type"].strip(),
            }
            for row in csv.DictReader(f)
        ]


def _pct(raw: str) -> float | None:
    m = re.search(r"([\d.]+)\s*%", raw)
    return float(m.group(1)) if m else None


def build() -> dict[str, dict]:
    with open(DOMAIN_BRAND_MAP_PATH) as f:
        brands = sorted(set(json.load(f).values()))

    print(f"Checking {len(brands)} verified-domain brands...")
    cue_campaigns = fetch_all_india_campaigns()
    if not cue_campaigns:
        raise RuntimeError(
            "Got zero Cuelinks campaigns back — check CUELINKS_API_KEY in .env "
            "before trusting this run. Refusing to overwrite an existing "
            "coverage file with empty data."
        )
    cue_by_norm: dict[str, list[dict]] = {}
    for c in cue_campaigns:
        cue_by_norm.setdefault(_norm(c["name"]), []).append(c)

    inr_merchants = _load_inrdeals_snapshot()
    inr_by_norm: dict[str, list[dict]] = {}
    for m in inr_merchants:
        inr_by_norm.setdefault(_norm(m["name"]), []).append(m)

    coverage: dict[str, dict] = {}
    counts = {"cuelinks": 0, "inrdeals": 0, "none": 0}

    for brand in brands:
        cue = _fuzzy_find(brand, cue_by_norm, BAD_CUELINKS_MATCHES)
        inr = _fuzzy_find(brand, inr_by_norm, BAD_INRDEALS_MATCHES)

        cue_live = bool(cue) and cue.get("access_status") == "open"
        inr_live = bool(inr) and inr.get("status", "").upper() == "ACTIVE"

        if cue_live and inr_live:
            cue_pct = float(cue["payout"]) if cue.get("payout_currency") == "%" else None
            inr_pct = _pct(inr["payout_raw"])
            if cue_pct is not None and inr_pct is not None and inr_pct > cue_pct:
                network = "inrdeals"
            else:
                # Ties, or a rate we can't compare (flat-amount/CPA payouts on
                # either side) default to Cuelinks — it's the network Dealo
                # already has more history and trust with.
                network = "cuelinks"
        elif inr_live:
            network = "inrdeals"
        elif cue_live:
            network = "cuelinks"
        else:
            network = "none"

        counts[network] += 1
        entry = {"network": network}
        if network == "inrdeals":
            entry["inrdeals_campaign_type"] = inr["campaign_type"].lower()
        coverage[brand] = entry

    return coverage, counts


def main() -> None:
    coverage, counts = build()
    OUT_PATH.write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(coverage)} brand entries to {OUT_PATH}")
    print(f"  cuelinks: {counts['cuelinks']}  |  inrdeals: {counts['inrdeals']}  |  none: {counts['none']}")


if __name__ == "__main__":
    main()
