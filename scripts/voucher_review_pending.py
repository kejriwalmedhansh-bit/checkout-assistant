"""Print what the last voucher refresh added that the owner hasn't reviewed.

Run after every refresh (see VOUCHER_REFRESH.md); anything listed is held back
from shoppers until it's added to data/voucher_choice_review.json.

    /usr/local/bin/python3.11 scripts/voucher_review_pending.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.voucher_service import pending_review  # noqa: E402

pending = pending_review()
print(f"Listings filed under a reviewed name (held back): {len(pending['held_listings'])}")
for h in pending["held_listings"]:
    print(f"  {h['platform']:<9} {h['brand_name']:<24} {h['pct']}%  {h['listing']}")
print(f"\nNew voucher names at reviewed shops (not asked about yet): {len(pending['new_names'])}")
for source, name, pct in pending["new_names"]:
    print(f"  {source:<9} {name:<40} {pct}%")
