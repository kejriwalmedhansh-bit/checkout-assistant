"""In-memory WhatsApp conversation log (stateless, same pattern as cache.py).

Keeps a rolling transcript per phone number so a real conversation can be
read back for manual QA — "what did the user send, what did the bot send
back, in what order" — since nothing else in the codebase currently records
message content (analytics_service only tracks event names/properties, not
the actual text). Not a permanent record: like session state, it resets on
process restart/redeploy — acceptable for a manual QA tool, consistent with
the rest of this app's stateless, in-memory design.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Literal

_MAX_MESSAGES_PER_PHONE = 200
_MAX_PHONES = 500

_log: dict[str, deque[dict]] = {}
_phone_order: deque[str] = deque()  # oldest-first, for evicting a phone once _MAX_PHONES is hit


def record(phone: str, direction: Literal["in", "out"], text: str) -> None:
    if phone not in _log:
        if len(_log) >= _MAX_PHONES:
            oldest = _phone_order.popleft()
            _log.pop(oldest, None)
        _log[phone] = deque(maxlen=_MAX_MESSAGES_PER_PHONE)
        _phone_order.append(phone)
    _log[phone].append({"direction": direction, "text": text, "ts": time.time()})


def get_conversation(phone: str) -> list[dict]:
    return list(_log.get(phone, []))


def list_phones() -> list[str]:
    """Most-recently-active first."""
    return sorted(
        _log.keys(),
        key=lambda p: _log[p][-1]["ts"] if _log[p] else 0,
        reverse=True,
    )
