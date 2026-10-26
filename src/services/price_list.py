"""Plain shop price list for WhatsApp — the bot's copy of the website's
react/src/utils/priceList.js. Same rule, same order: when the gift card saves
too little to be worth the extra steps, the bot shows every shop cheapest
first (one swipeable card per shop) instead of a tiny "You save ₹40" with a
two-site how-to. Keep the two files in step.

Also draws the picture on each card (shop logo, price, a bar for how much
more it costs), since WhatsApp carousel cards need an image header from a
public web address — served by GET /wa/price-card.jpg.
"""
from __future__ import annotations

import io
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode, urlparse

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..config import get_settings
from ..constants import HYPERLOCAL_MERCHANTS

# Below either limit the gift card saving is too small to lead with.
MIN_GIFT_CARD_SAVING_RS = 100
MIN_GIFT_CARD_SAVING_PCT = 2

# Meta allows 2-10 cards per carousel.
MAX_CARDS = 10


def _is_hyperlocal(merchant: str) -> bool:
    m = (merchant or "").lower()
    return any(h in m for h in HYPERLOCAL_MERCHANTS)


def build_price_list(result: dict) -> list[dict]:
    """One row per shop, cheapest first; each row carries a route shaped like
    search_service.rank_routes' so its gift card can open the usual steps."""
    vouchers = {(v.get("merchant") or "").lower(): v for v in result.get("vouchers") or []}
    by_shop: dict[str, dict] = {}
    for r in result.get("results") or []:
        merchant, price = r.get("merchant"), r.get("price")
        if not merchant or not price:
            continue
        key = merchant.lower()
        if key in by_shop and by_shop[key]["price"] <= price:
            continue
        seller = (r.get("sellers") or [{}])[0] or {}
        v = vouchers.get(key)
        voucher_route = None
        if v:
            voucher_route = {
                "listed_price": price,
                "sellers": r.get("sellers") or [],
                "match_type": r.get("match_type") or "",
                "title": r.get("title") or "",
                "card_fomo": None,
                "merchant": f"{merchant} (in-store)" if v.get("offline_only") else merchant,
                "final_cost": (v.get("upi") or {}).get("effective_price"),
                "voucher": v,
            }
        by_shop[key] = {
            "merchant": merchant,
            "price": price,
            "link": seller.get("link"),
            "delivery": seller.get("delivery") or "",
            "hyperlocal": _is_hyperlocal(merchant),
            "voucher": v,
            "voucher_route": voucher_route,
        }

    def with_gift_card(s: dict) -> float:
        vr = s["voucher_route"]
        return vr["final_cost"] if vr and vr.get("final_cost") is not None else s["price"]

    return sorted(
        by_shop.values(),
        key=lambda s: (
            s["hyperlocal"], s["price"], with_gift_card(s),
            0 if re.match(r"free", s["delivery"], re.I) else 1,
        ),
    )


def should_show_price_list(shops: list[dict], rec: dict | None) -> bool:
    """At least two shops to compare, and the best gift card saves less than
    ₹100 or 2% against simply buying at the cheapest shop."""
    normal = [s for s in shops if not s["hyperlocal"]]
    if len(normal) < 2 or not rec:
        return False
    cheapest = normal[0]["price"]
    saving = cheapest - (rec.get("final_cost") or cheapest) if rec.get("voucher") else 0
    return saving < MIN_GIFT_CARD_SAVING_RS or saving / cheapest * 100 < MIN_GIFT_CARD_SAVING_PCT


def gift_card_saving(shop: dict) -> int:
    vr = shop.get("voucher_route")
    if not vr or vr.get("final_cost") is None:
        return 0
    return max(0, round(shop["price"] - vr["final_cost"]))


def short_delivery(text: str) -> str:
    """"Free delivery between Sat–Sun" → "Free, Sat–Sun"; keeps paid delivery visible."""
    if not text:
        return ""
    if text.startswith("Delivery ₹"):
        return f"+{text.removeprefix('Delivery ')} delivery"
    text = re.sub(r"^Free delivery between ", "Free, ", text)
    return re.sub(r"^Free next-day delivery$", "Free, next day", text)


def inr(amount: float) -> str:
    """₹1,23,456, Indian grouping like the website (en-IN)."""
    n = str(round(amount))
    head, tail = n[:-3], n[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return "₹" + ",".join(([head] if head else []) + groups + [tail])


def more_than(diff: float, cheapest: str) -> str:
    """"₹4,899 more than Amazon.in": a bare "+₹4,899" read as confusing."""
    return f"{inr(diff)} more than {cheapest or 'the cheapest'}"


def shop_host(link: str | None) -> str:
    try:
        return (urlparse(link or "").hostname or "").removeprefix("www.")
    except ValueError:
        return ""


def card_image_url(shop: dict, rank: int, best: float, priciest: float, cheapest_name: str) -> str:
    """Public address of this shop's card picture. Everything the picture
    shows travels in the address, so the server keeps nothing between the
    message and Meta fetching the image."""
    q = urlencode({
        "m": shop["merchant"], "h": shop_host(shop.get("link")),
        "p": round(shop["price"]), "b": round(best), "x": round(priciest), "r": rank, "c": cheapest_name,
    })
    return f"{get_settings().PUBLIC_BASE_URL}/wa/price-card.jpg?{q}"


# ── card picture ────────────────────────────────────────────────────────────

_FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
_W, _H = 800, 418  # 1.91:1, the shape WhatsApp shows link and card images at
# Website colours (react/src/theme/foundations/colors.js).
_BG, _TEXT, _TEXT3, _BRAND = "#FAFAF7", "#16202B", "#8A9089", "#1F3A5F"
_BAR_BG, _BAR, _BORDER = "#EFEDE5", "#CFCBBB", "#E6E4DD"
# Public id, same one the website sends (react/src/config.js).
_BRANDFETCH_CLIENT_ID = "1idlpu4MvGHZOo2yZmy"
_BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def _font(name: str, size: int, weight: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(_FONTS / name), size)
    if weight:
        try:
            f.set_variation_by_name(weight)
        except (OSError, ValueError):
            pass
    return f


@lru_cache(maxsize=512)
def _logo(host: str) -> Image.Image | None:
    """Same sources as the website, best first: Brandfetch's square icon
    (it only answers browser-like requests), then the site's favicon."""
    if not host:
        return None
    sources = [
        f"https://cdn.brandfetch.io/{host}/w/256/h/256/fallback/404/type/icon?c={_BRANDFETCH_CLIENT_ID}",
        f"https://www.google.com/s2/favicons?domain={host}&sz=128",
    ]
    for i, url in enumerate(sources):
        try:
            r = httpx.get(url, headers=_BROWSER, timeout=4.0, follow_redirects=True)
            if r.status_code >= 400 or not r.content or "image" not in r.headers.get("content-type", ""):
                continue
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            # Google answers unknown sites with a tiny grey globe; skip it.
            if i == 1 and img.width < 32:
                continue
            return img
        except Exception:
            continue
    return None


def _initials(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name or "")
    return "".join(w[0] for w in words[:2]).upper() or "?"


def render_price_card(merchant: str, host: str, price: int, best: int, priciest: int, rank: int, cheapest_name: str = "") -> bytes:
    img = Image.new("RGB", (_W, _H), _BG)
    d = ImageDraw.Draw(img)
    pad = 48

    # Logo on a white disc, like the website's list.
    size, lx, ly = 132, pad, 70
    d.ellipse((lx - 2, ly - 2, lx + size + 2, ly + size + 2), fill=_BORDER)
    d.ellipse((lx, ly, lx + size, ly + size), fill="#FFFFFF")
    logo = _logo(host)
    if logo is not None:
        # Brandfetch's icon fills the disc; a small favicon sits inside it.
        filled = logo.width >= 128
        inner = size if filled else 84
        logo = ImageOps.fit(logo, (inner, inner), Image.LANCZOS)
        alpha = logo.getchannel("A")
        if filled:
            circle = Image.new("L", (inner, inner), 0)
            ImageDraw.Draw(circle).ellipse((0, 0, inner - 1, inner - 1), fill=255)
            alpha = Image.composite(alpha, circle, circle)
        off = (size - inner) // 2
        img.paste(logo, (lx + off, ly + off), alpha)
    else:
        f = _font("hanken-grotesk-variable.woff2", 48, "Bold")
        t = _initials(merchant)
        tw, th = d.textbbox((0, 0), t, font=f)[2:]
        d.text((lx + (size - tw) / 2, ly + (size - th) / 2 - 6), t, font=f, fill=_BRAND)

    # Price, big; then how much more than the cheapest.
    x = lx + size + 40
    diff = price - best
    d.text((x, 62), inr(price), font=_font("IBMPlexMono-Bold.ttf", 88), fill=_TEXT)
    sub = more_than(diff, cheapest_name) if diff else ("Cheapest" if rank == 0 else "Same price")
    sub_font = _font("IBMPlexMono-Bold.ttf", 32)
    if d.textlength(sub, font=sub_font) > _W - pad - x:
        sub = more_than(diff, "the cheapest")
    d.text((x + 4, 176), sub, font=sub_font, fill=_TEXT3 if diff else _BRAND)

    # Bar: full and navy for the cheapest, grey and as long as the gap otherwise.
    span = (priciest - best) or 1
    by, bh = 300, 22
    d.rounded_rectangle((pad, by, _W - pad, by + bh), radius=bh // 2, fill=_BAR_BG)
    frac = max(0.06, diff / span) if diff else 1.0
    d.rounded_rectangle((pad, by, pad + (_W - 2 * pad) * frac, by + bh), radius=bh // 2, fill=_BAR if diff else _BRAND)

    if rank == 0 and not diff:
        f = _font("hanken-grotesk-variable.woff2", 26, "Bold")
        label = "CHEAPEST"
        tw = d.textbbox((0, 0), label, font=f)[2]
        d.rounded_rectangle((_W - pad - tw - 28, 30, _W - pad, 74), radius=8, fill=_BRAND)
        d.text((_W - pad - tw - 14, 36), label, font=f, fill="#FFFFFF")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()
