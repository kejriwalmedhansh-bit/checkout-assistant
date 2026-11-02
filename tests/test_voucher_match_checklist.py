"""Every shop Dealo knows must find its voucher brand on every source that
sells one — checked for the names Dealo actually sees, not just the
catalogue's own spelling.

Why (2026-11-02): an igp.com link named the shop "IGP.com"; no voucher
matched although IGP is on Gyftr, Maximize and BuyHatke, and the shopper was
sent to pay full price. Nothing flagged it. The same quiet miss existed for
68 of the 350 shop websites on file. This test runs the three name paths a
result can arrive by and fails when a shop that used to find its voucher
stops finding it, or finds a different brand's.

Known gaps (in-store-only cards for an online shopper, sub-brand ties) live
in tests/fixtures/voucher_match_known.json. After a deliberate change:
    .venv/bin/python tests/test_voucher_match_checklist.py --accept

Run:  .venv/bin/python -m pytest tests/test_voucher_match_checklist.py -q
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.repositories import buyhatke_repository, maximize_repository, voucher_repository  # noqa: E402
from src.repositories._brand_matching import _strip_generic_suffix_words, normalize  # noqa: E402
from src.services import search_service as ss  # noqa: E402

KNOWN = ROOT / "tests" / "fixtures" / "voucher_match_known.json"
SOURCES = {"gyftr": voucher_repository, "maximize": maximize_repository, "buyhatke": buyhatke_repository}
_TLD = re.compile(r"\.(com|in|co\.in|net|org|co|io|shop|store|app|fit)$", re.IGNORECASE)
_CHANNEL = re.compile(r"[-\s]*(luxe)?[-\s]*(gift card|in store|online|\(.*?\))\s*$", re.IGNORECASE)


def _key(name: str) -> str:
    """A shop's identity with web endings, generic words and a catalogue's
    channel labels ("Gift Card", "In Store", "(4 Hr Wait)") removed."""
    bare = _CHANNEL.sub("", _CHANNEL.sub("", name or ""))
    return normalize(_strip_generic_suffix_words(_TLD.sub("", bare.strip().lower())))


def _listed() -> dict[str, dict[str, str]]:
    """brand key -> {source: brand_name} for every brand with a voucher."""
    out: dict[str, dict[str, str]] = {}
    for src, repo in SOURCES.items():
        records = repo.all_vouchers() if hasattr(repo, "all_vouchers") else repo.all_brands()
        for rec in records:
            name = rec.get("brand_name") or ""
            if _key(name):
                out.setdefault(_key(name), {}).setdefault(src, name)
    return out


def _shop_names() -> list[tuple[str, str]]:
    """(shop name as a result would carry it, expected brand key)."""
    names: list[tuple[str, str]] = []
    domains = json.loads((ROOT / "data" / "domain_brand_map.json").read_text())
    for domain, brand in domains.items():
        # 1. the catalogue's own spelling
        names.append((brand, _key(brand)))
        # 2. a pasted link on the shop's website that names itself by its address
        host = re.sub(r"^(www|shop|online|b)\.", "", domain)
        stem = _TLD.sub("", host).split(".")[0]
        page = f'<meta property="og:site_name" content="{stem.upper()}{host[len(stem):]}" />'
        merchant = ss._brand_website_name(page, domain, None)
        if merchant:
            names.append((merchant, _key(brand)))
    # 3. seller labels Google has really shown, from the saved searches
    listed = _listed()
    for path in glob.glob(str(ROOT / "tests" / "fixtures" / "**" / "*.json"), recursive=True):
        for label in set(re.findall(r'"seller": *"([^"]+)"', Path(path).read_text())):
            if _key(label) in listed:
                names.append((label, _key(label)))
    return names


def _failures() -> dict[str, str]:
    """'shop name | source' -> what went wrong, for every shop that should
    find a voucher on that source and doesn't."""
    listed = _listed()
    bad: dict[str, str] = {}
    for name, expected in _shop_names():
        for src, expected_name in (listed.get(expected) or {}).items():
            got = (SOURCES[src].get_by_merchant(name) or {}).get("brand_name")
            if got is None:
                bad[f"{name} | {src}"] = f"found nothing, should be {expected_name!r}"
            elif _key(got) != expected:
                bad[f"{name} | {src}"] = f"found {got!r}, should be {expected_name!r}"
    return bad


def test_every_known_shop_finds_its_voucher():
    known = json.loads(KNOWN.read_text()) if KNOWN.exists() else {}
    new = {k: v for k, v in _failures().items() if k not in known}
    assert not new, "shops that no longer find their voucher:\n" + "\n".join(
        f"  {k}: {v}" for k, v in sorted(new.items()))


def test_the_igp_link_finds_igp_everywhere():
    for src in SOURCES:
        assert (SOURCES[src].get_by_merchant("IGP.com") or {}).get("brand_name") == "IGP", src


if __name__ == "__main__":
    bad = _failures()
    if "--accept" in sys.argv:
        KNOWN.write_text(json.dumps(dict(sorted(bad.items())), indent=2, ensure_ascii=False) + "\n")
        print(f"recorded {len(bad)} known gap(s) in {KNOWN.relative_to(ROOT)}")
    else:
        for k, v in sorted(bad.items()):
            print(f"{k}: {v}")
        print(f"{len(bad)} gap(s)")
