/**
 * Presentation + derived-math helpers, ported from the legacy templates/index.html
 * render logic. Keeping the money math here means the route components read the
 * /search contract keys directly and never re-derive backend mechanics.
 */
import { API_BASE_URL } from '@/config';

/** Format a number as INR: '₹' + thousands-separated, rounded. `—` when empty. */
export function fmt(n) {
  if (n == null || n === '') return '—';
  return '₹' + Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

const round = (n) => (n == null ? null : Math.round(n));

/** Final price the user pays: voucher effective price if a voucher exists, else listed.
 * `payingByCard` reads the voucher's card-rate figures instead of UPI's — Gyftr/Maximize
 * give a lower discount when the voucher itself is paid for by card, so this is a genuinely
 * different (not just relabeled) number once the shopper says they're paying by card. */
export function finalPrice(rec, payingByCard = false) {
  if (!rec) return null;
  const v = rec.voucher || null;
  if (!v) return round(rec.listed_price);
  const priceSet = payingByCard ? v.card : v.upi;
  return round(priceSet?.effective_price);
}

/** Original price: source price in URL mode (when present), else the listed price. */
export function originalPrice(result, rec) {
  const sourcePrice =
    result?.mode === 'url' && result?.source?.price ? round(result.source.price) : null;
  return sourcePrice || round(rec?.listed_price);
}

/** Amount saved. Prefers original−final; falls back to the voucher's own saving. */
export function saving(result, rec, payingByCard = false) {
  const fin = finalPrice(rec, payingByCard);
  const orig = originalPrice(result, rec);
  if (fin && orig && orig > fin) return orig - fin;
  const v = rec?.voucher || null;
  if (!v) return null;
  const priceSet = payingByCard ? v.card : v.upi;
  return round(priceSet?.saving);
}

/** The cashback ₹ figure that actually applies for a selected card's quote
 * (see CreditCardPrompt/card_service.get_card_quote) — `direct_cashback`
 * when the route is skipping the voucher for this card (`skip_voucher`),
 * else the voucher-funded `cashback`. Single source of truth so the
 * top savings box and the card's own cashback tile can never disagree. */
export function effectiveCashback(quote) {
  if (!quote) return 0;
  return (quote.skip_voucher ? quote.direct_cashback ?? quote.cashback : quote.cashback) || 0;
}

/** What the buyer actually pays for the voucher itself (face value less the applicable
 * discount — UPI's or, once a card is picked, the card rate's, per `payingByCard`). The
 * face value itself (`voucher_amount`) doesn't depend on payment method, so it's always
 * read from `v.upi` — only the discount % differs between the two. */
export function paidForVoucher(v, payingByCard = false) {
  if (!v?.upi) return null;
  const pct = (payingByCard ? v.card?.pct : v.upi.pct) ?? v.upi.pct;
  return Math.round(v.upi.voucher_amount * (1 - pct / 100));
}

/**
 * Clean raw Gyftr redemption instructions: drop empties, trailing "Important
 * Instructions" headers, and all-caps heading lines. Only still needed for
 * VoucherDetailPage, which reads straight from voucher_repository (raw data)
 * — the route-building path (HowToSteps) gets pre-cleaned data straight from
 * voucher_service.py::_clean_instructions() now, the single source of truth
 * for both web and WhatsApp there.
 */
export function cleanInstructions(list) {
  return (list || []).filter((i) => {
    const t = (i || '').trim();
    return t && !/Important Instructions\s*$/.test(t) && !/^[A-Z][A-Z\s&/-]+$/.test(t);
  });
}

/**
 * Affiliate wrapper for merchant store links — deliberately NOT applied to
 * Gyftr voucher links (callers should pass those through unwrapped).
 *
 * Routes through our own backend (/go, see src/api/routers/redirect.py)
 * instead of linking straight to linksredirect.com, so hovering the link
 * shows our domain, not an unfamiliar third-party tracking redirect. The
 * backend does the actual Cuelinks wrap and 302s onward.
 */
export function affiliateUrl(link) {
  if (!link) return '#';
  return `${API_BASE_URL}/go?url=${encodeURIComponent(link)}`;
}
