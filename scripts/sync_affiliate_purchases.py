"""Pull affiliate sales into Mixpanel, attributed to the person who clicked.

Every shop link Dealo hands out goes through /go (src/api/routers/redirect.py),
which stamps subid = the person's device id, subid2 = click id, subid3 =
surface. Cuelinks and INRDeals report those back on each sale. This script
reads the last LOOKBACK_DAYS of sales from both and sends:

  Purchase Recorded        once per sale
  Purchase Status Changed  once per status the sale has been seen in
                           (pending -> validated -> paid, or -> rejected)

Safe to run as often as you like, with no database: every event carries a
fixed $insert_id (network + sale id [+ status]) and a fixed time (the sale
date), so Mixpanel keeps exactly one copy however many runs send it.

Runs every 3 hours from .github/workflows/sync-purchases.yml.

Needs (env or .env):
  MIXPANEL_SERVICE_ACCOUNT_USERNAME / _SECRET   required
  CUELINKS_API_KEY                              Cuelinks part (read:transactions scope)
  INRDEALS_API_TOKEN / INRDEALS_USERNAME        INRDeals part
A network with no credentials is skipped, not an error.

Run:  .venv/bin/python scripts/sync_affiliate_purchases.py [--dry-run] [--days 90]
"""
from __future__ import annotations

import argparse
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import get_settings  # noqa: E402
from src.repositories.cuelinks_repository import CUELINKS_API_BASE, _headers as cuelinks_headers  # noqa: E402
from src.services.analytics_service import build_event  # noqa: E402

LOOKBACK_DAYS = 90  # Cuelinks validation takes ~60 days; statuses keep moving until then.
IMPORT_URL = "https://api-eu.mixpanel.com/import"
IMPORT_BATCH = 1000
INRDEALS_REPORTS_URL = "https://inrdeals.com/fetch/reports"

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _first(record: dict, *keys: str):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _amount(value) -> float | None:
    try:
        return round(float(str(value).replace(",", "")), 2)
    except (TypeError, ValueError):
        return None


def _timestamp(value) -> float:
    if not value:
        return datetime.now(timezone.utc).timestamp()
    text = str(value).strip().replace("Z", "+00:00")
    for parse in (datetime.fromisoformat, lambda t: datetime.strptime(t, "%Y-%m-%d %H:%M:%S"), lambda t: datetime.strptime(t, "%d-%m-%Y")):
        try:
            dt = parse(text)
            if dt.tzinfo is None:
                # Both networks report Indian time.
                dt = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
            return dt.timestamp()
        except ValueError:
            continue
    return datetime.now(timezone.utc).timestamp()


def normalize(network: str, raw: dict) -> dict | None:
    """One network's sale record -> the fields we send. Field names are read
    from several spellings because neither network documents its response in
    full; unknown shapes are reported by the caller, not silently dropped."""
    tx_id = _first(raw, "id", "transaction_id", "txn_id", "order_id")
    if tx_id is None:
        return None
    device_id = _first(raw, "sub_id", "subid", "sub_id1", "subid1", "aff_sub", "aff_sub1")
    click_id = _first(raw, "sub_id2", "subid2", "aff_sub2")
    surface = _first(raw, "sub_id3", "subid3", "aff_sub3")
    return {
        "network": network,
        "transaction_id": str(tx_id),
        "device_id": device_id if isinstance(device_id, str) and _ID_RE.match(device_id) and device_id != "anon" else None,
        "click_id": click_id,
        "click_surface": surface,
        "shop": _first(raw, "campaign_name", "store_name", "merchant", "campaign", "advertiser") or "",
        "sale_amount": _amount(_first(raw, "sale_amount", "order_amount", "amount")),
        "commission": _amount(_first(raw, "commission", "user_commission", "payout", "earning")),
        "currency": _first(raw, "currency") or "INR",
        "status": str(_first(raw, "status") or "unknown").lower(),
        "sold_at": _timestamp(_first(raw, "transaction_date", "sale_date", "created_at", "date")),
        "status_updated_at": _first(raw, "updated_at", "status_updated_at") or "",
        "has_attribution": device_id is not None,
    }


def to_events(sale: dict) -> list[dict]:
    common = {
        "network": sale["network"],
        "transaction_id": sale["transaction_id"],
        "shop": sale["shop"],
        "sale_amount": sale["sale_amount"],
        "commission": sale["commission"],
        "currency": sale["currency"],
    }
    key = f"{sale['network']}-{sale['transaction_id']}"

    def insert_id(suffix: str) -> str:
        # Mixpanel caps $insert_id at 36 characters; a name-based uuid keeps
        # it fixed per sale without truncating long network ids.
        return uuid.uuid5(uuid.NAMESPACE_URL, f"dealo-purchase/{key}/{suffix}").hex

    recorded = build_event(
        "Purchase Recorded",
        surface="server",
        device_id=sale["device_id"],
        timestamp=sale["sold_at"],
        insert_id=insert_id("recorded"),
        properties={
            **common,
            "status": sale["status"],
            "click_id": sale["click_id"],
            "click_surface": sale["click_surface"],
        },
    )
    status = build_event(
        "Purchase Status Changed",
        surface="server",
        device_id=sale["device_id"],
        # Sale time, not update time: an update time can move on a re-sync,
        # which would defeat de-duplication.
        timestamp=sale["sold_at"],
        insert_id=insert_id(f"status/{sale['status']}"),
        properties={**common, "status": sale["status"], "status_updated_at": sale["status_updated_at"]},
    )
    events = [recorded, status]
    for event in events:
        if not sale["device_id"]:
            # Sale on a link without our ids (e.g. clicked before this
            # tracking shipped): kept, under one shared anonymous id.
            event["properties"]["distinct_id"] = "anonymous-purchase"
        event["properties"].pop("token", None)
    return events


def fetch_cuelinks(start: date, end: date, client: httpx.Client) -> list[dict]:
    if not get_settings().CUELINKS_API_KEY:
        print("[cuelinks] no CUELINKS_API_KEY — skipped")
        return []
    rows, page = [], 1
    while True:
        r = client.get(
            f"{CUELINKS_API_BASE}/transactions",
            headers=cuelinks_headers(),
            params={"start_date": start.isoformat(), "end_date": end.isoformat(), "per_page": 500, "page": page},
        )
        r.raise_for_status()
        body = r.json()
        rows += body.get("data") or []
        next_page = (body.get("meta") or {}).get("next_page")
        if not next_page:
            break
        page = next_page
    print(f"[cuelinks] {len(rows)} sale(s) {start}..{end}")
    return rows


def fetch_inrdeals(start: date, end: date, client: httpx.Client) -> list[dict]:
    settings = get_settings()
    if not (settings.INRDEALS_API_TOKEN and settings.INRDEALS_USERNAME):
        print("[inrdeals] no INRDEALS_API_TOKEN / INRDEALS_USERNAME — skipped")
        return []
    r = client.get(
        INRDEALS_REPORTS_URL,
        params={
            "token": settings.INRDEALS_API_TOKEN,
            "id": settings.INRDEALS_USERNAME,
            "startdate": start.isoformat(),
            "enddate": end.isoformat(),
        },
    )
    r.raise_for_status()
    body = r.json()
    rows = body if isinstance(body, list) else (body.get("data") or body.get("result") or body.get("transactions") or [])
    print(f"[inrdeals] {len(rows)} sale(s) {start}..{end}")
    return rows


def import_events(events: list[dict], client: httpx.Client) -> None:
    settings = get_settings()
    auth = (settings.MIXPANEL_SERVICE_ACCOUNT_USERNAME.strip(), settings.MIXPANEL_SERVICE_ACCOUNT_SECRET.strip())
    for i in range(0, len(events), IMPORT_BATCH):
        batch = events[i: i + IMPORT_BATCH]
        r = client.post(
            IMPORT_URL,
            params={"project_id": settings.MIXPANEL_PROJECT_ID, "strict": "1"},
            auth=auth,
            json=batch,
        )
        if r.status_code != 200:
            raise SystemExit(f"[mixpanel] import failed {r.status_code}: {r.text[:500]}")
        print(f"[mixpanel] imported {len(batch)} event(s): {r.text[:200]}")


def check_credentials() -> int:
    """Confirms every configured key works, sending nothing."""
    settings = get_settings()
    ok = True
    with httpx.Client(timeout=30.0) as client:
        auth = (settings.MIXPANEL_SERVICE_ACCOUNT_USERNAME.strip(), settings.MIXPANEL_SERVICE_ACCOUNT_SECRET.strip())
        for host in ("https://eu.mixpanel.com", "https://mixpanel.com"):
            r = client.get(f"{host}/api/app/me", auth=auth)
            if r.status_code == 200:
                break
        projects = ((r.json().get("results") or {}).get("projects") or {}) if r.status_code == 200 else {}
        if str(settings.MIXPANEL_PROJECT_ID) in {str(k) for k in projects}:
            print(f"[mixpanel] OK — service account can reach project {settings.MIXPANEL_PROJECT_ID}")
        else:
            ok = False
            print(f"[mixpanel] FAILED — status {r.status_code}, projects visible: {sorted(projects)}")
        if settings.CUELINKS_API_KEY:
            r = client.get(f"{CUELINKS_API_BASE}/transactions", headers=cuelinks_headers(), params={"per_page": 1})
            print(f"[cuelinks] {'OK' if r.status_code == 200 else 'FAILED'} — status {r.status_code}")
            ok = ok and r.status_code == 200
        else:
            print("[cuelinks] not configured")
        if settings.INRDEALS_API_TOKEN:
            print("[inrdeals] token present (checked on the first real sync)")
        else:
            print("[inrdeals] not configured yet")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=LOOKBACK_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print, send nothing")
    parser.add_argument("--check", action="store_true", help="Only confirm the keys work")
    args = parser.parse_args()
    if args.check:
        return check_credentials()

    settings = get_settings()
    if not args.dry_run and not (settings.MIXPANEL_SERVICE_ACCOUNT_USERNAME and settings.MIXPANEL_SERVICE_ACCOUNT_SECRET):
        print("MIXPANEL_SERVICE_ACCOUNT_USERNAME / _SECRET not set — nothing can be sent.")
        return 1

    end = date.today()
    start = end - timedelta(days=args.days)
    sales, unreadable = [], 0
    with httpx.Client(timeout=60.0) as client:
        for network, fetch in (("cuelinks", fetch_cuelinks), ("inrdeals", fetch_inrdeals)):
            for raw in fetch(start, end, client):
                sale = normalize(network, raw)
                if sale is None:
                    unreadable += 1
                    print(f"[{network}] unreadable record, keys: {sorted(raw)}")
                    continue
                if not sale["has_attribution"]:
                    print(f"[{network}] sale {sale['transaction_id']} has no Dealo sub-id; keys: {sorted(raw)}")
                sales.append(sale)

        events = [e for sale in sales for e in to_events(sale)]
        attributed = sum(1 for s in sales if s["device_id"])
        print(f"{len(sales)} sale(s), {attributed} attributed to a person, {unreadable} unreadable -> {len(events)} event(s)")
        if args.dry_run:
            for sale in sales:
                print(sale)
            return 0
        if events:
            import_events(events, client)
    return 1 if unreadable else 0


if __name__ == "__main__":
    raise SystemExit(main())
