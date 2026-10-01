"""Dealo inside ChatGPT and Claude: the /mcp endpoint both of them call.

Checks the handshake, that the tool links its card (both the open-standard
key and ChatGPT's own), and that a real shop prices end to end from the
local catalogue. Uses Nykaa, which every refresh so far has kept active.

Run:  .venv/bin/python -m pytest tests/test_chat_app.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from src.application import app  # noqa: E402

client = TestClient(app)


def _rpc(method: str, params: dict | None = None, ua: str = "test") -> dict:
    r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                    headers={"user-agent": ua})
    assert r.status_code == 200
    return r.json()


def test_handshake_and_notifications():
    init = _rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})["result"]
    assert init["protocolVersion"] == "2025-06-18"
    assert "tools" in init["capabilities"]
    assert client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    assert client.get("/mcp").status_code == 405


def test_tool_points_at_card_for_both_apps():
    tool = _rpc("tools/list")["result"]["tools"][0]
    uri = tool["_meta"]["ui"]["resourceUri"]
    assert tool["_meta"]["openai/outputTemplate"] == uri
    card = _rpc("resources/read", {"uri": uri})["result"]["contents"][0]
    assert card["mimeType"] == "text/html;profile=mcp-app"
    assert "ui/initialize" in card["text"]


def test_priced_answer_and_tracked_link():
    res = _rpc("tools/call", {"name": "find_gift_card_deal",
                              "arguments": {"shop": "Nykaa", "amount_inr": 4000}}, ua="openai-mcp/1.0")["result"]
    deal = res["structuredContent"]["deal"]
    assert deal["priced"] and deal["saving"] > 0
    assert "/out?url=" in deal["buy_url"] and "surface=chatgpt" in deal["buy_url"]
    assert ".0%" not in res["content"][0]["text"]


def test_unknown_shop_says_so():
    res = _rpc("tools/call", {"name": "find_gift_card_deal", "arguments": {"shop": "qwzxv shop"}})["result"]
    assert res["structuredContent"]["has_voucher"] is False
    assert "no gift card discount" in res["content"][0]["text"]
