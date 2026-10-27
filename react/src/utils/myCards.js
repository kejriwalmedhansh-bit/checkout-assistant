/**
 * The banks a shopper has credit cards from, asked once on the results page
 * and kept on this device (no login). Used to fold the shops' bank card
 * offers into the price list, so the list shows what this shopper pays.
 *
 * Card offers worth asking about (Flipkart study, 34 products, 2026-10-27):
 * a bank discount of ₹1,000+ shows up on electronics and appliances from
 * about ₹12,000; fashion, beauty and cheap items have none. Flipkart Axis /
 * Flipkart SBI give 5% on nearly everything; that is the card's normal
 * reward, not a deal on the item, so it never triggers the question.
 */
const KEY = 'dealo_my_cards';

// The choices, as the shops name the bank in their offers. Co-branded cards
// are separate: a Flipkart Axis card is not an Axis Bank card.
export const CARD_CHOICES = [
  { id: 'HDFC', label: 'HDFC', site: 'hdfcbank.com' },
  { id: 'ICICI', label: 'ICICI', site: 'icicibank.com' },
  { id: 'SBI', label: 'SBI', site: 'sbicard.com' },
  { id: 'Axis', label: 'Axis', site: 'axisbank.com' },
  { id: 'Kotak', label: 'Kotak', site: 'kotak.com' },
  { id: 'IDFC', label: 'IDFC FIRST', site: 'idfcfirstbank.com' },
  { id: 'BOB', label: 'BOBCARD', site: 'bobcard.co.in', also: ['bank of baroda', 'bobcard'] },
  { id: 'HSBC', label: 'HSBC', site: 'hsbc.co.in' },
  { id: 'OneCard', label: 'OneCard', site: 'getonecard.app', also: ['one card'] },
  { id: 'Flipkart Axis', label: 'Flipkart Axis', site: 'flipkart.com' },
  { id: 'Flipkart SBI', label: 'Flipkart SBI', site: 'flipkart.com' },
  { id: 'Amazon Pay ICICI', label: 'Amazon Pay ICICI', site: 'amazon.in', also: ['amazon pay'] },
];

export const MIN_REAL_OFFER_RS = 1000;

// Owner's call 2026-10-27: ask while results load, only for things card
// offers are about (phones, tablets, laptops, TVs, big appliances, cameras,
// watches) costing over ₹20,000. Words matched against the product's title.
export const ASK_ABOVE_RS = 20000;
const CARD_CATEGORY_WORDS = [
  'phone', 'iphone', 'galaxy', 'pixel', 'oneplus', 'redmi', 'poco', 'vivo', 'oppo', 'realme', 'iqoo', 'motorola', 'nothing phone',
  'mobile', 'smartphone', '5g',
  'ipad', 'tablet', 'galaxy tab',
  'laptop', 'macbook', 'notebook', 'chromebook', 'thinkpad', 'vivobook', 'zenbook', 'ideapad', 'inspiron', 'pavilion', 'victus',
  'tv', 'television', 'oled', 'qled',
  'refrigerator', 'fridge', 'washing machine', 'air conditioner', ' ac ', 'split ac', 'window ac', 'dishwasher', 'microwave',
  'camera', 'mirrorless', 'dslr', 'gopro',
  'watch', 'smartwatch',
  'playstation', 'ps5', 'xbox', 'nintendo',
];
export function shouldAskForCards(title, price) {
  if (!price || price <= ASK_ABOVE_RS) return false;
  const t = ` ${(title || '').toLowerCase()} `;
  return CARD_CATEGORY_WORDS.some((w) => t.includes(w));
}
const STORE_CARD_NORMAL_PCT = 5.5;

/** Saved answer: { cards: [choice ids] ([] = "None"), prime: bool }, or
 * null if never asked. `prime` only matters for Amazon Pay ICICI (5% back
 * with Prime, 3% without). */
export function loadMyCards() {
  try {
    const v = JSON.parse(window.localStorage.getItem(KEY));
    if (Array.isArray(v)) return { cards: v, prime: false };
    return v && Array.isArray(v.cards) ? { cards: v.cards, prime: !!v.prime } : null;
  } catch {
    return null;
  }
}

export function saveMyCards(answer) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(answer));
  } catch {
    // Private mode: the answer lasts for this visit only.
  }
}

/** Which choice an offer's bank is, e.g. "Flipkart Axis" → "Flipkart Axis",
 * "HDFC Bank" → "HDFC". Longest name first so co-branded cards win. */
export function choiceFor(bank) {
  const b = (bank || '').toLowerCase();
  return CARD_CHOICES.flatMap((c) => [c.id, ...(c.also || [])].map((name) => [name.toLowerCase(), c.id]))
    .sort((x, y) => y[0].length - x[0].length)
    .find(([name]) => b.includes(name))?.[1];
}

const isCredit = (o) => o.card === 'Credit Card';

/** An offer that is a real deal on this item, not a store card's usual 5%. */
export function isRealOffer(o, price) {
  if (!isCredit(o) || o.saving < MIN_REAL_OFFER_RS) return false;
  const storeCard = /flipkart|amazon/i.test(o.bank);
  return !(storeCard && (o.saving / price) * 100 <= STORE_CARD_NORMAL_PCT);
}

/** What the shop's Gift Voucher takes off, in ₹ (0 without one). */
export const giftVoucherSaving = (shop) =>
  shop.voucher && shop.voucherRoute ? Math.round(shop.price - shop.voucherRoute.final_cost) : 0;

// Owner's call 2026-10-27: a card offer only shows where it takes off more
// than that shop's Gift Voucher; otherwise the Gift Voucher stays the deal.
const beatsVoucher = (o, shop) => o.saving > giftVoucherSaving(shop);

/** The best offer on this shop for the shopper's cards, or null. */
export function myBestOffer(shop, myCards) {
  if (!myCards?.length) return null;
  const o = (shop.cardOffers || []).find((x) => isCredit(x) && myCards.includes(choiceFor(x.bank)));
  return o && beatsVoucher(o, shop) ? o : null;
}

/** The best real offer on this shop, for someone without that card. */
export function bestRealOffer(shop) {
  const o = (shop.cardOffers || []).find((x) => isRealOffer(x, shop.price));
  return o && beatsVoucher(o, shop) ? o : null;
}

/** For a shopper without the card: the one card offer that would beat the
 * cheapest deal on the page, or null. Shown only when that is true. */
export function missingOut(shops, myCards, cheapest) {
  let best = null;
  for (const s of shops) {
    for (const o of s.cardOffers || []) {
      if (!isRealOffer(o, s.listPrice ?? s.price) || myCards?.includes(choiceFor(o.bank))) continue;
      const pay = (s.listPrice ?? s.price) - o.saving;
      if (pay < cheapest && (!best || pay < best.pay)) best = { shop: s, offer: o, pay };
    }
  }
  return best;
}

/** Where to apply for the card in an offer. TODO: affiliate links once a
 * partner is picked; the bank's own page until then. */
const APPLY = {
  'Flipkart Axis': 'https://www.axisbank.com/retail/cards/credit-card/flipkart-axisbank-credit-card',
  'Flipkart SBI': 'https://www.sbicard.com/en/personal/credit-cards/flipkart-sbi-card.html',
  HDFC: 'https://www.hdfcbank.com/personal/pay/cards/credit-cards',
  ICICI: 'https://www.icicibank.com/personal-banking/cards/credit-card',
  Axis: 'https://www.axisbank.com/retail/cards/credit-card',
  SBI: 'https://www.sbicard.com/en/personal/credit-cards.page',
  Kotak: 'https://www.kotak.com/en/personal-banking/cards/credit-cards.html',
  IDFC: 'https://www.idfcfirstbank.com/credit-card',
  BOB: 'https://www.bobcard.co.in/',
  HSBC: 'https://www.hsbc.co.in/credit-cards/',
  OneCard: 'https://www.getonecard.app/',
  'Amazon Pay ICICI': 'https://www.icici.bank.in/personal-banking/cards/credit-card/amazon-pay-credit-card',
};
export const applyLink = (o) => APPLY[choiceFor(o.bank)] || null;

/** Every shop at what this shopper pays: the cheaper of their best card
 * offer and the shop's Gift Voucher (owner's call 2026-10-27: the top row is
 * the cheapest way to pay, card or voucher). Cheapest first; quick-commerce
 * apps still go last. Each row keeps `listPrice` and says which way won:
 * `mine` (card offer) or `byVoucher`. */
export function pricesFor(shops, myCards) {
  return shops
    .map((s) => {
      const mine = myBestOffer(s, myCards);
      const gv = giftVoucherSaving(s);
      const saving = Math.max(mine?.saving || 0, gv);
      return {
        ...s,
        listPrice: s.price,
        mine: mine && mine.saving >= gv ? mine : null,
        byVoucher: gv > 0 && gv > (mine?.saving || 0),
        price: s.price - saving,
      };
    })
    .sort((a, b) => a.hyperlocal - b.hyperlocal || a.price - b.price);
}
