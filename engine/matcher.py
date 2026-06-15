import re
import difflib


# ── helpers ──────────────────────────────────────────────────────────────────

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


_STORAGE_NORM_RE = re.compile(r"(\d+)\s*(gb|tb)", re.IGNORECASE)

_REFURB_RE = re.compile(
    r"\b(refurb(?:ished)?|renewed|open[- ]?box|pre[- ]?owned|second[- ]?hand|secondhand)\b",
    re.IGNORECASE,
)


def detect_condition(product: dict) -> str:
    """Return 'refurbished' if the product is clearly non-new, else 'new'."""
    if _REFURB_RE.search(product.get("name") or ""):
        return "refurbished"
    for prop in (product.get("additionalProperties") or []):
        key = (prop.get("name") or "").lower()
        val = (prop.get("value") or "")
        if "condition" in key:
            if _REFURB_RE.search(val) or re.search(r"\bused\b", val, re.IGNORECASE):
                return "refurbished"
        if _REFURB_RE.search(val):
            return "refurbished"
    if _REFURB_RE.search(product.get("description") or ""):
        return "refurbished"
    return "new"


def _apply_condition(result: dict, original: dict, candidate: dict) -> dict:
    """Downgrade Exact Match to Similar Match when candidate is refurbished and original is new."""
    if (result["match_type"] == "Exact Match"
            and candidate.get("_condition") == "refurbished"
            and original.get("_condition", "new") == "new"):
        return {"match_type": "Similar Match", "variant_notes": "Refurbished listing"}
    return result


def _tokenize(name: str) -> list[str]:
    """Split a product name into word tokens for similarity scoring.
    Normalises '128 GB' → '128gb' so spacing differences don't split storage tokens.
    """
    s = _STORAGE_NORM_RE.sub(lambda m: m.group(1) + m.group(2).lower(), name.lower())
    return [t for t in (re.sub(r"[^a-z0-9]", "", w) for w in s.split()) if t]


def _brand(product: dict) -> str:
    """
    Extract brand from flat Zyte schema (brand.name) or from the product name
    as a fallback when Zyte returns a spurious brand (e.g. 'Amazon Prime logo').
    """
    b = product.get("brand") or {}
    raw = (b.get("name") or "") if isinstance(b, dict) else str(b)
    # Filter out obviously wrong values injected by Zyte on Amazon pages
    _noise = {"amazon prime", "amazon", "prime"}
    if _normalise(raw).lower() in _noise or "logo" in raw.lower():
        raw = ""
    if raw:
        return _normalise(raw)
    # Fallback: check if a known brand appears in the product name
    name = product.get("name") or ""
    _known_brands = [
        "apple", "samsung", "sony", "lg", "hp", "dell", "lenovo", "asus",
        "acer", "microsoft", "google", "oneplus", "realme", "xiaomi", "oppo",
        "vivo", "motorola", "nokia", "huawei", "canon", "nikon",
    ]
    lower = name.lower()
    for brand in _known_brands:
        if brand in lower:
            return brand
    return ""


def _sku(product: dict) -> str:
    """Return normalised SKU (Zyte uses 'sku' for ASIN / product code)."""
    return _normalise(product.get("sku") or "")


def _mpn(product: dict) -> str:
    """Return normalised MPN — may be absent in Zyte flat schema."""
    return _normalise(product.get("mpn") or "")


def _gtins(product: dict) -> set[str]:
    """Return GTIN values. Zyte flat schema doesn't emit these; kept for future."""
    return {g.get("value", "") for g in (product.get("gtin") or [])} - {""}


def get_price(product: dict) -> float | None:
    """Price from Zyte flat schema ('price' key is a string like '110290.0')."""
    raw = product.get("price")
    if raw is not None:
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass
    return None


def get_regular_price(product: dict) -> float | None:
    raw = product.get("regularPrice")
    if raw is not None:
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass
    return None


def get_availability(product: dict) -> str:
    """Zyte flat schema: 'availability' is a string or may be absent."""
    return product.get("availability") or ""


# ── spec extraction ───────────────────────────────────────────────────────────

_COLOR_WORDS = [
    "black", "white", "silver", "gold", "blue", "red", "green",
    "pink", "grey", "gray", "yellow", "purple", "orange", "starlight",
    "midnight", "sky", "coral", "teal", "lavender",
    "obsidian", "porcelain", "hazel", "bay", "mint", "peony", "wintergreen",
    "aloe", "charcoal", "sage", "linen", "ultramarine", "mocha", "jade",
]
_STORAGE_RE = re.compile(r"\b(\d+\s*(?:gb|tb))\b", re.IGNORECASE)
_RAM_RE = re.compile(r"\b(\d+\s*gb)\s+(?:ram|memory|unified)\b", re.IGNORECASE)
# Matches "13.6 inch", "15.3 inch", '13.6″', '13.6"'
_SIZE_RE = re.compile(r"\b(\d+\.?\d*)\s*(?:inch|″|\")\b", re.IGNORECASE)

# Apple part-number codes: e.g. MDHC4HN/A, MDV94HN/A, MXD13HN/A
_APPLE_CODE_RE = re.compile(r"\b([A-Z]{2,5}\d{1,2}[A-Z]{2}(?:\/[A-Z])?)\b")


def _extract_specs(name: str) -> dict:
    lower = name.lower()
    colors = [c for c in _COLOR_WORDS if c in lower]
    storages = [m.group(1).lower().replace(" ", "") for m in _STORAGE_RE.finditer(lower)]
    rams = [m.group(1).lower().replace(" ", "") for m in _RAM_RE.finditer(lower)]
    sizes = [m.group(1) for m in _SIZE_RE.finditer(name)]
    return {
        "colors": set(colors),
        "storages": set(storages),
        "rams": set(rams),
        "sizes": set(sizes),
    }


def _merge_product_specs(name_specs: dict, product: dict) -> dict:
    """
    Augment name-derived specs with values from Zyte additionalProperties.

    Flipkart (and other merchants) often omit color/size from the product name
    but expose them as structured properties ('selected color', 'variant', etc.).
    Without this merge, conflicts are invisible to the matcher.
    """
    merged = {k: set(v) for k, v in name_specs.items()}
    merged.setdefault("sizes", set())

    for prop in (product.get("additionalProperties") or []):
        if not isinstance(prop, dict):
            continue
        key = (prop.get("name") or "").lower().strip()
        val = (prop.get("value") or "").lower().strip()

        if "color" in key or "colour" in key:
            for c in _COLOR_WORDS:
                if c in val:
                    merged["colors"].add(c)

        m = re.search(r"(\d+\.?\d*)\s*inch", val)
        if m:
            merged["sizes"].add(m.group(1))

    return merged


def _apple_codes(product: dict) -> set[str]:
    """
    Extract Apple part-number codes (e.g. MDHC4HN/A) from name, MPN, and
    additionalProperties.  Different codes mean different SKUs — never Exact Match.
    """
    texts = [product.get("name") or "", product.get("mpn") or ""]
    for prop in (product.get("additionalProperties") or []):
        if isinstance(prop, dict):
            texts.append(prop.get("value") or "")
    codes: set[str] = set()
    for text in texts:
        for m in _APPLE_CODE_RE.finditer(text.upper()):
            codes.add(m.group(1))
    return codes


def _model_tokens(name: str) -> set[str]:
    """Pull out model-like tokens (M4/M4 Pro/RTX 4090/i9-13900K etc.)."""
    tokens: set[str] = set()

    # Apple silicon: M1/M2/M3/M4 [Pro|Max|Ultra]
    for m in re.finditer(r"\bm[1-9](?:\s+(?:pro|max|ultra))?\b", name, re.IGNORECASE):
        tokens.add(m.group().lower().replace(" ", "-"))

    # Generic alpha-numeric model codes: 2-3 letters + digits
    for m in re.finditer(r"\b[A-Za-z]{1,3}\d{3,6}[A-Za-z0-9]*\b", name):
        tokens.add(m.group().lower())

    # Year tokens
    for m in re.finditer(r"\b(202\d)\b", name):
        tokens.add(m.group())

    return tokens


# ── main matching function ────────────────────────────────────────────────────

def match_product(original: dict, candidate: dict) -> dict:
    """
    Compare *candidate* against *original* and return:
      {"match_type": "Exact Match" | "Similar Match" | "No Match",
       "variant_notes": str}
    """
    orig_name = original.get("name") or ""
    cand_name = candidate.get("name") or ""

    if not cand_name:
        return {"match_type": "No Match", "variant_notes": "No product name"}

    orig_brand = _brand(original)
    cand_brand = _brand(candidate)
    orig_mpn = _mpn(original)
    cand_mpn = _mpn(candidate)
    orig_sku = _sku(original)
    cand_sku = _sku(candidate)
    orig_gtins = _gtins(original)
    cand_gtins = _gtins(candidate)

    notes: list[str] = []

    # ── Tier 1: SKU ──
    sku_match = bool(orig_sku and cand_sku and orig_sku == cand_sku)
    if sku_match:
        return _apply_condition(
            {"match_type": "Exact Match", "variant_notes": f"SKU {orig_sku}"},
            original, candidate,
        )

    # ── Tier 2: MPN / GTIN ──
    mpn_match = bool(orig_mpn and cand_mpn and orig_mpn == cand_mpn)
    gtin_match = bool(orig_gtins & cand_gtins)

    # ── brand ──
    brand_match = bool(
        orig_brand and cand_brand
        and (orig_brand in cand_brand or cand_brand in orig_brand)
    )

    # ── name similarity (token-level) ──
    sim = difflib.SequenceMatcher(
        None, _tokenize(orig_name), _tokenize(cand_name)
    ).ratio()

    # ── model tokens ──
    orig_models = _model_tokens(orig_name)
    cand_models = _model_tokens(cand_name)
    model_overlap = orig_models & cand_models
    model_conflict = bool(orig_models and cand_models and not model_overlap)

    # ── spec conflicts — merge name-based with additionalProperties ──
    # Merchants like Flipkart omit color/size from the product name but expose
    # them as structured properties; without this merge those conflicts are invisible.
    orig_specs = _merge_product_specs(_extract_specs(orig_name), original)
    cand_specs = _merge_product_specs(_extract_specs(cand_name), candidate)

    color_conflict = bool(
        orig_specs["colors"] and cand_specs["colors"]
        and orig_specs["colors"] != cand_specs["colors"]
    )
    storage_conflict = bool(
        orig_specs["storages"] and cand_specs["storages"]
        and orig_specs["storages"] != cand_specs["storages"]
    )
    size_conflict = bool(
        orig_specs["sizes"] and cand_specs["sizes"]
        and orig_specs["sizes"] != cand_specs["sizes"]
    )

    if color_conflict:
        notes.append(
            f"Color: {'/'.join(sorted(orig_specs['colors']))} vs "
            f"{'/'.join(sorted(cand_specs['colors']))}"
        )
    if storage_conflict:
        notes.append(
            f"Storage: {'/'.join(sorted(orig_specs['storages']))} vs "
            f"{'/'.join(sorted(cand_specs['storages']))}"
        )
    if size_conflict:
        notes.append(
            f"Size: {'/'.join(sorted(orig_specs['sizes']))}\" vs "
            f"{'/'.join(sorted(cand_specs['sizes']))}\" inch"
        )
    if model_conflict:
        notes.append(
            f"Model: {'/'.join(orig_models)} vs {'/'.join(cand_models)}"
        )

    # ── Apple part-number conflict ──
    # MDHC4HN/A vs MDV94HN/A are different products; require exact code match
    # when both sides expose a code.
    orig_codes = _apple_codes(original)
    cand_codes = _apple_codes(candidate)
    if orig_codes and cand_codes and not (orig_codes & cand_codes):
        notes.append(
            f"Different variant/configuration "
            f"({', '.join(sorted(orig_codes))} vs {', '.join(sorted(cand_codes))})"
        )

    has_variant_diff = bool(notes)

    # ── Tier 2 classification ──
    if mpn_match or gtin_match:
        if has_variant_diff:
            return {"match_type": "Similar Match", "variant_notes": "; ".join(notes)}
        id_type = "MPN" if mpn_match else "GTIN"
        return _apply_condition(
            {"match_type": "Exact Match", "variant_notes": f"{id_type} verified"},
            original, candidate,
        )

    if brand_match and (sim >= 0.78 or model_overlap) and not model_conflict:
        if has_variant_diff:
            return {"match_type": "Similar Match", "variant_notes": "; ".join(notes)}
        tag = f"name sim {sim:.0%}"
        if model_overlap:
            tag += f"; model {', '.join(model_overlap)}"
        return _apply_condition(
            {"match_type": "Exact Match", "variant_notes": tag},
            original, candidate,
        )

    if brand_match and sim >= 0.60:
        notes.insert(0, f"name sim {sim:.0%}")
        return {"match_type": "Similar Match", "variant_notes": "; ".join(notes)}

    if sim >= 0.65:
        notes.insert(0, f"name sim {sim:.0%}, brand differs")
        return {"match_type": "Similar Match", "variant_notes": "; ".join(notes)}

    return {"match_type": "No Match", "variant_notes": f"low similarity ({sim:.0%})"}
