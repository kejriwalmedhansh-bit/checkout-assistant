"""Refresh the Product Picker fixtures from the live SearchApi.

Each query costs one SearchApi credit (budget is 1,000/month), so run this
only when the saved listings have gone stale — normal verification should use
the fixtures via tests/check_picker.py, which is free and deterministic.

    .venv/bin/python tests/capture_fixtures.py

After refreshing, re-run `tests/check_picker.py --baseline` so the comparison
baseline matches the new listings.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.repositories import searchapi_repository  # noqa: E402

# The manual regression set from CLAUDE.md, plus the "product that doesn't
# exist" case (`airpods pro max`) and its two real counterparts.
QUERIES = [
    "airpods pro max",
    # The same product spelled with a space. It is a genuinely different search
    # — different tokens, different listings — and it used to fall through
    # every filter into a raw unvetted dump of counterfeits. Kept as its own
    # fixture so that can't come back unnoticed.
    "air pods pro max",
    "airpods max",
    "boat airdopes 141",
    "apple iphone 17 256gb",
    "iphone 17e 256gb",
    "ray-ban meta wayfarer gen 2",
    "lakme cc cream",
    "oneplus 15 5g 256gb",
    "puma skyrocket lite 2",
    "adidas supernova rise 3 m running shoes for men",
]

OUT = pathlib.Path(__file__).parent / "fixtures" / "search"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for query in QUERIES:
        raw = searchapi_repository.search_products(query)
        if raw.get("error"):
            print(f"  SKIP {query}: {raw['error']}")
            continue
        slug = query.replace(" ", "_").replace("-", "_")
        listings = raw.get("shopping_results", [])
        (OUT / f"{slug}.json").write_text(
            json.dumps({"query": query, "shopping_results": listings}, indent=1)
        )
        print(f"  saved {slug}.json ({len(listings)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
