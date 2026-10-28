"""Turn the captured benchmark searches into hand-marked checklist entries.

Reads tests/fixtures/benchmark/*.json (from tests/capture_benchmark.py) and
the answers below, and appends the entries to tests/fixtures/match_checklist.json
under the sets "27 Oct AI club" and "fresh 25". Safe to re-run: entries for a
URL already in the checklist are replaced, not duplicated.

Marking rules, the same as the original 409:
  exact    the product (any colour; any size for clothes and shoes)
  similar  the product in another size, pack, storage, or inside a bundle
  wrong    another model, sub-model, brand, an accessory, or unrelated
A listing with no brand anywhere is "wrong" unless the seller is the brand.

    .venv/bin/python tests/build_benchmark_key.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BENCH = ROOT / "tests" / "fixtures" / "benchmark"
CHECKLIST = ROOT / "tests" / "fixtures" / "match_checklist.json"

E, S, W = "exact", "similar", "wrong"


def marks(default: str, **overrides: list[int]) -> dict[int, str]:
    """A default answer plus index lists: marks(W, exact=[0, 4], similar=[2])."""
    out: dict[int, str] = {}
    for key, idxs in overrides.items():
        for i in idxs:
            out[i] = {"exact": E, "similar": S, "wrong": W}[key]
    out[-1] = default
    return out


# slug -> (set name, kind, answers). kind: product | link | category.
# category = the search names a kind of thing, not one product; the live code
# never runs the matcher on those, so they're scored separately.
CASES: dict[str, tuple[str, str, dict[int, str]]] = {
    "adidas_originals_women_handball_spezial_sneakers": ("27 Oct AI club", "product", marks(
        W, exact=[6, 14, 15, 23, 25, 38, 39])),
    "nike_downshifter_14": ("27 Oct AI club", "link", marks(
        E, wrong=[3, 8, 11, 13, 15, 17, 23, 27, 30, 31, 33, 34, 35, 36, 37, 38, 39])),
    "allen_solly_men_polo_t_shirt_navy": ("fresh 25", "category", marks(E, wrong=[0, 3, 5, 6])),
    "biba_women_anarkali_kurta_set": ("fresh 25", "category", marks(
        W, exact=[12, 14, 15, 16, 17, 28, 32, 36])),
    "boat_rockerz_550_headphones": ("fresh 25", "product", marks(
        W, exact=[1, 2, 5, 6, 8, 9, 11, 15, 19, 25])),
    "cetaphil_moisturising_lotion_250ml": ("fresh 25", "product", marks(
        W, exact=[0, 1, 2, 5, 6, 8, 9, 10, 12, 14, 15, 18, 24],
        similar=[3, 7, 11, 16, 20, 26, 28, 29, 30, 32, 36, 37, 39])),
    "crocs_classic_clog_unisex_black": ("fresh 25", "product", marks(
        W, exact=[0, 2, 3, 4, 7, 9, 11, 12, 14, 17, 22, 24, 25, 26, 27, 29, 32, 34, 36])),
    "dot_key_vitamin_c_sunscreen_spf_50": ("fresh 25", "product", marks(
        W, exact=[0, 1, 3, 7, 11, 12, 22],
        similar=[2, 4, 5, 6, 9, 10, 13, 14, 16, 17, 20, 21, 25, 27, 28, 29, 30, 31, 35, 36, 39])),
    "jbl_flip_6_bluetooth_speaker": ("fresh 25", "product", marks(W, exact=[1, 2, 3, 4, 22], similar=[0])),
    "jockey_1406_women_hipster_brief_pack_of_3": ("fresh 25", "product", marks(W, exact=[9, 11])),
    "lakme_9_to_5_primer_matte_lipstick": ("fresh 25", "product", marks(
        E, wrong=[3, 4, 5, 21, 31, 38], similar=[12, 15, 19, 24, 25, 28, 32, 35, 36, 39])),
    "levis_512_slim_taper_jeans_men": ("fresh 25", "product", marks(
        E, wrong=[4, 13, 29, 34, 35, 36, 37])),
    "mamaearth_ubtan_face_wash_100ml": ("fresh 25", "product", marks(
        W, exact=[9], similar=[6, 12, 13, 14, 21, 26, 27, 28])),
    "maybelline_sky_high_mascara": ("fresh 25", "product", marks(W, exact=[0, 1, 2])),
    "minimalist_2_salicylic_acid_serum_30ml": ("fresh 25", "product", marks(
        W, exact=[0, 1, 4, 8, 9, 14],
        similar=[2, 3, 5, 6, 7, 10, 12, 13, 16, 17, 19, 21, 23, 27, 30, 32, 35, 36, 37, 39])),
    "noise_colorfit_pro_5_smartwatch": ("fresh 25", "product", marks(
        W, exact=[0, 3, 5, 6, 7, 10, 13, 15, 20, 21])),
    "nykaa_cosmetics_matte_to_last_liquid_lipstick": ("fresh 25", "product", marks(W, exact=[4, 6, 7, 8])),
    "philips_hl7756_mixer_grinder_750w": ("fresh 25", "product", marks(
        W, exact=[0, 2, 5, 8, 11, 15, 18], similar=[4, 10, 14])),
    "plum_green_tea_toner_200ml": ("fresh 25", "product", marks(
        W, exact=[0, 1, 2, 3, 4, 9],
        similar=[5, 6, 7, 8, 11, 12, 14, 15, 16, 17, 18, 20, 21, 26, 27, 29, 30, 33, 34, 38])),
    "prestige_pic_20_induction_cooktop": ("fresh 25", "product", marks(W)),
    "puma_men_softride_enzo_evo_running_shoes": ("fresh 25", "product", marks(W, exact=[0, 1, 2, 4])),
    "realme_buds_t310_earbuds": ("fresh 25", "product", marks(
        W, exact=[0, 1, 2, 3, 4, 5, 6, 8, 9, 11, 12, 14, 32, 39])),
    "samsung_galaxy_m35_5g_8gb_128gb": ("fresh 25", "product", marks(W, exact=[0, 1, 10], similar=[3, 13])),
    "skechers_go_walk_7_men": ("fresh 25", "product", marks(W, exact=[9, 10])),
    "woodland_leather_boots_men_brown": ("fresh 25", "category", marks(E, wrong=[15, 24, 28, 33])),
}

_RUPEES = re.compile(r"₹\s*([\d,]+(?:\.\d+)?)")


def was_price(row: dict) -> float | None:
    """The crossed-out price a listing shows, when it shows one.
    "72% off₹3,990" puts the percentage in extracted_original_price, so the
    rupee figure is read from the text; anything not above the price is noise."""
    price = row.get("extracted_price")
    m = _RUPEES.search(row.get("original_price") or "")
    was = float(m.group(1).replace(",", "")) if m else row.get("extracted_original_price")
    return was if was and price and was > price else None


def main() -> int:
    data = json.loads(CHECKLIST.read_text())
    new_urls = set()
    entries = []
    for slug, (set_name, kind, answers) in CASES.items():
        raw = json.loads((BENCH / f"{slug}.json").read_text())
        rows = raw["shopping_results"]
        url = raw.get("url") or f"typed:{slug}"
        listings = [{
            "title": r.get("title") or "",
            "shop": r.get("seller") or "",
            "answer": answers.get(i, answers[-1]),
            "price": r.get("extracted_price"),
            "was_price": was_price(r),
        } for i, r in enumerate(rows)]
        entries.append({
            "set": set_name, "kind": kind, "product": raw["query"], "url": url,
            "page_title": raw.get("page_title") or raw["query"],
            "typed": raw.get("url") is None, "query_sent": raw["query"],
            "listings": listings,
        })
        new_urls.add(url)
    kept = [l for l in data["links"] if l["url"] not in new_urls]
    data["links"] = kept + entries
    CHECKLIST.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    n = sum(len(e["listings"]) for e in entries)
    print(f"wrote {len(entries)} entries, {n} listings; checklist now has {len(data['links'])} links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
