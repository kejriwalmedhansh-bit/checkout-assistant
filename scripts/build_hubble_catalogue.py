"""Refresh data/hubble_catalogue.json: which vouchers Hubble sells us.

    python scripts/build_hubble_catalogue.py            # staging
    HUBBLE_ENV=production python scripts/build_hubble_catalogue.py

Lists every active voucher from Hubble's own store search
(docs.myhubble.money/sdk/features/custom-listing) with our client id, then
reads each one's details for two facts that rarely change:

- where it works: "ONLINE", "OFFLINE" (in store) or both, from Hubble's
  how-to-use steps. Dealo matches an online order only to an online voucher
  and an in-store order only to an in-store one.
- add_voucher_url: Hubble's link to the shop's own add-gift-card page
  (e.g. AJIO Wallet), used by the "voucher ready" screen.

Prices and amount rules change often, so the server reads those live per
brand (services/hubble_service.py), never from here.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import get_settings  # noqa: E402
from src.services import hubble_service  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


def out_path(env: str) -> Path:
    """Production and staging are different stores with different brand ids,
    so each keeps its own file (services/hubble_service.py picks by env)."""
    return DATA / ("hubble_catalogue.json" if env == "production" else "hubble_catalogue.staging.json")


def build() -> list[dict]:
    """Hubble's list today, read the same way the live server reads it
    (hubble_service.fetch_catalogue): vouchers already in the file keep their
    details, and one that left Hubble's listing but still sells is kept."""
    out = out_path(get_settings().HUBBLE_ENV)
    previous = json.loads(out.read_text()) if out.exists() else []
    return asyncio.run(hubble_service.fetch_catalogue(previous))


if __name__ == "__main__":
    brands = build()
    OUT = out_path(get_settings().HUBBLE_ENV)
    OUT.write_text(json.dumps(brands, indent=1, ensure_ascii=False) + "\n")
    online = sum("ONLINE" in b["works"] for b in brands)
    print(f"wrote {len(brands)} vouchers to {OUT} ({online} work online, {len(brands) - online} in store only)")
