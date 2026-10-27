/**
 * Plain price comparison across shops, built from the same /routes response
 * the voucher view reads (`results` = every verified shop listing,
 * `vouchers` = the gift card deal per shop). Used when a gift card isn't
 * worth the extra steps, so the screen becomes "cheapest shop first"
 * instead of a tiny "You save ₹40" with a two-step how-to.
 */
import { BRANDFETCH_CLIENT_ID } from '@/config';
import AMAZON_BANK_OFFERS from '@/data/amazonBankOffers.json';

// Below either limit the gift card saving is too small to lead with.
export const MIN_GIFT_CARD_SAVING_RS = 100;
export const MIN_GIFT_CARD_SAVING_PCT = 2;

// Mirrors HYPERLOCAL_MERCHANTS in src/constants.py: quick-commerce apps rank
// after every normal shop whatever the price, same as the route ranking.
const HYPERLOCAL = ['blinkit', 'zepto', 'swiggy', 'zomato', 'instamart', 'bigbasket', 'nykaa now', 'mnow'];
const isHyperlocal = (merchant) => HYPERLOCAL.some((m) => (merchant || '').toLowerCase().includes(m));

/** One row per shop, cheapest first; each row carries a route object shaped
 * like search_service.rank_routes' so it can open the normal voucher view. */
export function buildPriceList(result, cardOffers = []) {
  const vouchers = new Map((result?.vouchers || []).map((v) => [v.merchant.toLowerCase(), v]));
  const cards = new Map((cardOffers || []).filter((c) => c.offers?.length).map((c) => [c.store.toLowerCase(), c.offers]));
  const byShop = new Map();
  for (const r of result?.results || []) {
    if (!r.merchant || !r.price) continue;
    const key = r.merchant.toLowerCase();
    if (byShop.has(key) && byShop.get(key).price <= r.price) continue;
    const seller = (r.sellers || [])[0] || {};
    const v = vouchers.get(key) || null;
    const base = {
      listed_price: r.price,
      sellers: r.sellers || [],
      match_type: r.match_type || '',
      title: r.title || '',
      card_fomo: null,
    };
    byShop.set(key, {
      merchant: r.merchant,
      price: r.price,
      link: seller.link || null,
      delivery: seller.delivery || '',
      hyperlocal: isHyperlocal(r.merchant),
      voucher: v,
      // This shop's bank card offers, best first: read off Flipkart's page,
      // or this week's Amazon bank offers worked out for this price.
      cardOffers: cards.get(key) || (key.includes('amazon') ? amazonCardOffers(r.price, r.title) : []),
      voucherRoute: v
        ? {
            ...base,
            merchant: v.offline_only ? `${r.merchant} (in-store)` : r.merchant,
            final_cost: v.upi.effective_price,
            voucher: v,
          }
        : null,
    });
  }
  return [...byShop.values()].sort(
    (a, b) =>
      a.hyperlocal - b.hyperlocal || a.price - b.price || withGiftCard(a) - withGiftCard(b) || freeFirst(a) - freeFirst(b),
  );
}

/** Amazon's bank offers cover whole categories (e.g. "10% off up to ₹1,250
 * with SBI Credit Card on orders above ₹10,000") rather than one product,
 * so they are kept in amazonBankOffers.json, checked weekly, and worked out
 * here for this item's price. Best first, same shape as Flipkart's. */
export function amazonCardOffers(price, title = '', today = new Date().toISOString().slice(0, 10)) {
  const name = (title || '').toLowerCase();
  return (AMAZON_BANK_OFFERS.offers || [])
    .filter(
      (o) =>
        price >= (o.min_order || 0) &&
        (!o.starts || today >= o.starts) &&
        (!o.ends || today <= o.ends) &&
        !(o.excludes || []).some((w) => name.includes(w.toLowerCase())),
    )
    .map((o) => ({
      bank: o.bank,
      card: o.card || 'Credit Card',
      saving: Math.round(Math.min((price * o.percent) / 100, o.max_off || Infinity)),
      cashback: !!o.cashback,
    }))
    .sort((a, b) => b.saving - a.saving);
}

// Same price: the shop whose gift card takes more off goes first.
const withGiftCard = (s) => s.voucherRoute?.final_cost ?? s.price;
const freeFirst = (s) => (/^free/i.test(s.delivery) ? 0 : 1);

/** True when the price list should lead instead of the gift card steps:
 * at least two shops to compare, and the best gift card saves less than
 * ₹100 or 2% against simply buying at the cheapest shop. */
export function shouldShowPriceList(shops, rec) {
  const normal = shops.filter((s) => !s.hyperlocal);
  if (normal.length < 2 || !rec) return false;
  const cheapest = normal[0].price;
  const saving = rec.voucher ? cheapest - rec.final_cost : 0;
  return saving < MIN_GIFT_CARD_SAVING_RS || (saving / cheapest) * 100 < MIN_GIFT_CARD_SAVING_PCT;
}

/** "Free delivery between Sat–Sun" → "Free, Sat–Sun"; keeps paid delivery visible. */
export function shortDelivery(text) {
  if (!text) return '';
  if (/^Delivery ₹/.test(text)) return `+${text.replace('Delivery ', '')} delivery`;
  return text.replace(/^Free delivery between /, 'Free, ').replace(/^Free next-day delivery$/, 'Free, next day');
}

/** Logos to try for a shop, best first: Brandfetch's square brand icon
 * (404s when it has none, so the next one loads), then the site's own
 * favicon via Google. Both are looked up by the listing's website. */
export function shopLogos(link) {
  let host;
  try {
    host = new URL(link).hostname.replace(/^www\./, '');
  } catch {
    return [];
  }
  return [
    `https://cdn.brandfetch.io/${host}/w/128/h/128/fallback/404/type/icon?c=${BRANDFETCH_CLIENT_ID}`,
    `https://www.google.com/s2/favicons?domain=${host}&sz=128`,
  ];
}
