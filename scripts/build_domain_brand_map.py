"""Builds data/domain_brand_map.json — which brand's voucher belongs to which shop.

The Chrome extension can tell it is on a checkout; this map is how the backend
knows which brand that checkout belongs to (`GET /voucher-check`).

Two lists feed it, in order of authority:

  1. audits/brand_domains_confirmed.csv — read out of the sellers' own
     voucher terms by scripts/extract_brand_domains.py, with every pairing
     that could put a wrong offer in front of a shopper checked by hand
     (2026-09-10; the answers are kept in audits/brand_domain_overrides.json).
  2. audits/brand_website_matching.csv — the 2026-08-08 merchant-trust audit,
     "Verified"/"High" rows only. It still knows shops the terms never name
     (Domino's, Blinkit, Apollo Pharmacy), so it fills in any website the
     first list lacks. Where both name a website, the first list wins.

Then two filters:

  - A brand whose vouchers only work in a physical store is left out, by the
    same rule extract_brand_domains.py uses. The older audit mapped Reliance
    Digital, Vijay Sales and Manyavar to their websites, which would have
    had Dealo wake up at an online checkout for a voucher the shop's tills
    accept and its website does not.
  - audits/brand_domain_corrections.json removes and adds by hand, each with
    its reason: misspellings in the sellers' own terms, addresses that do
    not exist.

When several brands share a website ("Amazon", "Amazon Fresh", "Amazon Prime
Membership" all on amazon.in), the shortest name wins — reliably the plain
listing rather than a narrower variant, the same tie-break
`_brand_matching.find_best_match` uses.

Re-run after any of those files change:
    python3.11 scripts/build_domain_brand_map.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_brand_domains import IN_STORE_NAME, NOT_A_SHOP, OFFLINE_ONLY, norm  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDITS = REPO_ROOT / "audits"
CONFIRMED_CSV = AUDITS / "brand_domains_confirmed.csv"
OLDER_CSV = AUDITS / "brand_website_matching.csv"
CORRECTIONS = AUDITS / "brand_domain_corrections.json"
OUT_PATH = REPO_ROOT / "data" / "domain_brand_map.json"

_TRUSTED_CONFIDENCE = {"Verified", "High"}


def _clean_domain(raw: str) -> str:
    site = raw.strip().lower()
    site = re.sub(r"^https?://", "", site)
    site = site.split("/")[0]
    if site.startswith("www."):
        site = site[4:]
    return site


def _store_only_brands() -> set[str]:
    """Brand names (normalised) whose every listing, on every seller, is
    redeemable only in a physical store."""
    kinds: dict[str, set[str]] = {}
    for source in ("gyftr", "maximize", "buyhatke"):
        path = REPO_ROOT / "data" / f"{source}_master.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for record in (data if isinstance(data, list) else list(data.values())):
            seen = kinds.setdefault(norm(record.get("brand_name")), set())
            for product in record.get("products", []):
                kind = str(product.get("redemption_type") or "").strip().lower()
                if kind:
                    seen.add(kind)
    return {name for name, seen in kinds.items() if seen and seen <= OFFLINE_ONLY}


def _add(domain_map: dict[str, str], domain: str, brand: str) -> None:
    existing = domain_map.get(domain)
    if existing is None or len(brand) < len(existing):
        domain_map[domain] = brand


def build() -> tuple[dict[str, str], dict[str, int]]:
    store_only = _store_only_brands()
    counts = {"confirmed": 0, "older": 0, "store_only": 0, "removed": 0, "added": 0}

    def usable(domain: str, brand: str) -> bool:
        if not domain or not brand or domain in NOT_A_SHOP:
            return False
        if IN_STORE_NAME.search(brand) or norm(brand) in store_only:
            counts["store_only"] += 1
            return False
        return True

    domain_map: dict[str, str] = {}
    with CONFIRMED_CSV.open(newline="") as f:
        for row in csv.DictReader(f):
            domain, brand = _clean_domain(row["domain"]), row["brand"].strip()
            if usable(domain, brand):
                _add(domain_map, domain, brand)
    counts["confirmed"] = len(domain_map)

    older: dict[str, str] = {}
    with OLDER_CSV.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["Confidence"] not in _TRUSTED_CONFIDENCE:
                continue
            domain = _clean_domain(row["Guessed Official Website"])
            brand = row["Brand Name"].strip()
            if domain not in domain_map and usable(domain, brand):
                _add(older, domain, brand)
    domain_map.update(older)
    counts["older"] = len(older)

    corrections = json.loads(CORRECTIONS.read_text())
    for fix in corrections.get("remove", []):
        if domain_map.pop(_clean_domain(fix["domain"]), None) is not None:
            counts["removed"] += 1
    for fix in corrections.get("add", []):
        domain_map[_clean_domain(fix["domain"])] = fix["brand"]
        counts["added"] += 1

    return domain_map, counts


def main() -> None:
    domain_map, counts = build()
    OUT_PATH.write_text(json.dumps(domain_map, indent=2, sort_keys=True) + "\n")
    print(
        f"Wrote {len(domain_map)} websites to {OUT_PATH.relative_to(REPO_ROOT)}: "
        f"{counts['confirmed']} from the confirmed list, {counts['older']} more from the older audit, "
        f"{counts['store_only']} store-only rows left out, "
        f"{counts['removed']} removed and {counts['added']} added by hand."
    )


if __name__ == "__main__":
    main()
