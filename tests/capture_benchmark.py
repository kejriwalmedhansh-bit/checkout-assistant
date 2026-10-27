"""Capture raw Google Shopping results for the matching benchmark.

One SearchApi credit per query. The saved files feed the hand-marked answer
key in tests/fixtures/match_checklist.json (set "fresh 25" and "27 Oct AI
club"), so re-run only to add cases, never to refresh marked ones.

    .venv/bin/python tests/capture_benchmark.py            # all queries below
    .venv/bin/python tests/capture_benchmark.py "query"    # one query

Each entry is (search text, pasted link or None, page title or None). For a
pasted link the search text is what Dealo sent to Google for that page.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.repositories import searchapi_repository  # noqa: E402

CASES: list[tuple[str, str | None, str | None]] = [
    # 27 Oct 2026, Calcutta AI Club
    ("Adidas Originals Women Handball Spezial Sneakers", None, None),
    ("nike downshifter 14",
     "https://www.nykaafashion.com/nike-charcoal-men-s-downshifter-14-running-shoes/p/27579262",
     "Nike Men"),
    # fashion
    ("puma men softride enzo evo running shoes", None, None),
    ("levis 512 slim taper jeans men", None, None),
    ("allen solly men polo t-shirt navy", None, None),
    ("biba women anarkali kurta set", None, None),
    ("skechers go walk 7 men", None, None),
    ("crocs classic clog unisex black", None, None),
    ("woodland leather boots men brown", None, None),
    ("jockey 1406 women hipster brief pack of 3", None, None),
    # beauty
    ("minimalist 2% salicylic acid serum 30ml", None, None),
    ("lakme 9 to 5 primer matte lipstick", None, None),
    ("dot & key vitamin c sunscreen spf 50", None, None),
    ("mamaearth ubtan face wash 100ml", None, None),
    ("maybelline sky high mascara", None, None),
    ("plum green tea toner 200ml", None, None),
    ("nykaa cosmetics matte to last liquid lipstick", None, None),
    ("cetaphil moisturising lotion 250ml", None, None),
    # electronics and appliances
    ("samsung galaxy m35 5g 8gb 128gb", None, None),
    ("boat rockerz 550 headphones", None, None),
    ("jbl flip 6 bluetooth speaker", None, None),
    ("noise colorfit pro 5 smartwatch", None, None),
    ("philips hl7756 mixer grinder 750w", None, None),
    ("prestige pic 20 induction cooktop", None, None),
    ("realme buds t310 earbuds", None, None),
]

OUT = pathlib.Path(__file__).parent / "fixtures" / "benchmark"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = [c for c in CASES if not argv[1:] or c[0] in argv[1:]]
    for query, url, page_title in wanted:
        path = OUT / f"{slug(query)}.json"
        if path.exists():
            print(f"  kept  {path.name} (already captured)")
            continue
        raw = searchapi_repository.search_products(query)
        if raw.get("error"):
            print(f"  SKIP  {query}: {raw['error']}")
            continue
        listings = raw.get("shopping_results", [])
        path.write_text(json.dumps({"query": query, "url": url, "page_title": page_title,
                                    "shopping_results": listings}, indent=1, ensure_ascii=False))
        print(f"  saved {path.name} ({len(listings)} listings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
