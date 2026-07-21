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

/** Final price the user pays: voucher effective price if a voucher exists, else listed. */
export function finalPrice(rec) {
  if (!rec) return null;
  const v = rec.voucher || null;
  return v ? round(v.upi?.effective_price) : round(rec.listed_price);
}

/** Original price: source price in URL mode (when present), else the listed price. */
export function originalPrice(result, rec) {
  const sourcePrice =
    result?.mode === 'url' && result?.source?.price ? round(result.source.price) : null;
  return sourcePrice || round(rec?.listed_price);
}

/** Amount saved. Prefers original−final; falls back to the voucher's own saving. */
export function saving(result, rec) {
  const fin = finalPrice(rec);
  const orig = originalPrice(result, rec);
  if (fin && orig && orig > fin) return orig - fin;
  const v = rec?.voucher || null;
  return v ? round(v.upi?.saving) : null;
}

/** What the buyer actually pays for the voucher itself (face value less UPI discount). */
export function paidForVoucher(v) {
  if (!v?.upi) return null;
  return Math.round(v.upi.voucher_amount * (1 - v.upi.pct / 100));
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
