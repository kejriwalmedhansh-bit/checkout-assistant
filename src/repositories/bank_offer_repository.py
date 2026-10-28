"""Bank card offers a store prints on its own product page — "HDFC Credit
Card: ₹6,000 off" — read as plain text, no AI.

Three stores (2026-10-28): Flipkart, Croma and Vijay Sales. Flipkart's
product page lists the top bank offers already worked out in rupees for that
item, e.g. on the iPhone 17 Pro (256 GB, ₹1,34,900):

    Bank offers
    Best value for you
    ₹6,000 off  Apply  HDFC           Credit Card
    ₹4,000 off  Apply  Flipkart Axis  Credit Card • Cashback
    ₹4,000 off  Apply  Flipkart SBI   Credit Card • Cashback
    Bank offers                       <- the EMI block that follows

Flipkart's markup is generated class names with no labels, so the offers are
read off the page's text in reading order rather than by element. Amazon
hides its list behind a click and blocks repeat reads; not covered yet.

Croma and Vijay Sales print each offer as a sentence instead ("Instant
discount of Rs.4000 on HDFC Bank Credit Card on minimum transaction amount of
Rs 54000", "Flat Rs.6000 Instant Discount on HDFC Bank Credit Card/Debit Card
EMI 6 Months and Above Tenures"); those are read by `offer_from_sentence`.

Owner's rules (2026-10-27):
  - EMI-only offers never count: the shopper pays in full.
  - A percentage with no rupee cap is never guessed at; it is left out.
  - Only banks the website's card picker knows are kept, and an offer tied to
    one particular card ("HSBC TAJ Credit Card") is left out, because a
    shopper who said "HSBC" need not hold that card.
  - Reward points (NeuCoins) are not a saving; cashback is.

Cashback offers count as a saving (owner's call 2026-10-26: "cashback is
cashback"); they are flagged so the shopper can be told it comes back later.
"""
from __future__ import annotations

import re

_TAG_RE = re.compile(r"<[^>]+>")
_SKIP_RE = re.compile(r"(?is)<(script|style|noscript)\b.*?</\1>")
_OFF_RE = re.compile(r"^₹\s?([\d,]+)\s+off$", re.IGNORECASE)
_CARD_RE = re.compile(r"\b(credit|debit)\s+card\b", re.IGNORECASE)
_SECTION = "bank offers"
# Text that ends the bank offer block if the second "Bank offers" heading
# is missing.
_SECTION_END = ("view emi offers", "additional benefits", "delivery details")


def _page_text(markup: str) -> list[str]:
    """The page's text pieces in reading order."""
    pieces = _TAG_RE.split(_SKIP_RE.sub(" ", markup))
    out = []
    for piece in pieces:
        text = re.sub(r"\s+", " ", piece.replace("&amp;", "&").replace("&nbsp;", " ")).strip()
        if text:
            out.append(text)
    return out


def flipkart_bank_offers(markup: str) -> list[dict]:
    """Bank offers from a Flipkart product page, best first:
    [{"bank": "HDFC", "card": "Credit Card", "saving": 6000.0,
      "cashback": False}, ...]. Empty when the page shows none."""
    text = _page_text(markup or "")
    try:
        start = next(i for i, t in enumerate(text) if t.lower() == _SECTION)
    except StopIteration:
        return []

    offers = []
    i = start + 1
    while i < len(text):
        t = text[i]
        if t.lower() == _SECTION or t.lower().startswith(_SECTION_END):
            break
        m = _OFF_RE.match(t)
        if m:
            # ₹X off, then "Apply", then the bank, then the card type.
            rest = [x for x in text[i + 1:i + 5] if x.lower() != "apply"]
            if len(rest) >= 2 and _CARD_RE.search(rest[1]):
                offers.append({
                    "bank": rest[0],
                    "card": _CARD_RE.search(rest[1]).group(0).title(),
                    "saving": float(m.group(1).replace(",", "")),
                    "cashback": "cashback" in rest[1].lower(),
                })
        i += 1
    offers.sort(key=lambda o: -o["saving"])
    return offers


# --- Offers written as sentences (Croma, Vijay Sales) -----------------------

# The banks the website's picker offers, with how the stores spell them. The
# stored name is what the picker matches on (react/src/utils/myCards.js).
_KNOWN_BANKS = [
    ("HDFC", r"hdfc"),
    ("ICICI", r"icici"),
    ("SBI", r"sbi|state bank of india"),
    ("Axis", r"axis"),
    ("Kotak", r"kotak(?: mahindra)?"),
    ("IDFC FIRST", r"idfc(?: first)?"),
    ("BOBCARD", r"bob|bobcard|bank of baroda"),
    ("HSBC", r"hsbc"),
    ("OneCard", r"onecard|one card"),
]
_BANK_PHRASE_RE = re.compile(
    r"\bon\s+(?P<bank>[A-Za-z][A-Za-z ]*?)\s+(?:bank\s+)?(?P<card>credit\s*card\s*/\s*debit\s*card|credit(?:\s+card)?|debit(?:\s+card)?)\b",
    re.IGNORECASE,
)
_MONEY = r"(?:rs\.?|inr|₹)\s?([\d,]+)"
_FLAT_RE = re.compile(r"(?:flat\s+)?" + _MONEY + r"(?:/-)?\s*(?:instant\s+)?(?:discount|off|cashback)", re.IGNORECASE)
_OF_RE = re.compile(r"(?:discount|cashback)\s+of\s+" + _MONEY, re.IGNORECASE)
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
_CAP_RE = re.compile(r"up\s*to\s+" + _MONEY, re.IGNORECASE)
_MIN_RE = re.compile(r"min(?:imum)?\.?\s+(?:transaction|purchase|order|cart)?\s*(?:amount|value)?\s*(?:of)?\s*" + _MONEY, re.IGNORECASE)
_EMI_RE = re.compile(r"\bemi\b", re.IGNORECASE)
_NOT_EMI_RE = re.compile(r"non[- ]?emi|full[- ]swipe", re.IGNORECASE)
_POINTS_RE = re.compile(r"neucoins?|reward|points|coins", re.IGNORECASE)


def _rupees(s: str) -> float:
    return float(s.replace(",", ""))


def _bank_name(phrase: str) -> str | None:
    """The picker's name for a bank phrase ("IDFC First" -> "IDFC FIRST"),
    or None when it is not a known bank or names one particular card
    ("HSBC TAJ", "Tata Neu SBI")."""
    words = phrase.strip().lower()
    for name, pattern in _KNOWN_BANKS:
        if re.fullmatch(pattern, words):
            return name
    return None


def offer_from_sentence(sentence: str, price: float | None) -> list[dict]:
    """The card offers one sentence describes for an item at `price`, in
    the Flipkart shape ({bank, card, saving, cashback}); [] when the
    sentence is not a counted offer (EMI-only, points, an uncapped %, an
    unknown bank, or a minimum the price does not reach). A "Credit
    Card/Debit Card" sentence gives one offer per card type."""
    text = re.sub(r"\s+", " ", (sentence or "").replace("&nbsp;", " ").replace("&amp;", "&")).strip()
    if not text:
        return []
    if _EMI_RE.search(text) and not _NOT_EMI_RE.search(text):
        return []
    if _POINTS_RE.search(text):
        return []
    m = _BANK_PHRASE_RE.search(text)
    if not m:
        return []
    bank = _bank_name(m.group("bank"))
    if bank is None:
        return []
    head = text[: m.start()]
    saving = None
    flat = _OF_RE.search(head) or _FLAT_RE.search(head)
    pct = _PCT_RE.search(head)
    if pct and (not flat or pct.start() < flat.start()):
        cap = _CAP_RE.search(head)
        if not cap or not price:
            return []  # never guess an uncapped percentage
        saving = min(float(pct.group(1)) * price / 100.0, _rupees(cap.group(1)))
    elif flat:
        saving = _rupees(flat.group(1))
    if not saving or saving <= 0:
        return []
    minimum = _MIN_RE.search(text)
    if minimum and price and price < _rupees(minimum.group(1)):
        return []
    card_text = m.group("card").lower()
    cards = ["Credit Card", "Debit Card"] if "/" in card_text else ["Credit Card" if card_text.startswith("credit") else "Debit Card"]
    cashback = "cashback" in text.lower()
    return [{"bank": bank, "card": card, "saving": round(saving), "cashback": cashback} for card in cards]


def _sentences_to_offers(sentences: list[str], price: float | None) -> list[dict]:
    seen, offers = set(), []
    for sentence in sentences:
        for offer in offer_from_sentence(sentence, price):
            key = (offer["bank"], offer["card"], offer["saving"], offer["cashback"])
            if key not in seen:
                seen.add(key)
                offers.append(offer)
    offers.sort(key=lambda o: -o["saving"])
    return offers


_CROMA_OFFER_RE = re.compile(r'class="bank-offers-text-pdp-carousel"[^>]*>(.*?)</span>', re.IGNORECASE | re.DOTALL)
_VIJAY_OFFER_RE = re.compile(r'<li\b[^>]*\binstant-discount-offer\b[^>]*>(.*?)</li>', re.IGNORECASE | re.DOTALL)


def croma_bank_offers(markup: str, price: float | None) -> list[dict]:
    """Bank offers from a Croma product page ("Super Savings" strip), best
    first, for an item at `price`."""
    sentences = [_TAG_RE.sub(" ", m) for m in _CROMA_OFFER_RE.findall(markup or "")]
    return _sentences_to_offers(sentences, price)


def vijay_sales_bank_offers(markup: str, price: float | None) -> list[dict]:
    """Bank offers from a Vijay Sales product page (the "Bank Offers" tab's
    list), best first, for an item at `price`. Each item's text sits before
    its "View Details" link, whose terms are long and not read."""
    sentences = [_TAG_RE.sub(" ", m.split("<span", 1)[0]) for m in _VIJAY_OFFER_RE.findall(markup or "")]
    return _sentences_to_offers(sentences, price)


# Which reader a store's product page gets, by link host.
STORE_READERS = {
    "flipkart.com": ("Flipkart", lambda markup, price: flipkart_bank_offers(markup)),
    "croma.com": ("Croma", croma_bank_offers),
    "vijaysales.com": ("Vijay Sales", vijay_sales_bank_offers),
}


def reader_for(link: str):
    """(store, reader) for a product page link on a store whose bank offers
    Dealo reads, else None. Only product pages (/p/) count."""
    from urllib.parse import urlsplit
    host = (urlsplit(link or "").hostname or "").lower()
    for domain, reader in STORE_READERS.items():
        if (host == domain or host.endswith("." + domain)) and "/p/" in (link or ""):
            return reader
    return None
