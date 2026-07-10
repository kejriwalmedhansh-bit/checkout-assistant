"""Cashback-card data access. Loads data/cashback_cards.json once."""
from __future__ import annotations

import json

from ..constants import DATA_DIR

_CARDS_PATH = DATA_DIR / "cashback_cards.json"

_cards: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _cards
    if _cards is None:
        with open(_CARDS_PATH) as f:
            _cards = json.load(f)
    return _cards


def all_cards() -> dict[str, dict]:
    return _load()


def get(name: str) -> dict | None:
    return _load().get(name)
