"""In-memory TTL cache + session store (stateless, stdlib only).

Replaces the old SQLite disk cache (db/cache.py) and the SQLite WhatsApp
session store (whatsapp/session_store.py). Everything lives in process memory,
so nothing survives a restart — acceptable for a stateless deploy.

Uses time.monotonic() so clock adjustments can't corrupt TTL math.
"""
from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """A minimal thread-unsafe TTL cache with lazy (on-access) eviction."""

    def __init__(self, default_ttl: float, max_size: int | None = None):
        self.default_ttl = default_ttl
        self.max_size = max_size
        # key -> (value, expires_at_monotonic)
        self._store: dict[Any, tuple[Any, float]] = {}

    def _now(self) -> float:
        return time.monotonic()

    def get(self, key: Any) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._now() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: Any, value: Any, ttl: float | None = None) -> None:
        ttl = self.default_ttl if ttl is None else ttl
        if self.max_size is not None and len(self._store) >= self.max_size:
            self._evict_expired()
            if len(self._store) >= self.max_size:
                # Drop the soonest-to-expire entry to make room.
                oldest = min(self._store, key=lambda k: self._store[k][1])
                self._store.pop(oldest, None)
        self._store[key] = (value, self._now() + ttl)

    def touch(self, key: Any, ttl: float | None = None) -> bool:
        """Slide the expiry of an existing, unexpired key. Returns False if absent/expired."""
        value = self.get(key)
        if value is None:
            return False
        self.set(key, value, ttl)
        return True

    def _evict_expired(self) -> None:
        now = self._now()
        for k in [k for k, (_, exp) in self._store.items() if now > exp]:
            self._store.pop(k, None)


class SessionStore:
    """Per-phone WhatsApp session state on top of two TTL caches.

    - ``_users`` tracks first-seen phones (long-lived) for is_new_user().
    - ``_sessions`` holds the last routes payload with a sliding TTL.
    """

    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        # Users never expire in-process (long TTL); sessions slide.
        self._users = TTLCache(default_ttl=float("inf"))
        self._sessions = TTLCache(default_ttl=ttl_seconds)

    def is_new_user(self, phone_number: str) -> bool:
        if self._users.get(phone_number) is not None:
            return False
        self._users.set(phone_number, True)
        return True

    def get_session(self, phone_number: str) -> dict | None:
        session = self._sessions.get(phone_number)
        if session is None:
            return None
        # Sliding TTL: accessing the session extends its life.
        self._sessions.touch(phone_number, self.ttl_seconds)
        return session

    def set_session(self, phone_number: str, data: dict) -> None:
        self._sessions.set(phone_number, data, self.ttl_seconds)


# --- Module singletons (import and use directly) ---
# TTLs are read once at import from settings; both default to the intended values.
from .config import get_settings as _get_settings  # noqa: E402

_settings = _get_settings()
search_cache = TTLCache(default_ttl=_settings.SEARCH_CACHE_TTL_SECONDS, max_size=None)
session_store = SessionStore(ttl_seconds=_settings.WHATSAPP_SESSION_TTL_SECONDS)
