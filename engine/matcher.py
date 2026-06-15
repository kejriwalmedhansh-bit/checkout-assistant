"""
matcher.py — Product matching with submodel conflict detection
"""

import re
from dataclasses import dataclass

SUBMODEL_KEYWORDS = [
    "pro", "anc", "elite", "gen 2", "gen2", "neo", "plus", "max",
    "lite", "mini", "ultra", "prime", "sport",
    "141x", "141 pro", "141 anc", "141 elite", "141 gen",
]

COLOR_WORDS = [
    "obsidian", "porcelain", "hazel", "bay", "mint", "coral", "peony",
    "wintergreen", "aloe", "charcoal", "sage", "linen", "ultramarine",
    "mocha", "jade", "black", "white", "blue", "red", "green", "pink",
    "silver", "gold", "grey", "gray", "purple", "yellow",
]

STORAGE_PATTERN = re.compile(r'\b(\d+)\s*(gb|tb|mb)\b', re.IGNORECASE)

# Matches physical size/quantity: weight (g, mg, kg), volume (ml, l), or shoe
# sizes (UK/US/EU). Longest alternatives first to avoid partial matches.
_SIZE_RE = re.compile(
    r'\b(\d+(?:\.\d+)?)\s*(litre|liter|gms|gm|kg|ml|mg|g|l)\b'
    r'|\b(uk|us|eu)\s*(\d+(?:\.\d+)?)\b',
    re.IGNORECASE,
)

_FOREIGN_SOURCES = frozenset({
    "farfetch", "ssense", "net-a-porter", "mytheresa",
    "stockx", "kickscrew", "kicksonfire", "desertcart",
})

# Generic descriptor words stripped from both source and candidate token sets
# before Jaccard similarity and subset checks.  These words are
# merchant-specific labels that vary across retailers (e.g. Myntra says
# "Leather Sneakers", AJIO says "Shoes", Amazon says "Running Shoes"), so
# including them in similarity punishes cross-merchant matches unfairly.
# "womens"/"mens" are the normalized forms of "Women's"/"Men's".
_TOKEN_NOISE = frozenset({
    "women", "womens", "men", "mens", "boys", "girls",
    "casual", "running", "formal", "leather",
    "wireless", "bluetooth", "truly", "tws",
    "earbuds", "headphones", "sneakers", "shoes", "sandals",
    "deal",  # "Deal:" prefix sometimes added to Amazon titles
    "for",   # filler preposition common in candidate titles
})

# Strip feature-description suffixes before extracting submodel tags or
# computing similarity. Cuts at the first comma, opening parenthesis, or
# standalone "with" — all of which signal the start of spec copy rather than
# the product's model identity (e.g. "Noise Master Buds 2 with Sound by Bose
# (2026),51dB Adaptive ANC..." → "Noise Master Buds 2").
_CORE_STOP_RE = re.compile(r'\s*[,(]|\s+with\b', re.IGNORECASE)


def _core_name(text: str) -> str:
    m = _CORE_STOP_RE.search(text)
    return text[:m.start()].strip() if m else text.strip()


@dataclass
class MatchResult:
    match_type: str
    confidence: float
    notes: str
    submodel_conflict: bool


def _normalize(text: str) -> str:
    return re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()


def _token_similarity(a: str, b: str) -> float:
    tokens_a = set(_normalize(a).split())
    tokens_b = set(_normalize(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _extract_submodel_tags(text: str) -> set[str]:
    # Scan only the core model name, not feature descriptions that follow commas
    # or "with ..." clauses — prevents "Adaptive ANC" in a spec list from being
    # mistaken for an ANC submodel variant.
    normalized = _normalize(_core_name(text))
    return {kw for kw in SUBMODEL_KEYWORDS if kw in normalized}


def _extract_colors(text: str) -> set[str]:
    normalized = _normalize(text)
    return {c for c in COLOR_WORDS if c in normalized}


def _extract_storage(text: str) -> list[str]:
    return [m.group(0).lower().replace(' ', '') for m in STORAGE_PATTERN.finditer(text)]


def _extract_size(text: str) -> list[str]:
    """Extract physical sizes from raw text (weight, volume, shoe sizes).

    Operates on the lowercased raw text (not _normalize output) so that
    decimal points in shoe sizes like 'UK 3.5' are preserved.
    """
    sizes = []
    for m in _SIZE_RE.finditer(text.lower()):
        if m.group(1) is not None:
            num, unit = m.group(1), m.group(2).lower()
            if unit in ("gm", "gms"):
                unit = "g"
            elif unit in ("litre", "liter"):
                unit = "l"
            sizes.append(f"{num}{unit}")
        else:
            sizes.append(f"{m.group(3).upper()} {m.group(4)}")
    return sizes


def _is_refurbished(text: str) -> bool:
    normalized = _normalize(text)
    return any(w in normalized for w in ["refurbished", "renewed", "open box", "used", "pre owned"])


def _meaningful_tokens(text: str, extra_strip: frozenset = frozenset()) -> set[str]:
    """Normalized token set with noise words and extra tokens removed.

    Used for Jaccard similarity and subset checks so that merchant-specific
    descriptors (shoe type, gender label, material) don't dominate distance.
    Falls back to the full normalized set minus extras if stripping leaves
    nothing (e.g. a product named only "Running Shoes").
    """
    tokens = set(_normalize(text).split())
    stripped = tokens - _TOKEN_NOISE - extra_strip
    return stripped if stripped else tokens - extra_strip


def match_product(source_name: str, source_brand: str, candidate_title: str) -> MatchResult:
    source_norm = _normalize(source_name)
    candidate_norm = _normalize(candidate_title)
    brand_norm = _normalize(source_brand)

    if brand_norm and brand_norm not in candidate_norm:
        return MatchResult(match_type="No Match", confidence=0.0,
                           notes=f"Different brand — source is '{source_brand}'",
                           submodel_conflict=False)

    source_is_refurb = _is_refurbished(source_name)
    candidate_is_refurb = _is_refurbished(candidate_title)
    if source_is_refurb != candidate_is_refurb:
        note = "Candidate is refurbished, source is new" if candidate_is_refurb else "Source is refurbished, candidate is new"
        return MatchResult(match_type="Similar Match", confidence=0.4,
                           notes=note, submodel_conflict=True)

    source_tags = _extract_submodel_tags(source_name)
    candidate_tags = _extract_submodel_tags(candidate_title)
    source_only = source_tags - candidate_tags
    candidate_only = candidate_tags - source_tags
    submodel_conflict = bool(source_only or candidate_only)
    submodel_notes = ""
    if source_only:
        submodel_notes += f"Source has '{', '.join(source_only)}' not in candidate. "
    if candidate_only:
        submodel_notes += f"Candidate has '{', '.join(candidate_only)}' not in source."

    # Color: only conflict when BOTH sides carry a color AND they differ.
    # A color in the candidate alone (e.g. "Black" edition) is fine when the
    # source name has no color — that just means the source is color-agnostic.
    source_colors = _extract_colors(source_name)
    candidate_colors = _extract_colors(candidate_title)
    color_conflict = bool(source_colors and candidate_colors and source_colors != candidate_colors)
    color_notes = f"Color mismatch: {source_colors} vs {candidate_colors}" if color_conflict else ""

    source_storage = _extract_storage(source_name)
    candidate_storage = _extract_storage(candidate_title)
    storage_conflict = bool(source_storage and candidate_storage and source_storage != candidate_storage)
    storage_notes = f"Storage mismatch: {source_storage} vs {candidate_storage}" if storage_conflict else ""

    # Size/quantity: weight (g, ml, kg …) or shoe size (UK 6, US 8 …).
    # Only conflict when BOTH sides have a size AND they differ — a source
    # with no size listed is compatible with any quantity variant.
    source_size = _extract_size(source_name)
    candidate_size = _extract_size(candidate_title)
    size_conflict = bool(source_size and candidate_size and sorted(source_size) != sorted(candidate_size))
    size_notes = f"Size mismatch: {' / '.join(source_size)} vs {' / '.join(candidate_size)}" if size_conflict else ""

    # Noise-stripped token sets for subset and similarity checks.
    # Brand tokens are stripped too — brand presence is already enforced above,
    # so keeping them here only penalises sources where the brand isn't part of
    # the extracted product name (e.g. Myntra returns "Women Waffle Debut …"
    # without "Nike" in the title).
    brand_tokens = frozenset(_normalize(source_brand).split()) if source_brand else frozenset()
    source_tokens = _meaningful_tokens(source_name, brand_tokens)
    candidate_tokens = _meaningful_tokens(candidate_title, brand_tokens)

    inter = source_tokens & candidate_tokens
    union = source_tokens | candidate_tokens
    similarity = len(inter) / len(union) if union else 0.0

    conflict_notes = " | ".join(filter(None, [submodel_notes, color_notes, storage_notes, size_notes]))

    if submodel_conflict or color_conflict or storage_conflict or size_conflict:
        return MatchResult(match_type="Similar Match", confidence=max(0.3, similarity - 0.2),
                           notes=conflict_notes or "Variant conflict", submodel_conflict=submodel_conflict)

    # Forward subset: source core tokens ⊆ candidate tokens (source is the
    # brief name, candidate adds colour/spec/category words).
    if source_tokens and source_tokens.issubset(candidate_tokens):
        return MatchResult(match_type="Exact Match", confidence=1.0,
                           notes="Source tokens subset of candidate", submodel_conflict=False)

    # Reverse subset: candidate tokens ⊆ source tokens (long Amazon source
    # title that contains all of the short candidate's meaningful words).
    # Minimum 2 tokens after noise-stripping to avoid trivial single-word hits.
    if len(candidate_tokens) >= 2 and candidate_tokens.issubset(source_tokens):
        return MatchResult(match_type="Exact Match", confidence=1.0,
                           notes="Candidate tokens subset of source", submodel_conflict=False)

    if similarity >= 0.55:
        return MatchResult(match_type="Exact Match", confidence=similarity,
                           notes="", submodel_conflict=False)
    elif similarity >= 0.35:
        return MatchResult(match_type="Similar Match", confidence=similarity,
                           notes=f"Low similarity ({similarity:.0%})", submodel_conflict=False)
    else:
        return MatchResult(match_type="No Match", confidence=similarity,
                           notes=f"Too different ({similarity:.0%})", submodel_conflict=False)


_BOX_RE = re.compile(r'\b(without\s+box|open\s*box|unboxed)\b', re.IGNORECASE)


def _is_foreign_marketplace(source: str) -> bool:
    s = source.lower()
    return any(name in s for name in _FOREIGN_SOURCES)


def filter_discovery_results(discovery_results: list[dict], source_name: str,
                              source_brand: str, include_similar: bool = True) -> list[dict]:
    annotated = []
    for result in discovery_results:
        title = result.get("title", "")
        if not title:
            continue
        if _BOX_RE.search(title):
            continue
        if _is_foreign_marketplace(result.get("source", "")):
            continue
        match = match_product(source_name, source_brand, title)
        if match.match_type == "No Match":
            continue
        if match.match_type == "Similar Match" and not include_similar:
            continue
        annotated.append({
            **result,
            "match_type": match.match_type,
            "match_confidence": round(match.confidence, 2),
            "match_notes": match.notes,
            "submodel_conflict": match.submodel_conflict,
        })

    def sort_key(r):
        return ({"Exact Match": 0, "Similar Match": 1}.get(r["match_type"], 2),
                r.get("extracted_price", 9999))

    return sorted(annotated, key=sort_key)
