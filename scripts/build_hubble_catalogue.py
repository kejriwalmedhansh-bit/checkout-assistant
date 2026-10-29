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

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config import get_settings  # noqa: E402
from src.services.hubble_service import API_HOST  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


def out_path(env: str) -> Path:
    """Production and staging are different stores with different brand ids,
    so each keeps its own file (services/hubble_service.py picks by env)."""
    return DATA / ("hubble_catalogue.json" if env == "production" else "hubble_catalogue.staging.json")


def _details(client: httpx.Client, base: str, brand: dict) -> dict | None:
    resp = client.get(f"{base}/v1/store/products/voucher-product/{brand['id']}")
    if resp.status_code == 404:
        return None  # listed in search but has no product page: can't be bought
    resp.raise_for_status()
    meta = resp.json().get("voucherProductMetadata") or {}
    modes = sorted({(s.get("retailMode") or "").upper() for s in meta.get("howToUseSteps") or []} - {""})
    if not modes:
        modes = ["OFFLINE"] if "offline" in brand["brand_key"] else ["ONLINE"]
    return {**brand, "works": modes, "add_voucher_url": meta.get("addVoucherBrandPageUrl")}


def build() -> list[dict]:
    s = get_settings()
    base = API_HOST[s.HUBBLE_ENV]
    with httpx.Client(headers={"X-CLIENT-ID": s.HUBBLE_CLIENT_ID}, timeout=60) as client:
        resp = client.get(f"{base}/v3/store/products/search", params={"pageNo": 0, "limit": 2000})
        resp.raise_for_status()
        brands = {}
        for section in resp.json().get("data", []):
            for p in section.get("products", []):
                vp = p.get("voucherProduct") or {}
                if p.get("type") == "VOUCHER" and vp.get("status") == "ACTIVE":
                    brands[p["id"]] = {"id": p["id"], "name": vp.get("title", "").strip(), "brand_key": (p.get("brandKey") or "").lower()}
        with ThreadPoolExecutor(8) as pool:
            out = [b for b in pool.map(lambda b: _details(client, base, b), brands.values()) if b]
    return sorted(out, key=lambda b: (b["name"].lower(), b["brand_key"]))


if __name__ == "__main__":
    brands = build()
    OUT = out_path(get_settings().HUBBLE_ENV)
    OUT.write_text(json.dumps(brands, indent=1, ensure_ascii=False) + "\n")
    online = sum("ONLINE" in b["works"] for b in brands)
    print(f"wrote {len(brands)} vouchers to {OUT} ({online} work online, {len(brands) - online} in store only)")
