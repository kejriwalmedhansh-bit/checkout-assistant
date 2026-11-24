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

/** When the Reddit threads behind the Reddit guide were last read. */
const REDDIT_READ = 'November 2026';

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
    // What the shops' own rules say, for the Reddit guide.
    noClub: shopPages.filter((s) => s.canClub === false).length,
    club: shopPages.filter((s) => s.canClub === true).length,
    oneCard: shopPages.filter((s) => s.stack === 'One voucher per order').length,
    singleUse: shopPages.filter((s) => s.multiUse === false).length,
    multiUse: shopPages.filter((s) => s.multiUse === true).length,
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
    {
      // Search Console and Google's suggestions (Nov 2026): the questions end
      // in "reddit", and AI chats search the same way. This page is an honest
      // summary of public threads, each one linked. Owner's rules: no seller
      // is named or ranked; opinions are paraphrased, never quoted at length.
      slug: 'discounted-gift-cards-india-reddit',
      title: `Discounted gift cards in India: what Reddit users say (${f.year})`,
      description: 'What Indian Reddit users say about buying gift cards at a discount: is it a scam, why are they cheaper, and the catches people ran into. With links to the threads.',
      heading: 'Discounted gift cards in India: what Reddit users say',
      intro: 'We read the Reddit threads so you do not have to. Six things people keep asking, with links to the threads.',
      sections: [
        {
          h: 'The short answer',
          p: [
            'On Indian Reddit the common view is simple. Buying a gift card from an official seller works and saves real money. Buying one from a stranger is how people get cheated. And most bad experiences come from not reading the card’s rules before paying.',
            `This is Dealo’s own summary of public threads on r/CreditCardsIndia, r/Frugal_Ind, r/IsThisAScamIndia and other Indian subreddits, read in ${REDDIT_READ}. Dealo is not Reddit and Reddit has not approved this page. The opinions belong to the people who posted them; follow the links to read them in full.`,
          ],
        },
        {
          h: '1. “Is it a scam?”',
          p: [
            'The most upvoted answers draw one line: who is selling. When someone posted about a stranger on a marketplace offering Amazon and Flipkart vouchers far below value, the replies were close to unanimous that it was a scam, and that the seller blocks you once the money is sent.',
            'Another poster who was cheated explained what sat behind a “50% off” offer: the codes had been taken from other people, so they could be cancelled at any time.',
            'The rule people repeat: if the discount is much bigger than every official seller shows, walk away.',
          ],
          links: [
            { label: 'r/IsThisAScamIndia: a stranger offering discounted Amazon and Flipkart vouchers', href: 'https://www.reddit.com/r/IsThisAScamIndia/comments/1nvadgs/amazonflipkart_discounted_gift_vouchers/' },
            { label: 'r/IndiaDealsExchange: how a “huge discount” gift card seller operates', href: 'https://www.reddit.com/r/IndiaDealsExchange/comments/1pa9g77/beware_of_gift_card_sellers_offering_huge/' },
          ],
        },
        {
          h: '2. “Why would anyone sell a card for less than its value?”',
          p: [
            'People ask this often, because a real discount with no catch sounds wrong. The answer that gets the most agreement: the shop itself pays for most of the discount. A sold gift card is money the shop has already received, and any balance nobody spends is pure profit for it.',
            'That is also why the discount differs so much from shop to shop. Big marketplaces do not need to give much. Smaller brands give more to win the order.',
          ],
          links: [
            { label: 'r/CreditCardsIndia: how do gift voucher platforms make money?', href: 'https://www.reddit.com/r/CreditCardsIndia/comments/1q6ldvw/how_do_gift_voucher_platforms_like_maximize_money/' },
          ],
        },
        {
          h: '3. “Can I use it with a coupon or a bank offer?”',
          p: [
            'This is the most common regret. One poster bought a travel gift card for the cashback, then found that paying with it switched off every other offer at checkout, and ended up worse off. The replies: it was in the terms, read them first.',
            'On adding a bank card offer on top, people point out that the instant discount usually applies only to the part you pay by card, and often needs a minimum card spend. A gift card for the full amount can leave nothing for the bank offer to apply to.',
            `Dealo’s own data agrees that this varies. Of the ${f.total} shops checked on ${f.checked}, ${f.noClub} do not allow a gift card with other offers and ${f.club} do. Each shop page says which.`,
          ],
          links: [
            { label: 'r/CreditCardsIndia: a gift card that switched off every other offer', href: 'https://www.reddit.com/r/CreditCardsIndia/comments/18ycbnv/beware_of_the_gift_card_offers/' },
            { label: 'r/CreditCardsIndia: gift card plus a bank card offer at a fashion shop', href: 'https://www.reddit.com/r/CreditCardsIndia/comments/1h7fud0/can_i_combine_gift_voucher_and_credit_card/' },
          ],
        },
        {
          h: '4. “It would not cover my whole bill”',
          p: [
            'A widely read post describes buying several cards at an electronics store counter, only to learn that the bill was split in two and the cards could not be spread across both. Others added their own versions: a cap on how many cards one order accepts, cards that cannot pay for an extended warranty, cards that cannot buy gold or silver.',
            `What people advise: ask how the bill will be made before you buy the cards, and buy one small card first if you are unsure. In Dealo’s data, ${f.oneCard} of ${f.total} shops accept only one gift card per order, so there you buy a single card for the amount.`,
          ],
          links: [
            { label: 'r/CreditCardsIndia: gift cards and a split bill at an electronics store', href: 'https://www.reddit.com/r/CreditCardsIndia/comments/1k9uumc/double_check_before_buying_gyftr_vouchers/' },
          ],
        },
        {
          h: '5. “What if I return the order?”',
          p: [
            'In a thread recommending gift cards for everyday shopping, the caution that got the most agreement was about returns. Money paid with a gift card usually comes back as store credit, not to your bank. Some people avoid gift cards for clothes for this reason and keep them for food and groceries, where nothing goes back.',
            'A second point from the same discussions: cards that load into the shop’s wallet and can be spent across several orders cause fewer problems than single-use cards.',
            `In Dealo’s data, ${f.multiUse} of ${f.total} cards can be spent across several orders and ${f.singleUse} must be used in one go.`,
          ],
          links: [
            { label: 'r/Frugal_Ind: gift cards with discounts, and the returns warning', href: 'https://www.reddit.com/r/Frugal_Ind/comments/1hqdkbr/gift_cards_with_discounts/' },
          ],
        },
        {
          h: '6. “Is the credit card points maths worth it?”',
          p: [
            'Much of the Reddit discussion is about stacking card reward points on top of gift cards. The sums are long, they depend on which card you hold, and a convenience fee often eats part of the gain. One popular reply joked about paying real money in fees to earn it back as points.',
            'Dealo leaves this out on purpose. Every number on Dealo is the price you pay today, and it is the same whichever bank you use. Points and cashback are never counted.',
          ],
          links: [
            { label: 'r/CreditCardsIndia: does buying gift cards for points still make sense?', href: 'https://www.reddit.com/r/CreditCardsIndia/comments/1osp9vo/does_it_actually_make_sense_to_get_gyftr_cards/' },
          ],
        },
        {
          h: 'Reddit’s advice in one list',
          ul: [
            'Buy from an official seller, never from a person on a marketplace, Telegram or Reddit.',
            'A discount far above what official sellers show is a warning, not a deal.',
            'Read what the card cannot be combined with and cannot buy.',
            'Ask how the bill will be made before buying cards at a store counter.',
            'Buy the card only when you are about to pay, for the amount you will spend.',
            'Prefer cards for things you will not return.',
          ],
        },
        {
          h: 'Biggest gift card discounts today',
          shops: top.slice(0, 6).map((s) => s.slug),
        },
      ],
      note: 'Disclosure: Dealo sells gift cards itself, issued through Hubble, an official gift card issuer. This page summarises public Reddit threads in Dealo’s own words and links to each one. Reddit is a trademark of Reddit, Inc.; Dealo is not connected to it.',
      faqs: [
        {
          q: 'Is buying discounted gift cards legit, according to Reddit?',
          a: 'Yes, from official sellers. Reddit users in India buy them routinely. The scam warnings are about individuals selling codes on marketplaces, Telegram or Reddit itself at very large discounts.',
        },
        {
          q: 'Where does Reddit say to buy discounted gift cards in India?',
          a: 'Threads point to official gift card sellers and issuers, and warn against buying codes from a person. Dealo sells cards issued through Hubble, an official gift card issuer.',
        },
        {
          q: 'Which gift cards do Reddit users find least trouble?',
          a: 'Cards that load into the shop’s own wallet and can be spent across several orders, such as food delivery and big marketplaces. Single-use cards for one bill draw the most complaints.',
        },
        {
          q: 'What is the most common mistake Reddit users report?',
          a: 'Not reading the terms: finding out at checkout that the card cannot be combined with another offer, cannot be split across bills, or cannot pay for certain items.',
        },
        {
          q: 'Can I get my money back if I return something bought with a gift card?',
          a: 'Usually the refund comes back as store credit, not to your bank. Reddit users suggest using gift cards for things you will not return.',
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
