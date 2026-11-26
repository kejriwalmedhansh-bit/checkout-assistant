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
