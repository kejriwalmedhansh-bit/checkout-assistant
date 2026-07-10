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
 * Clean the raw Gyftr redemption instructions for the "Before you buy" list:
 * drop empties, drop trailing "Important Instructions" headers, and drop
 * all-caps heading lines.
 */
export function cleanInstructions(list) {
  return (list || []).filter((i) => {
    const t = (i || '').trim();
    return t && !/Important Instructions\s*$/.test(t) && !/^[A-Z][A-Z\s&/-]+$/.test(t);
  });
}

/**
 * Affiliate wrapper. Identity passthrough for now — the single place to add
 * Cuelinks wrapping later (deliberately not applied to Gyftr voucher links).
 */
export function affiliateUrl(link) {
  return link || '#';
}
