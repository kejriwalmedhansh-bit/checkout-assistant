"""INRDeals postback — INRDeals calls this address the moment a sale happens.

The address pasted into INRDeals' dashboard (Postback page):

  https://<api host>/hooks/inrdeals/sale?key=<INRDEALS_POSTBACK_KEY>
    &txn={trans_id}&tag={subid1}&amount={sale_amount}&payout={payout}
    &shop={offer_name}&status={status}&date={date}

INRDeals fills in the {...} parts. `tag` is the subid /go stamped on the link
(redirect.py): the person's device id, or c_<click id> for a visitor without
one. The sale goes to Mixpanel as Purchase Recorded, with the same fixed id
scripts/sync_affiliate_purchases.py uses, so a later sync of the same sale
does not count it twice.

INRDeals calls this for new sales only; a sale later confirmed or rejected is
seen in their dashboard (or the reports API once we have a token).
"""
from __future__ import annotations

import hmac
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from ...config import get_settings
from ...services import analytics_service

router = APIRouter(tags=["affiliate"])

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CLICK_TAG_RE = re.compile(r"^c_([0-9a-f]{16})$")
_IST = timezone(timedelta(hours=5, minutes=30))


def _amount(value: str) -> float | None:
    try:
        return round(float(value.replace(",", "")), 2)
    except ValueError:
        return None


def _sold_at(value: str) -> float | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_IST).timestamp()
    except ValueError:
        return None


@router.get("/hooks/inrdeals/sale")
async def inrdeals_sale(
    key: str = "",
    txn: str = "",
    tag: str = "",
    amount: str = "",
    payout: str = "",
    shop: str = "",
    status: str = "",
    date: str = "",
) -> dict:
    expected = get_settings().INRDEALS_POSTBACK_KEY
    if not expected or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(status_code=404)
    if not _ID_RE.match(txn):
        raise HTTPException(status_code=400, detail="txn missing")

    click = _CLICK_TAG_RE.match(tag)
    device_id = tag if _ID_RE.match(tag) and not click and tag != "anon" else None
    event = analytics_service.build_event(
        "Purchase Recorded",
        surface="server",
        device_id=device_id,
        timestamp=_sold_at(date),
        insert_id=uuid.uuid5(uuid.NAMESPACE_URL, f"dealo-purchase/inrdeals-{txn}/recorded").hex,
        properties={
            "network": "inrdeals",
            "transaction_id": txn,
            "click_id": click.group(1) if click else None,
            "shop": shop[:100],
            "sale_amount": _amount(amount),
            "commission": _amount(payout),
            "currency": "INR",
            "status": (status or "unknown").lower()[:30],
            "click_surface": None,
        },
    )
    if not device_id:
        event["properties"]["distinct_id"] = "anonymous-purchase"
    analytics_service.fire(event)
    return {"ok": True}
