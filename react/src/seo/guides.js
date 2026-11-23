/**
 * Guides (/guides/<slug>/): answers to the questions people type into Google
 * and ask AI chats, from Google's own India search suggestions (18 Nov 2026):
 * "how to buy flipkart gift card at discount", "can i buy gift cards at a
 * discount", "is it safe to buy gift card online", "is buyhatke gift card legit".
 *
 * Owner's rule (18 Nov 2026): no seller-vs-seller comparison. Guides explain
 * the method and show today's rates; they never rank sellers against Dealo.
 *
 * Read by GuidePage.jsx and scripts/prerender.mjs (relative imports only).
 * Rates come from shopPages.json, so they move with every rebuild.
 */
import { SITE_NAME, SITE_URL, pct, shownPct } from './pageMeta.js';
import { CATEGORIES, categoryShops, inr, payOn } from './categories.js';

const topShops = (shopPages, n) =>
  [...shopPages].filter((s) => shownPct(s)).sort((a, b) => shownPct(b) - shownPct(a)).slice(0, n);

const bySlug = (shopPages, slug) => shopPages.find((s) => s.slug === slug);

function example(shopPages) {
  const s = bySlug(shopPages, 'myntra') || topShops(shopPages, 1)[0];
  const r = shownPct(s);
  return { shop: s, rate: r, pay: inr(payOn(r)) };
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
/** "2026-11-23" → "23 November 2026". */
const niceDate = (iso) => {
  const [y, m, d] = String(iso).split('-').map(Number);
  return y && m && d ? `${d} ${MONTHS[m - 1]} ${y}` : String(iso);
};

const names = (shops) => shops.map((s) => `${s.name} (${pct(shownPct(s))})`).join(', ');

/** Today's figures for the main guide, all counted from shopPages.json. */
function figures(shopPages) {
  const rated = shopPages.filter((s) => shownPct(s));
  const low = rated.filter((s) => shownPct(s) < 3).sort((a, b) => shownPct(a) - shownPct(b));
  return {
    total: rated.length,
    high: rated.filter((s) => shownPct(s) >= 8).length,
    low,
    onlineOnly: rated.filter((s) => s.online && !s.offline).length,
    storeOnly: rated.filter((s) => !s.online && s.offline),
    both: rated.filter((s) => s.online && s.offline).length,
    checked: niceDate(shopPages.map((s) => s.checked).sort().pop()),
    // The year the rates were last checked: turns to 2027 by itself with the first rebuild of January.
    year: String(shopPages.map((s) => s.checked).sort().pop()).slice(0, 4),
    // One row per kind of shop: how many, and today's biggest and smallest.
    byType: CATEGORIES.map((c) => {
      const shops = categoryShops(c, shopPages);
      if (!shops.length) return null;
      const best = shops[0];
      const least = shops[shops.length - 1];
      return {
        href: `/gift-cards/${c.slug}/`,
        label: c.name,
        count: shops.length,
        best: `${best.name} ${pct(shownPct(best))}`,
        least: `${least.name} ${pct(shownPct(least))}`,
      };
    }).filter(Boolean),
  };
}

export function buildGuides(shopPages) {
  const ex = example(shopPages);
  const top = topShops(shopPages, 10);
  const f = figures(shopPages);
  const knownStoreOnly = ['skechers', 'westside', 'puma', 'bata', 'titan', 'woodland']
    .map((sl) => f.storeOnly.find((s) => s.slug === sl))
    .filter(Boolean)
    .map((s) => s.name);
  return [
    {
      slug: 'buy-gift-cards-at-discount',
      title: `How to buy gift cards at a discount in India (${f.year})`,
      description: `Today's gift card discount at ${f.total} Indian shops, checked ${f.checked}. A ₹1,000 ${ex.shop.name} gift card costs ${ex.pay}. Where it is worth it, where it is not, and how to buy one.`,
      heading: 'How to buy gift cards at a discount in India',
      intro: 'Pay less at the shop you already use, without a coupon or a special bank card.',
      sections: [
        {
          h: 'What is a discounted gift card?',
          p: [
            `Most Indian shops sell their own gift cards. Official gift card issuers sell many of them below face value, so a ₹1,000 card costs less than ₹1,000. Today a ₹1,000 ${ex.shop.name} gift card costs ${ex.pay} (${pct(ex.rate)} off).`,
            'You then pay at the shop with the gift card code, like store credit. The shop gets its full price, and you keep the difference.',
          ],
        },
        {
          h: 'Today’s numbers',
          p: [
            `Dealo checked the gift card price at ${f.total} Indian shops on ${f.checked}. At ${f.high} of them the card costs at least 8% less than its value. At ${f.low.length} it is under 3%.`,
            'Every number on this page is the price you pay today. Cashback is never counted, because it may or may not arrive later.',
          ],
        },
        {
          h: 'How to buy one, step by step',
          ol: [
            'Search the shop on getdealo.in, or paste a link to what you want to buy.',
            'Pick the gift card amount, close to what you plan to spend.',
            'Pay for the card. Where Dealo sells it, you pay from your bank app and the code arrives in seconds.',
            'At the shop’s checkout, choose “gift card” as the payment method and enter the code. Pay any balance the usual way.',
          ],
        },
        {
          h: 'Discount by type of shop',
          table: { cols: ['Type of shop', 'Shops', 'Biggest today', 'Smallest today'], rows: f.byType },
        },
        {
          h: 'Biggest gift card discounts today',
          shops: top.map((s) => s.slug),
        },
        {
          h: 'When a gift card is not worth it',
          p: [
            `The biggest shops give very little: ${names(f.low)}. On a ₹1,000 order that is ₹${Math.round(shownPct(f.low[0]) * 10)} to ₹${Math.round(shownPct(f.low[f.low.length - 1]) * 10)}.`,
            'At these shops a bank offer on the shop’s own payment page can be bigger than the gift card discount. Compare the two before you buy a card.',
            'A gift card usually cannot be returned or turned back into money. Buy one only for an order you are about to place, and for the amount you plan to spend.',
          ],
        },
        {
          h: 'Online or in a store: check first',
          p: [
            `Of the ${f.total} shops, ${f.onlineOnly} cards work only on the shop’s website or app, ${f.storeOnly.length} work only at the counter in a store, and ${f.both} work in both.`,
            `Cards that work only in a store today include ${knownStoreOnly.join(', ')}. You show the code at the billing counter. Each shop page says where its card works.`,
          ],
        },
        {
          h: 'Before you buy, check three things',
          ul: [
            'Can you add a coupon or other offer too? Many shops do not allow a gift card with other offers. Each shop page says which.',
            'Can it buy everything? Some cards cannot pay for other gift cards, subscriptions or certain brands. Each shop page lists what it cannot buy.',
            'One card or several per order? Some shops take only one gift card per order, so buy one card for the full amount.',
          ],
        },
      ],
      note: 'Disclosure: Dealo sells gift cards itself, issued through Hubble, an official gift card issuer. The numbers here are read from live prices on the date shown and change often, so check the shop’s page before you pay.',
      faqs: [
        {
          q: 'Which shops give the biggest gift card discount in India?',
          a: `Today the biggest are ${names(top.slice(0, 5))}. Smaller brands, food, salons and subscriptions usually give more than big marketplaces.`,
        },
        {
          q: 'Is a gift card worth it for Amazon or Flipkart?',
          a: `Barely. Today it is ${names(f.low.filter((s) => ['amazon', 'flipkart'].includes(s.slug)))}. A bank offer at checkout can be bigger.`,
        },
        {
          q: 'Can I use a discounted gift card in a physical store?',
          a: `At some shops, yes. Of ${f.total} shops checked, ${f.storeOnly.length} cards work only in a store and ${f.both} work both online and in a store. The rest are online only.`,
        },
        {
          q: 'Can I really buy a gift card for less than its value?',
          a: `Yes. Official gift card issuers sell many Indian shops’ cards below face value. Today a ₹1,000 ${ex.shop.name} card costs ${ex.pay}.`,
        },
        {
          q: 'Is a discounted gift card the same as a coupon?',
          a: 'No. A coupon is a code the shop gives you; a gift card is store credit you buy. Where the shop allows it, you can use both: apply the coupon, then pay with the gift card.',
        },
        {
          q: 'Do I need a credit card to buy one?',
          a: 'No. You can pay from your bank app.',
        },
        {
          q: 'Does Dealo count cashback as a saving?',
          a: 'No. Dealo only shows money you do not pay at checkout, never cashback that may or may not arrive later.',
        },
      ],
    },
    {
      slug: 'is-it-safe-to-buy-discounted-gift-cards',
      title: 'Is it safe to buy discounted gift cards in India?',
      description: 'Discounted gift cards are safe when bought from official issuers. The warning signs of a gift card scam, and five rules to keep your money safe.',
      heading: 'Is it safe to buy discounted gift cards?',
      intro: 'Yes, when the card comes from an official issuer. Here is how to tell the difference.',
      sections: [
        {
          h: 'Why the discount is real',
          p: [
            'Shops give official gift card sellers a discount for selling their cards, and the sellers pass part of it on to you. The card is the shop’s own, issued through its official gift card partner, and the shop accepts it like money at checkout.',
            'Dealo’s own gift cards are issued through Hubble, an official gift card issuer. You pay from your bank app and the code arrives in seconds. Dealo never sees your card number, UPI PIN or bank OTP.',
          ],
        },
        {
          h: 'Warning signs of a gift card scam',
          ul: [
            'Someone on Telegram, WhatsApp, OLX or Instagram selling codes at a big discount and asking you to pay them directly.',
            'A seller who asks for your card number, UPI PIN or an OTP.',
            'Anyone asking you to pay a bill, a fine or a “refund fee” with gift cards. Real companies and government offices never do this.',
            'A discount far bigger than every official seller shows for the same shop.',
          ],
        },
        {
          h: 'Five rules to stay safe',
          ol: [
            'Buy only from official gift card sellers or issuers, never from a person.',
            'Pay through your bank app or the seller’s own checkout, never to someone’s personal UPI ID.',
            'Never share a gift card code before you use it. Anyone with the code can spend it.',
            'Check what the card cannot buy before you pay. Each Dealo shop page lists it.',
            'Use the card soon. Every card has an expiry date in its terms.',
          ],
        },
      ],
      faqs: [
        {
          q: 'Is buying a gift card at a discount legal in India?',
          a: 'Yes. Official issuers sell shops’ gift cards below face value openly, and the shop accepts the card at checkout like any other gift card.',
        },
        {
          q: 'What if the code does not work?',
          a: 'Contact the seller you bought it from with your order details. For a card bought on Dealo, write to Dealo on WhatsApp from the Contact page.',
        },
        {
          q: 'Does Dealo handle my money?',
          a: 'No. You pay the gift card seller from your bank app. Dealo never sees your card number, UPI PIN or OTP.',
        },
      ],
    },
  ];
}

export const guideBySlug = (shopPages, slug) => buildGuides(shopPages).find((g) => g.slug === slug) || null;

export function guideJsonLd(guide, checked) {
  const url = `${SITE_URL}/guides/${guide.slug}/`;
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: guide.title,
      description: guide.description,
      url,
      ...(checked ? { dateModified: checked } : {}),
      inLanguage: 'en-IN',
      author: { '@type': 'Organization', name: SITE_NAME, url: `${SITE_URL}/` },
      publisher: { '@type': 'Organization', name: SITE_NAME, url: `${SITE_URL}/` },
    },
    {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: guide.faqs.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
    },
    {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: SITE_NAME, item: `${SITE_URL}/` },
        { '@type': 'ListItem', position: 2, name: guide.title, item: url },
      ],
    },
  ];
}
