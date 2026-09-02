"""Builds db/domain_brand_map.json from audits/brand_website_matching.csv.

That CSV (577 rows, built during the 2026-08-08 merchant-trust audit) is the
real brand -> official-website mapping Dealo already has, but until now it was
only a spreadsheet — nothing in the running app read it. This script promotes
it into data the backend loads at runtime, for the Chrome extension's
checkout-page voucher check (`GET /voucher-check`).

Only "Verified"/"High" confidence rows are included — the CSV's own
"Medium"/"Low"/"Uncertain" rows are unconfirmed pattern guesses, and per
Dealo's #1 rule ("a wrong result is worse than no result") those shouldn't
silently drive an automatic match yet.

When several rows guess the same domain (common: brand-variant SKUs like
"Amazon" / "Amazon Fresh" / "Amazon Prime Membership" all guessing
amazon.in), the shortest brand name wins — it's reliably the plain/generic
listing rather than a narrower variant, the same tie-break already used by
`_brand_matching.find_best_match` elsewhere in this codebase.

Re-run after `audits/brand_website_matching.csv` changes:
    python3.11 scripts/build_domain_brand_map.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "audits" / "brand_website_matching.csv"
OUT_PATH = REPO_ROOT / "data" / "domain_brand_map.json"

_TRUSTED_CONFIDENCE = {"Verified", "High"}


def _clean_domain(raw: str) -> str:
    site = raw.strip().lower()
    site = re.sub(r"^https?://", "", site)
    site = site.split("/")[0]
    if site.startswith("www."):
        site = site[4:]
    return site


def build() -> dict[str, str]:
    domain_map: dict[str, str] = {}
    with CSV_PATH.open(newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        if row["Confidence"] not in _TRUSTED_CONFIDENCE:
            continue
        raw_site = row["Guessed Official Website"].strip()
        if not raw_site:
            continue
        domain = _clean_domain(raw_site)
        brand = row["Brand Name"].strip()
        if not domain or not brand:
            continue
        existing = domain_map.get(domain)
        if existing is None or len(brand) < len(existing):
            domain_map[domain] = brand

    return domain_map


def main() -> None:
    domain_map = build()
    OUT_PATH.write_text(json.dumps(domain_map, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {len(domain_map)} domain -> brand entries to {OUT_PATH}")


if __name__ == "__main__":
    main()
