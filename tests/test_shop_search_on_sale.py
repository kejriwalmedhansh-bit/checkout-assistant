"""A shop-name search never offers a card the refresh retired or marked
out of stock (Ikea left Gyftr on 2026-11-09 and the search still showed it)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services import search_service  # noqa: E402


def test_no_retired_gyftr_card_is_offered_by_shop_search():
    master = json.loads((ROOT / "data/gyftr_master.json").read_text())
    retired = [e["brand_name"] for e in master.values()
               if e.get("products") and all(p.get("status") == "inactive" for p in e["products"])]
    assert retired
    for name in retired:
        found = search_service.search_candidates(name, exact=True, shops_only=True)
        for card in found.get("voucher_choices") or [found.get("voucher") or {}]:
            same = (card.get("brand_name") or "").lower() == name.lower()
            assert not (same and card.get("voucher_source") == "gyftr"), name
