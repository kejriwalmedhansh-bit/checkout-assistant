"""Check data/hubble_card_notes.json against Hubble's live terms.

Every 'can't pay for' item must quote its voucher's live terms word for word;
the app drops an item whose quote is gone (hubble_service.card_details), so a
miss here means a shop silently lost an item. Run after editing the notes,
and now and then to catch Hubble rewording:

    HUBBLE_ENV=production python3.11 scripts/check_hubble_card_notes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import get_settings  # noqa: E402
from src.services import hubble_service  # noqa: E402


def main() -> int:
    notes = {k: v for k, v in json.loads((ROOT / "data/hubble_card_notes.json").read_text()).items() if not k.startswith("_")}
    exact, _ = hubble_service._catalogue(hubble_service._catalogue_path())
    s = get_settings()
    bad = 0
    with httpx.Client(headers={"X-CLIENT-ID": s.HUBBLE_CLIENT_ID}, timeout=20) as client:
        for key, items in notes.items():
            brands = exact.get(key) or []
            if not brands:
                print(f"NO VOUCHER  {key}")
                bad += 1
                continue
            # A shop can have an online and an in-store voucher under one name
            # (Lifestyle). An item needs to be in one of them: the card drops it
            # on a copy whose terms don't say it ("not in store" on the in-store one).
            terms = []
            for brand in brands:
                resp = client.get(f"{hubble_service.API_HOST[s.HUBBLE_ENV]}/v1/store/products/voucher-product/{brand['id']}")
                terms.append((brand["works"], (resp.json().get("voucherProductMetadata") or {}).get("conditions") or []))
            for item in items:
                if not any(item["quote"] in t for _, conditions in terms for t in conditions):
                    print(f"QUOTE GONE  {key}: {item['label']} <- {item['quote']!r}")
                    bad += 1
    print(f"{len(notes)} vouchers, {sum(len(v) for v in notes.values())} items, {bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
