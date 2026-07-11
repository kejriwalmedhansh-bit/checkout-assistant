/**
 * Presentation + derived-math helpers, ported from the legacy templates/index.html
 * render logic. Keeping the money math here means the route components read the
 * /search contract keys directly and never re-derive backend mechanics.
 */

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

// Cuelinks publisher cid (approved, live) — mirrors CUELINKS_BASE/CUELINKS_CID
// in src/constants.py + src/config.py. Not a secret: this id is already
// public in the wrapped URLs themselves.
const CUELINKS_CID = '297179';

/**
 * Affiliate wrapper for merchant store links — deliberately NOT applied to
 * Gyftr voucher links (callers should pass those through unwrapped).
 */
export function affiliateUrl(link) {
  if (!link) return '#';
  return `https://linksredirect.com/?cid=${CUELINKS_CID}&source=linkkit&url=${encodeURIComponent(link)}`;
}
