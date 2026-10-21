"""Refresh data/hubble_catalogue.json: which brands Hubble sells us, by name.

    python scripts/build_hubble_catalogue.py            # staging
    HUBBLE_ENV=production python scripts/build_hubble_catalogue.py

Reads Hubble's own store search (docs.myhubble.money/sdk/features/custom-listing)
with our client id, so the list is exactly what our shoppers can buy. Only
names and ids are kept: prices and amount rules change often, so the server
reads those live per brand (services/hubble_service.py), never from here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import get_settings  # noqa: E402
from src.services.hubble_service import API_HOST  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "hubble_catalogue.json"


def build() -> list[dict]:
    s = get_settings()
    resp = httpx.get(
        f"{API_HOST[s.HUBBLE_ENV]}/v3/store/products/search",
        params={"pageNo": 0, "limit": 2000},
        headers={"X-CLIENT-ID": s.HUBBLE_CLIENT_ID},
        timeout=60,
    )
    resp.raise_for_status()
    brands = {}
    for section in resp.json().get("data", []):
        for p in section.get("products", []):
            vp = p.get("voucherProduct") or {}
            key = (p.get("brandKey") or "").lower()
            # Hubble lists some shops twice under one name: an "-online"
            # voucher and an "-offline" (in-store) one. Dealo shoppers buy
            # online, so the in-store ones never belong here.
            if p.get("type") == "VOUCHER" and vp.get("status") == "ACTIVE" and "offline" not in key:
                brands[p["id"]] = {"id": p["id"], "name": vp.get("title", "").strip(), "brand_key": key}
    return sorted(brands.values(), key=lambda b: b["name"].lower())


if __name__ == "__main__":
    brands = build()
    OUT.write_text(json.dumps(brands, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(brands)} brands to {OUT}")
