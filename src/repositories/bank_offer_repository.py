"""Bank card offers a store prints on its own product page — "HDFC Credit
Card: ₹6,000 off" — read as plain text, no AI.

Flipkart only for now (2026-10-26). Its product page lists the top bank
offers already worked out in rupees for that item, e.g. on the iPhone 17 Pro
(256 GB, ₹1,34,900):

    Bank offers
    Best value for you
    ₹6,000 off  Apply  HDFC           Credit Card
    ₹4,000 off  Apply  Flipkart Axis  Credit Card • Cashback
    ₹4,000 off  Apply  Flipkart SBI   Credit Card • Cashback
    Bank offers                       <- the EMI block that follows

Flipkart's markup is generated class names with no labels, so the offers are
read off the page's text in reading order rather than by element. Amazon
hides its list behind a click and blocks repeat reads; not covered yet.

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
