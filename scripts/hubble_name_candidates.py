"""Partner card names (Gyftr / Maximize / BuyHatke) that don't reach a Hubble
card although Hubble sells a card whose name starts the same way: possible
"Steam vs Steam wallet" misses (18 Nov 2026). Each one needs a person's
decision, recorded once in data/hubble_name_review.json: link it (an alias
in data/hubble_aliases.json) or mark it a different card or shop.

Used by scripts/hubble_daily_check.py; run alone to list them:
    HUBBLE_ENV=production .venv/bin/python scripts/hubble_name_candidates.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.services import hubble_service as h  # noqa: E402

REVIEW = ROOT / "data" / "hubble_name_review.json"
MASTERS = ["gyftr_master", "maximize_master", "buyhatke_master"]
# Names that are a seller's in-store copy of a card are judged by their
# online twin; "Luxe" cards match by their own rule.
_SKIP = re.compile(r"in[\s-]?store|luxe", re.I)


def partner_names() -> dict[str, set[str]]:
    names: dict[str, set[str]] = {}
    for f in MASTERS:
        data = json.loads((ROOT / "data" / f"{f}.json").read_text())
        items = data if isinstance(data, list) else list(data.values())
        for x in items:
            if isinstance(x, dict) and (x.get("brand_name") or x.get("name")):
                names.setdefault(x.get("brand_name") or x.get("name"), set()).add(f.split("_")[0])
    return names


def _first_word(name: str) -> str:
    words = [h.normalize(w) for w in re.split(r"[\s\-]+", name) if h.normalize(w)]
    return words[0] if words else ""


def reviewed() -> dict[str, str]:
    data = json.loads(REVIEW.read_text()) if REVIEW.exists() else {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def candidates(brands: list[dict] | None = None) -> list[dict]:
    """[{name, sellers, hubble: [titles]}] not yet decided."""
    brands = brands if brands is not None else h.catalogue_brands()
    by_word: dict[str, set[str]] = {}
    for b in brands:
        by_word.setdefault(_first_word(b["name"]), set()).add(b["name"])
    done = reviewed()
    out = []
    for name, sellers in sorted(partner_names().items()):
        if _SKIP.search(name) or h.normalize(name) in done:
            continue
        if h.brand_for(name) or h.brand_for(name, in_store=True):
            continue
        word = _first_word(name)
        if len(word) >= 4 and word in by_word:
            out.append({"name": name, "sellers": sorted(sellers), "hubble": sorted(by_word[word])})
    return out


if __name__ == "__main__":
    for c in candidates():
        print(f"{c['name']!r:45} {c['sellers']} -> {c['hubble']}")
