"""Exact-product matching for pasted links.

A pasted link names ONE product. This module reads that product's "ID card"
from the page title (brand, model codes, name words, size/storage/pack) and
sorts every search listing into three tiers:

  exact   - same brand and model; nothing contradicts the ID card
  similar - same model, but a different size / storage / pack / bundle
  wrong   - a different model, sub-model, product type or brand

Search wide, show strict: the search step may return look-alikes, but only
`exact` listings can lead the picker, `similar` ones are labelled, and `wrong`
ones are never shown. Rules are general (codes, modifiers, units), never
per-product.
"""

from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

# Words that describe, market or position a product without naming it.
# Listing titles add or drop these freely, so they never decide a match.
_GENERIC = set("""
a an the and or with for of in on at by to from as is it this that
new all latest best original genuine official premium edition series model version
buy online price india sale offer deal deals shop store
men mens man women womens woman unisex boys girls adult adults
wireless wired bluetooth true truly active noise cancelling canceling cancellation
over ear in-ear on-ear headphone earphone mic calling clear hands free
smart digital analog analogue electric electronic automatic portable compact size
fast charging charge charger battery life playback hours hrs hour days
display amoled screen touch panel button push control controls
face power oil control induction ceiling table wall pedestal gen generation water resistant waterproof dustproof sweat proof ipx4 ipx5 ipx7 ip67 ip68
stainless steel steels metal leather plastic rubber mesh nylon cotton blend fabric
slim fit regular relaxed tapered straight skinny mid rise low high waist stretch stretchable
casual sports sport running walking training trainer gym everyday daily lace up
dark light solid plain printed textured colour color colours colors assorted
stereo sound audio bass drivers driver voice assistant ai app support
performance quiet clicks ergo ultra-fast scrolling track glass
multipurpose multi purpose use home kitchen travel office college school
long lasting lightweight light-weight heavy duty quality
spf pa broad spectrum hydrating non sticky no white cast skin normal dry oily
5g 4g lte sim ram storage expandable phone mobile smartphone
jars jar compartment compartments pieces piece pcs blades speeds
""".split())

_COLOURS = set("""
black white blue red green yellow purple pink gold golden silver grey gray
titanium graphite midnight starlight rose orange beige brown teal navy coral
indigo maroon olive khaki cream ivory charcoal mint lavender peach
multicolor multicolour camo tan nude
""".split())

# Product-type nouns. Not identity on their own, but a listing of another
# type (a hair mask for a conditioner) is a different product.
_TYPE_WORDS = set("""
headphones headset earbuds buds earphones neckband speaker soundbar
watch smartwatch band tracker phone laptop tablet kindle e-reader ereader mouse keyboard
trimmer shaver groomer dryer straightener
mixer grinder juicer blender kettle cooktop cooker fryer airfryer oven toaster fan cooler purifier conditioner
bank powerbank cable adapter
shoes shoe sneakers sneaker sandals slippers boots flip-flops
jeans shirt tshirt t-shirt polo tee trousers shorts jacket hoodie sweatshirt dress kurta
backpack bag rucksack wallet suitcase trolley
serum sunscreen cleanser wash facewash moisturiser moisturizer cream lotion gel
shampoo conditioner mask foundation primer powder lipstick kajal eyeliner mascara
""".split())

# Words that turn one model into a sibling model. If the pasted product has
# one and a listing doesn't (or the reverse), they are different products.
_MODIFIERS = set("""
plus pro max mini ultra lite neo turbo deco elite edge fe prime air slip
kids junior jr refurbished renewed business signature
""".split())

_UNIT = (r"(?:gb|tb|mb|ml|l|ltr|ltrs|litre|litres|liter|liters|g|gm|gms|kg|mah|w|watt|watts|v|mm|cm|inch|in|"
         r"hz|db|ms|dpi|mp|h|hr|hrs|hours|nits|core|%|compartments?|jars?|pieces|pcs|blades?|speeds?|"
         r"burners?|layers?|stars?|months?|years?|yrs?|days?)")
_SPEC_RE = re.compile(r"(?<![a-z0-9.])\d+(?:\.\d+)?\s*" + _UNIT + r"(?![a-z0-9])"
                      r"|\b(?:spf|ipx|ip|pa)(?![a-z])\s*\d*\+*")
_HEAD_CUT_RE = re.compile(r"\s*(?:,|\||\(|\[|:| with | for | - | – |/\s)", re.IGNORECASE)
_BRAND_ALIASES = {"mi": {"mi", "xiaomi", "redmi"}, "xiaomi": {"mi", "xiaomi"}, "levis": {"levis", "levi"}}
_STORE_JUNK_RES = [
    re.compile(r"^\s*(?:amazon\.in|flipkart\.com|flipkart)\s*:\s*", re.I),
    re.compile(r"^\s*(?:buy|shop)\s+", re.I),
    re.compile(r"\s+-\s+buy\s+.*$", re.I),
    re.compile(r"\s+(?:online\s+)?at\s+(?:low|best)\s+prices?.*$", re.I),
    re.compile(r"\s+online\s+at\s+.*$", re.I),
    re.compile(r"\s+(?:price\s+in\s+india).*$", re.I),
    re.compile(r"\s+at\s+(?:reliance digital|croma|vijay sales|nykaa|amazon\.in)\s*$", re.I),
]


_AIR_PHRASE_RE = re.compile(r"\bair[\s\-]+(?=(?:fryer|purifier|cooler|conditioner|force|jordan|max)\b)")


def _norm(s: str) -> str:
    s = (s or "").lower().replace("’", "'")
    s = _AIR_PHRASE_RE.sub("air", s)            # "air fryer" -> "airfryer", not the "Air" sub-model
    s = re.sub(r"(?<=[a-z])'s\b", "", s)          # men's -> men
    s = re.sub(r"(?<=\d)''|″|”", " inch", s)
    s = re.sub(r"[^a-z0-9.%+/\-\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?%?", _norm(s))


def _compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def clean_title(title: str) -> str:
    t = re.sub(r"\s+", " ", title or "").strip()
    for rx in _STORE_JUNK_RES:
        t = rx.sub("", t).strip()
    return t


def _tokens(s: str) -> list[str]:
    """Words with model codes kept whole ("wh-1000xm5", "a-158wa-1q"); a
    hyphenated plain word ("lace-up", "all-new") splits into its parts."""
    out = []
    for t in re.findall(r"[a-z0-9](?:[a-z0-9.%\-]*[a-z0-9%])?", _norm(s)):
        if "-" in t and not any(c.isdigit() for c in t):
            out += [p for p in t.split("-") if p]
        else:
            out.append(t)
    return out


def _slug_words(url: str | None) -> list[str]:
    if not url:
        return []
    best: list[str] = []
    for seg in urlsplit(url).path.split("/"):
        ws = re.findall(r"[a-z0-9]+", unquote(seg).lower())
        if len(ws) < 3:     # a lone id segment (ASIN, Flipkart itm id)
            ws = [w for w in ws if not (len(w) >= 9 and any(c.isdigit() for c in w))]
        if sum(1 for w in ws if not w.isdigit() and len(w) >= 3) > sum(1 for w in best if not w.isdigit() and len(w) >= 3):
            best = ws
    # "pic-20-0" in a slug is "PIC 20.0" with the dot turned into a dash.
    joined = re.sub(r"\b(\d+) (0)\b", r"\1.\2", " ".join(best))
    return joined.split()


def _is_code(w: str) -> bool:
    """A model code: has a digit and isn't a spec (150ml, 16gb, 5g, 2x)."""
    if not any(c.isdigit() for c in w) or w in _GENERIC:
        return False
    if re.fullmatch(r"(?:[1-9]|10)x", w):      # "2x zoom"; "70x" is a model
        return False
    return not re.fullmatch(r"\d+(?:\.\d+)?" + _UNIT, w)


def _code_pattern(code: str) -> str:
    """Regex for a code that tolerates separators between its letter/digit
    runs (WH-1000XM5 = WH1000XM5) and a trailing region suffix (A158WA-1DF
    for A158WA), but not a different number (BT3221 != BT3201)."""
    code = re.sub(r"\.0$", "", code)
    runs = re.findall(r"[a-z]+|\d+(?:\.\d+)?|%", code)
    body = r"[\s\-./]?".join(re.escape(r) for r in runs)
    end = r"(?![0-9])" if code[-1].isdigit() else ""
    if code.replace(".", "").isdigit():
        end = r"(?:\.0)?(?![a-z0-9])"   # "450" must not match "4500" or "450r"
    return r"(?<![a-z0-9])" + body + end


def _variants(title: str) -> dict:
    n = _norm(title)
    out: dict = {}
    ram = re.search(r"(\d+)\s*gb\s*ram", n)
    if ram:
        out["ram"] = int(ram.group(1))
    storage = [int(g) * (1024 if u == "tb" else 1) for g, u in re.findall(r"(\d+)\s*(gb|tb)(?!\s*ram)", n)]
    storage = [s for s in storage if s != out.get("ram")]
    if "ram" not in out and len(set(storage)) >= 2:
        out["ram"] = min(storage)            # "12GB, 256GB" / "8GB/128GB": the smaller is RAM
    if storage:
        out["storage"] = max(storage)
    vol = re.search(r"(\d+(?:\.\d+)?)\s*(ml|l|ltr|ltrs|litre|litres|liter|liters)(?![a-z])", n)
    if vol:
        v = float(vol.group(1)) * (1 if vol.group(2) == "ml" else 1000)
        out["volume"] = round(v)
    wt = re.search(r"(\d+(?:\.\d+)?)\s*(g|gm|gms|kg)(?![a-z])", n)
    if wt and not (wt.group(2) == "g" and wt.group(1) in ("2", "3", "4", "5")):
        out["weight"] = round(float(wt.group(1)) * (1000 if wt.group(2) == "kg" else 1))
    material = re.search(r"stainless|alumin(?:i)?um|hard[\s\-]*anodi[sz]ed|cast iron|tri[\s\-]*ply|triply", n)
    if material:
        m = material.group(0)
        out["material"] = ("stainless" if "stainless" in m else "anodised" if "anodi" in m
                           else "aluminium" if "alumin" in m else re.sub(r"\W", "", m))
    gen = re.search(r"\b(\d+)(?:st|nd|rd|th)\s*gen|\bgen(?:eration)?\s*(\d+)\b", n)
    if gen:
        out["generation"] = int(gen.group(1) or gen.group(2))
    strength = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", n)
    if strength:
        out["strength"] = float(strength.group(1))
    mah = re.search(r"(\d{4,6})\s*mah", n)
    if mah:
        out["mah"] = int(mah.group(1))
    pack = re.search(r"(?:pack|set)\s+of\s+(\d+)|(\d+)\s*(?:pcs|pieces)\b", n)
    if pack:
        out["pack"] = int(pack.group(1) or pack.group(2))
    if re.search(r"\b(?:combo|kit|bundle|duo|trio|\d\s*items|set of|each)\b", n) or re.search(r"\s(?:&|\+|and)\s+(?:" + "|".join(sorted(_TYPE_WORDS)) + r"|[a-z]+\s+(?:" + "|".join(sorted(_TYPE_WORDS)) + r"))\b", n):
        out["bundle"] = True
    return out


def _second_product(ident: dict, title: str) -> bool:
    """A different model code after "&"/"+"/"and" ("Mixer Grinder HL7756 &
    Classic GC097/50 Dry Iron") means two products in one listing. The
    product's own model number repeated there doesn't count."""
    own = {_compact(c) for c in ident["codes"]} | {_compact(a) for alts in ident["alt_codes"] for a in alts}
    for tail in re.findall(r"(?:&|\+|\band\b)\s+([^,|()]*)", (title or "").lower()):
        for t in _tokens(tail):
            c = _compact(_strip_region(t))
            if re.search(r"[a-z]", t) and re.search(r"\d", t) and _is_code(t) and len(c) >= 4 and c not in own:
                return True
    return False


_SKIP_LEAD = {"all", "new", "the", "buy", "shop", "original", "genuine", "latest"}


def _slug_title(slug: list[str]) -> str:
    """A product name from a web address's words: re-join model numbers the
    dashes split ("ga 2100 1a1dr" -> "ga-2100-1a1dr", "6 69 inch" -> "6.69
    inch"), and stop at the spec dump that follows the name ("samsung galaxy
    s24 fe | 5g dual sim smartphone 8gb ... exynos 2400e")."""
    out: list[str] = []
    i = 0
    while i < len(slug):
        w = slug[i]
        if re.fullmatch(r"[a-z]{1,3}", w) and i + 1 < len(slug) and slug[i + 1].isdigit() and len(slug[i + 1]) >= 3:
            w = f"{w}-{slug[i + 1]}"
            i += 1
            while i + 1 < len(slug) and re.fullmatch(r"(?=.*\d)[a-z0-9]{1,6}", slug[i + 1]) and not _SPEC_RE.fullmatch(slug[i + 1]):
                w += "-" + slug[i + 1]
                i += 1
        elif w.isdigit() and i + 1 < len(slug) and slug[i + 1].isdigit() and len(slug[i + 1]) <= 2 and i + 2 < len(slug) and slug[i + 2] in ("inch", "in", "cm"):
            w = f"{w}.{slug[i + 1]}"
            i += 1
        out.append(w)
        i += 1
    for k in range(3, len(out)):
        if out[k] in _GENERIC or out[k] in _TYPE_WORDS or out[k] in _COLOURS:
            return " ".join(out[:k + (1 if out[k] in _TYPE_WORDS else 0)])
    return " ".join(out)


def _strip_region(code: str) -> str:
    """A158WA-1Q -> A158WA; BT3221/15 -> BT3221. Keeps WH-1000XM5 whole."""
    m = re.fullmatch(r"(.+?)[\-/]([a-z0-9]{1,3})", code)
    if m and len(_compact(m.group(1))) >= 4 and any(c.isdigit() for c in m.group(1)):
        return m.group(1)
    return code


def build_identity(title: str, url: str | None = None) -> dict:
    """The pasted product's ID card, from its page title plus its URL slug."""
    title = clean_title(title)
    slug = _slug_words(url)
    distinct = lambda ws: {w for w in ws if w not in _GENERIC and w not in _COLOURS and len(w) > 2}
    # A storefront's own generic title ("Oneplus Smartphones Online at Best
    # Price") shares almost nothing with the product's slug - use the slug.
    if (len(distinct(slug)) >= 3 and len(distinct(slug) & distinct(_tokens(title))) <= 1
            and not any(_is_code(w) for w in _tokens(_SPEC_RE.sub(" ", _norm(title))))):
        title = _slug_title(slug)
    head = _HEAD_CUT_RE.split(title, maxsplit=1)[0]
    if len(_tokens(head)) < 2:                      # a title that starts "(...)"
        head = " ".join(_tokens(title)[:8])
    head_n = _SPEC_RE.sub(" ", _norm(head))
    toks = [t for t in _tokens(head_n) if t not in _SKIP_LEAD or _tokens(head_n).index(t) > 2]
    brand = toks[0] if toks else ""
    ordered: list[tuple[str, str]] = []             # (word, kind) in title order
    alt_codes: list[set] = []
    alt_seen = set()
    for m in re.finditer(r"(?<![a-z0-9])([a-z0-9.\-]+)/([a-z0-9.\-]+)(?![a-z0-9])", head_n):
        a, b = m.groups()
        if _is_code(a) and _is_code(b) and not (b.isdigit() and len(b) <= 2):
            alt_codes.append({a, b})
            alt_seen |= {a, b}
    for w in toks[1:]:
        if w == brand or w in alt_seen:
            continue
        if _is_code(w):
            ordered.append((_strip_region(w), "code"))
        elif w in _MODIFIERS:
            ordered.append((w, "mod"))
        elif w in _TYPE_WORDS:
            ordered.append((w, "type"))
        elif w not in _GENERIC and w not in _COLOURS and not w.isdigit():
            ordered.append((w, "name"))
    # A region suffix split off by "/" ("BT3221/15") is not a model number.
    codes = [w for w, k in ordered if k == "code" and not re.fullmatch(r"\d{1,2}", w)
             or (k == "code" and not re.search(r"/" + re.escape(w) + r"\b", head_n))]
    codes = list(dict.fromkeys(c for c in codes if not re.search(r"[a-z0-9]{3,}/" + re.escape(c) + r"(?![a-z0-9])", head_n)))
    # Model numbers only the slug names (Flipkart titles often drop them:
    # "Prestige 1600 W Induction Cooktop" for the PIC 20.0).
    slug_name = []
    if not codes and not alt_codes and slug:
        slug_n = _SPEC_RE.sub(" ", " ".join(slug))
        st = slug_n.split()
        for i, w in enumerate(st):
            if _is_code(w) and "percent" not in w and _compact(w) not in _compact(head):
                if w.isdigit():         # a bare catalogue number: confirms, never rejects
                    continue
                codes.append(_strip_region(w))
                if i and st[i - 1] not in _GENERIC and not _is_code(st[i - 1]) and st[i - 1] != brand:
                    slug_name.append(st[i - 1])
    name = [w for w, k in ordered if k == "name"] + [w for w in slug_name if w not in _compact(head)]
    # With a short model number ("Rockerz 450", "Galaxy A56", "Flip 6") the
    # line name right before it is part of the identity; a long code
    # ("WH-1000XM5", "BT3221") identifies the product on its own.
    # Catalogue and store codes (SM-R630NZWAINU, a shop's own G987) are proof
    # when a listing carries them, never a reason to reject one that doesn't:
    # other sellers name the product by its everyday model name instead.
    soft = [c for c in codes if len(_compact(c)) >= 10]
    if len(codes) > 1:
        first = codes[0]
        soft += [c for c in codes[1:] if c not in soft and re.fullmatch(r"[a-z]{0,2}\d{3,}[a-z]?", _compact(c))
                 and _compact(c) not in _compact(first)]
    codes = [c for c in codes if c not in soft] or codes[:1]
    strong = any(len(_compact(c)) >= 5 and re.search(r"[a-z]", c) and re.search(r"\d", c) for c in codes)
    if codes or alt_codes:
        first = next((i for i, (w, k) in enumerate(ordered) if k == "code" or w in alt_seen), len(ordered))
        line = [w for w, k in ordered[:first] if k == "name"][-2:]
        required = [] if strong else (line + [w for w in slug_name if w not in line])
    else:
        required = name
    return {
        "title": title, "brand": brand, "codes": codes, "alt_codes": alt_codes, "soft_codes": soft,
        "name": required, "all_name": name, "types": [w for w, k in ordered if k == "type"],
        "modifiers": [w for w, k in ordered if k == "mod"], "variants": _variants_with_slug(title, slug),
        "audience": _audience(title), "ordered": ordered,
    }


def _variants_with_slug(title: str, slug: list[str]) -> dict:
    """Size/storage/pack from the title, with anything it leaves out taken
    from the link's own web address ("...-galaxy-s25-5g-mint-128-gb")."""
    out = _variants(title)
    for k, v in _variants(" ".join(slug)).items():
        out.setdefault(k, v)
    return out


def _audience(title: str) -> str | None:
    n = " " + _norm(title) + " "
    if re.search(r"\b(kids|boys|girls|junior|infant|baby)\b", n):
        return "kids"
    if re.search(r"\b(women|womens|woman|ladies)\b", n):
        return "women"
    if re.search(r"\b(men|mens|man)\b", n):
        return "men"
    return None


def identity_query(ident: dict) -> str:
    """Short search text in title order: brand, line and model, product type.
    Words after the model number are description and are left out."""
    ordered = ident["ordered"]
    anchors = set(ident["codes"]) | set().union(*ident["alt_codes"]) if ident["alt_codes"] else set(ident["codes"])
    last = max((i for i, (w, _) in enumerate(ordered) if w in anchors), default=len(ordered) - 1)
    parts = [ident["brand"]]
    parts += [w for w, k in ordered[: last + 1] if k in ("name", "mod") or w in ident["codes"]]
    parts += [sorted(a, key=len)[0] for a in ident["alt_codes"]]
    parts += [w for w in ident["name"] + ident["codes"] if w not in parts]
    types = [w for w, k in ordered if k == "type"]
    if types:
        parts.append(types[-1])
    if "storage" in ident["variants"]:
        parts.append(f"{ident['variants']['storage']}GB")
    return " ".join(dict.fromkeys(p for p in parts if p))


def _has_word(word: str, words: set, compact: str) -> bool:
    if word in words or (word.endswith("s") and word[:-1] in words) or word + "s" in words:
        return True
    return len(word) >= 4 and word in compact


def match_tier(ident: dict, title: str, source: str = "") -> tuple[str, str]:
    """('exact' | 'similar' | 'wrong', short reason)."""
    n = _norm(title)
    head = _norm(_HEAD_CUT_RE.split(clean_title(title), maxsplit=1)[0])
    words = set(_words(title)) | set(_tokens(title))
    compact = _compact(title)
    brand = ident["brand"]
    if brand:
        names = _BRAND_ALIASES.get(brand, {brand})
        if not any(_has_word(b, words, compact) or b in _compact(source) for b in names):
            return "wrong", "brand"
    for code in ident["codes"]:
        if not re.search(_code_pattern(code), n):
            return "wrong", f"model {code}"
    for alts in ident["alt_codes"]:
        if not any(re.search(_code_pattern(a), n) for a in alts):
            return "wrong", f"model {'/'.join(sorted(alts))}"
    missing = [w for w in ident["name"] if not _has_word(w, words, compact)]
    if missing:
        return "wrong", f"name {missing[0]}"
    if ident["types"] and not (ident["codes"] or ident["alt_codes"]):
        if not any(_has_word(t, words, compact) for t in ident["types"]):
            return "wrong", "product type"
    head_words = set(_tokens(head))
    for m in _MODIFIERS:
        if (m in head_words) != (m in ident["modifiers"]):
            if m in ident["modifiers"] and m in words:
                continue
            return "wrong", f"sub-model '{m}'"
    # Editions sold as separate products: "for Mac", "for Business", and a
    # noise-cancelling version of a product whose own page never mentions it.
    ident_n = _norm(ident["title"])
    for ed in re.findall(r"\bfor (mac|business|ipad|iphone)\b", n):
        if not re.search(r"\bfor " + ed + r"\b", ident_n):
            return "wrong", f"edition 'for {ed}'"
    if bool(re.search(r"bluetooth edition", n)) != bool(re.search(r"bluetooth edition", ident_n)):
        return "wrong", "Bluetooth Edition"
    # Noise cancelling (ANC) is its own edition: both sides mention it or
    # neither does. The mic-only "ENx" noise cancellation doesn't count.
    anc = r"active noise cancel|\banc\b"
    ident_head = _norm(_HEAD_CUT_RE.split(ident["title"], maxsplit=1)[0])
    if re.search(anc, n) and not re.search(anc + r"|noise cancel", ident_n):
        return "wrong", "noise-cancelling edition"
    if re.search(r"\banc\b", ident_head) and not re.search(anc + r"|noise cancel", n):
        return "wrong", "not the noise-cancelling edition"
    aud = _audience(title)
    if ident["audience"] and aud and aud != ident["audience"] and "unisex" not in words:
        return "wrong", "audience"
    nxt = _word_after_model(ident, n)
    if nxt:
        return "wrong", f"sub-model '{nxt}'"
    cv, iv = _variants(title), ident["variants"]
    if "generation" in cv and "generation" in iv and cv["generation"] != iv["generation"]:
        return "wrong", "generation"
    if "strength" in cv and "strength" in iv and cv["strength"] != iv["strength"]:
        return "wrong", "strength"
    if "material" in cv and "material" in iv and cv["material"] != iv["material"]:
        return "wrong", "material"
    # Multi-packs always say so; a listing that doesn't is a single.
    if cv.get("pack", 1) != iv.get("pack", 1):
        return "similar", "pack"
    for k in ("storage", "ram", "volume", "weight", "mah"):
        if k in cv and k in iv and cv[k] != iv[k]:
            # A brand's repackaging (Cetaphil 125 ml -> 118 ml) is the same
            # product; 250 ml vs 125 ml is not.
            if k in ("volume", "weight") and abs(cv[k] - iv[k]) <= 0.07 * max(cv[k], iv[k]):
                continue
            return "similar", k
    if _second_product(ident, title) and not _second_product(ident, ident["title"]):
        return "similar", "bundle"
    if cv.get("bundle") != iv.get("bundle") and (cv.get("bundle") or iv.get("bundle")):
        return "similar", "bundle"
    return "exact", ""


def _word_after_model(ident: dict, n: str) -> str | None:
    """The word right after the model name, when it names a sibling model:
    'Go Walk Flex Remark', 'PIC 20 WIZ', 'Purifying Neem Foaming Face Wash'."""
    anchors = [_code_pattern(c) for c in ident["codes"]]
    anchors += ["(?:" + "|".join(_code_pattern(a) for a in alts) + ")" for alts in ident["alt_codes"]]
    anchors += [r"(?<![a-z0-9])" + re.escape(w) + r"s?(?![a-z0-9])" for w in ident["name"]]
    end = -1
    for a in anchors:
        m = re.search(a, n)
        if m:
            end = max(end, m.end())
    if end < 0:
        return None
    known = set(ident["name"]) | set(ident["codes"]) | set(ident["types"]) | set(ident["modifiers"]) | {ident["brand"]}
    for w in re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", n[end:])[:1]:
        if (w in known or w == "anc" or w in _GENERIC or w in _COLOURS or w in _TYPE_WORDS or w in _MODIFIERS
                or re.fullmatch(r"\d+(?:\.\d+)?", w) or re.fullmatch(r"\d+(?:\.\d+)?" + _UNIT, w)
                or (len(w) <= 3 and any(c.isdigit() for c in w))    # region suffix "1df"
                or re.fullmatch(r"\d+(?:st|nd|rd|th)", w)
                or len(w) <= 2):
            return None
        return w
    return None
