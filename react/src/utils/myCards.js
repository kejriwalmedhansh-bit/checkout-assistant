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
  { id: 'Flipkart Axis', label: 'Flipkart Axis', site: 'flipkart.com' },
  { id: 'Flipkart SBI', label: 'Flipkart SBI', site: 'flipkart.com' },
];

export const MIN_REAL_OFFER_RS = 1000;
const STORE_CARD_NORMAL_PCT = 5.5;

/** Saved answer: an array of choice ids ([] = "None"), or null if never asked. */
export function loadMyCards() {
  try {
    const v = JSON.parse(window.localStorage.getItem(KEY));
    return Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}

export function saveMyCards(ids) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    // Private mode: the answer lasts for this visit only.
  }
}

/** Which choice an offer's bank is, e.g. "Flipkart Axis" → "Flipkart Axis",
 * "HDFC Bank" → "HDFC". Longest name first so co-branded cards win. */
export function choiceFor(bank) {
  const b = (bank || '').toLowerCase();
  return [...CARD_CHOICES]
    .sort((x, y) => y.id.length - x.id.length)
    .find((c) => b.includes(c.id.toLowerCase()))?.id;
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

/** Ask only when a shop on the list has a real card offer that beats its
 * Gift Voucher. */
export const worthAsking = (shops) => shops.some((s) => bestRealOffer(s));

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
};
export const applyLink = (o) => APPLY[choiceFor(o.bank)] || null;
