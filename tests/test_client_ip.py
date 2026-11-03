"""/go and /out must read the shopper's address the same way the rate
limiter does: the last X-Forwarded-For hop, which is what Render saw."""
from starlette.requests import Request

from src.api.routers.redirect import _client_ip


def _request(forwarded=None, client=("10.0.0.1", 1234)):
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": client, "method": "GET", "path": "/"})


def test_last_hop_wins_over_a_forged_first_hop():
    assert _client_ip(_request("1.2.3.4, 49.36.1.1")) == "49.36.1.1"


def test_single_hop():
    assert _client_ip(_request("49.36.1.1")) == "49.36.1.1"


def test_no_header_falls_back_to_the_socket():
    assert _client_ip(_request()) == "10.0.0.1"


def test_unknown_becomes_none():
    assert _client_ip(_request(client=None)) is None
