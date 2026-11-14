/**
 * Presentation + derived-math helpers, ported from the legacy templates/index.html
 * render logic. Keeping the money math here means the route components read the
 * /search contract keys directly and never re-derive backend mechanics.
 */
import { shopLink } from '@/utils/analytics';

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
 * Merchant store link through the backend's /go redirect (see
 * src/api/routers/redirect.py): logs the click, wraps it for commission and
 * stamps the visitor's id on it. Voucher-partner links use outboundLink.
 * `ctx` names where on the page the link sits.
 */
export function affiliateUrl(link, ctx) {
  return shopLink(link, ctx);
}

/** A listing title as people would write it: some shops (BigBasket) put
 * the brand in front of a title that already starts with it ("Apple Apple
 * iPhone 17 Pro … 1 Unit"). Drops the repeated opening words and a
 * trailing "1 Unit" / "1 pc"; leaves real pack sizes ("2 Units") alone. */
export function tidyTitle(title) {
  let t = (title || '').trim();
  const words = t.split(/\s+/);
  for (let n = Math.min(3, Math.floor(words.length / 2)); n >= 1; n -= 1) {
    const head = words.slice(0, n).join(' ').toLowerCase();
    if (words.slice(n, 2 * n).join(' ').toLowerCase() === head) {
      t = words.slice(n).join(' ');
      break;
    }
  }
  return t.replace(/\s+1\s*(unit|pc|pcs|piece)\.?$/i, '');
}
