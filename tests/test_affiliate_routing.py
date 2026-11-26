"""Shop links must go out through a network that can actually pay for them.

Cuelinks rejected Flipkart and AJIO and dropped Croma, so /go sends those
through INRDeals instead (checked by hand 26 Nov 2026).
"""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.application import app  # noqa: E402

client = TestClient(app, follow_redirects=False)


@pytest.mark.parametrize("shop_url", [
    "https://www.flipkart.com/some-phone/p/itm123",
    "https://www.ajio.com/p/469123",
    "https://www.croma.com/some-tv/p/301234",
    "https://www.myntra.com/shoes/123/buy",
    "https://www.shopsy.in/some-kurta/p/itm9",
    "https://dl.flipkart.com/s/AbC12",
])
def test_shop_link_goes_through_inrdeals(shop_url):
    r = client.get("/go", params={"url": shop_url, "surface": "web"})
    assert r.status_code == 302
    target = urlparse(r.headers["location"])
    assert target.netloc == "inr.deals"
    assert parse_qs(target.query)["url"] == [shop_url]


def test_shop_cuelinks_still_carries_stays_on_cuelinks():
    r = client.get("/go", params={"url": "https://www.tatacliq.com/x/p-mp1", "surface": "web"})
    assert urlparse(r.headers["location"]).netloc == "linksredirect.com"


def test_visitor_without_device_id_is_tagged_with_the_click():
    r = client.get("/go", params={"url": "https://www.myntra.com/x", "surface": "web"})
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["subid"] == ["c_" + q["subid2"][0]]


def test_inrdeals_sale_alert(monkeypatch):
    from src.api.routers import affiliate_postback
    from src.config import get_settings

    sent = []
    monkeypatch.setattr(affiliate_postback.analytics_service, "fire", sent.append)
    sale = {"txn": "NYK-1", "tag": "c_0123456789abcdef", "amount": "2,900", "payout": "78.88",
            "shop": "Nykaa Beauty", "status": "Pending", "date": "2026-11-15 00:00:00"}

    # Switched off until a key is set, and a wrong key is refused.
    monkeypatch.setattr(get_settings(), "INRDEALS_POSTBACK_KEY", "")
    assert client.get("/hooks/inrdeals/sale", params={**sale, "key": ""}).status_code == 404
    monkeypatch.setattr(get_settings(), "INRDEALS_POSTBACK_KEY", "s3cret")
    assert client.get("/hooks/inrdeals/sale", params={**sale, "key": "wrong"}).status_code == 404
    assert sent == []

    assert client.get("/hooks/inrdeals/sale", params={**sale, "key": "s3cret"}).status_code == 200
    props = sent[0]["properties"]
    assert sent[0]["event"] == "Purchase Recorded"
    assert (props["network"], props["sale_amount"], props["commission"], props["status"]) == ("inrdeals", 2900.0, 78.88, "pending")
    assert props["click_id"] == "0123456789abcdef"
    assert props["distinct_id"] == "anonymous-purchase"

    # The same sale reported twice carries the same id, so Mixpanel keeps one.
    client.get("/hooks/inrdeals/sale", params={**sale, "key": "s3cret"})
    assert sent[1]["properties"]["$insert_id"] == props["$insert_id"]
