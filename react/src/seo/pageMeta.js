/**
 * Title, description and headline copy for every crawlable page — read by
 * the pages themselves (via usePageTitle) *and* by scripts/prerender.mjs,
 * which bakes the same text into each page's static HTML file.
 *
 * Why one shared file: a crawler reads the raw HTML before any JS runs, and
 * link previews (WhatsApp, LinkedIn) never run it at all. Before this, every
 * prerendered page shipped as "<title>Dealo</title>" over an empty
 * <div id="root">, so Google saw fourteen identical blank pages. Keeping the
 * copy here means the static file and the live page can't say different
 * things — which Google would treat as cloaking.
 *
 * Relative imports only: prerender.mjs runs under plain Node, which doesn't
 * know Vite's `@/` alias.
 */

export const SITE_URL = 'https://getdealo.in';
export const SITE_NAME = 'Dealo';

export const HOME_TITLE = 'Dealo — Pay less at Myntra, Nykaa, AJIO and 800+ shops';
export const DEFAULT_DESCRIPTION =
  // Under 160 characters so Google shows it whole.
  "Buy the shop's own gift card for less and pay with it at checkout. Free, no login. See what you'd really pay at Myntra, Nykaa, AJIO and 800+ Indian shops.";

/** `title` is what usePageTitle gets (it appends " — Dealo"); `heading`/`intro` mirror the page's visible top. */
export const PAGE_META = {
  home: {
    title: null,
    description: DEFAULT_DESCRIPTION,
    heading: 'Pay less at Myntra, Nykaa, AJIO and 800+ shops.',
    // No subtitle on the live homepage — prerender shows the three-step strip instead.
    intro: null,
  },
  howItWorks: {
    title: 'How it works',
    description:
      'How Dealo finds the cheapest legitimate way to buy something online — from pasting a product link to checking out with a discounted Gift Voucher.',
    heading: 'How Dealo works',
    intro: 'Same product end to end, so you can see exactly what happens at each step.',
  },
  about: {
    title: 'About',
    description:
      'Dealo is a pre-checkout tool that finds the cheapest legitimate way to buy something online in India, by stacking discounted Gift Vouchers with cashback cards.',
    heading: 'About Dealo',
    intro: 'The smartest way to buy — same product, less money out.',
  },
  contact: {
    title: 'Contact',
    description:
      'Reach the Dealo team by WhatsApp or email — search support, feedback, and questions about how Gift Voucher deals work.',
    heading: 'Contact',
    intro: 'Have a question, found a bug, or want to talk to us? Here’s how to reach Dealo.',
  },
  join: {
    title: 'Join the community',
    description: "Send Dealo’s founder whatever you’re about to buy — free, no catch.",
    heading: 'Send it. We find the price.',
    intro: "Send Dealo’s founder whatever you’re about to buy — free, no catch.",
  },
  privacy: {
    title: 'Privacy Policy',
    description:
      'Exactly what Dealo collects on the website, on WhatsApp, and in the Chrome extension — what we never collect, who else sees it, and how to have it deleted.',
    heading: 'Privacy Policy',
    intro:
      'Exactly what Dealo collects on the website, on WhatsApp, and in the Chrome extension — what we never collect, who else sees it, and how to have it deleted.',
  },
  chatApps: {
    title: 'Dealo in ChatGPT and Claude',
    description:
      'Add Dealo to Claude or ChatGPT and ask about any Indian shop: it shows the discounted gift card, what to buy, and what you actually pay.',
    heading: 'Dealo in ChatGPT and Claude',
    intro: 'The cheapest way to pay at a shop, inside the chat.',
  },
  terms: {
    title: 'Terms of Use',
    description: 'The terms for using Dealo’s product search and Gift Voucher recommendations.',
    heading: 'Terms of Use',
    intro: 'The terms for using Dealo’s product search and Gift Voucher recommendations.',
  },
};

export function brandsIndexMeta(exactCount) {
  // "850+" rather than "897+": a round floor reads as a claim, an exact
  // number with a plus on it reads as a counter.
  const storeCount = Math.floor(exactCount / 50) * 50;
  return {
    title: 'Gift Voucher deals by store',
    description: `Compare Gift Voucher discount rates across ${storeCount}+ Indian stores — search any brand and go straight to whichever voucher partner has the best rate.`,
    heading: 'Gift Voucher deals by store',
    intro: `Every store below sells Gift Vouchers at a discount through an official partner — buy one, spend it like store credit, save the difference. ${storeCount}+ stores tracked across our voucher partners.`,
  };
}

export function brandPageMeta(brand, ratePct) {
  return {
    title: `${brand.name} Gift Voucher discount`,
    description: `${brand.name} Gift Vouchers sell at ${ratePct}% off through the official voucher partner — buy one, spend it like store credit at ${brand.name}, and save the difference.`,
    heading: `${brand.name} Gift Voucher deal`,
    intro: brand.tagline,
  };
}

// Quick-facts wording — shared so the prerendered brand page says the same thing.
export function whereToRedeem(brand) {
  if (brand.online && brand.offline) return 'Online and in-store, at any listed outlet';
  if (brand.offline) return 'In-store only, at any listed outlet';
  return 'Online only';
}

export function multiUseText(brand) {
  if (brand.multiUse === true) return 'Multi-use — spend it across as many orders as you like';
  if (brand.multiUse === false) return 'Single-use — the full voucher value is redeemed in one go';
  return 'Not stated by the store';
}

export function canClubText(brand) {
  if (brand.canClub === true) return 'Yes — can be combined with other running offers';
  if (brand.canClub === false) return 'No — cannot be combined with other offers';
  return 'Not stated — treat as store credit only';
}

/**
 * HowTo (matches the numbered redemption steps shown on the page) +
 * BreadcrumbList, not Product/Offer — Dealo doesn't sell the voucher or
 * take a price on this page, it explains a discount rate, so Offer schema
 * would misrepresent what's actually here and risks Google rejecting or
 * penalizing the markup for not matching visible content.
 */
export function brandJsonLd(brand) {
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'HowTo',
      name: `How to get the ${brand.name} Gift Voucher discount`,
      description: brand.blurb,
      step: brand.steps.map((text, i) => ({
        '@type': 'HowToStep',
        position: i + 1,
        text,
      })),
    },
    {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: SITE_NAME, item: `${SITE_URL}/` },
        { '@type': 'ListItem', position: 2, name: 'Store deals', item: `${SITE_URL}/brands/` },
        { '@type': 'ListItem', position: 3, name: brand.name, item: `${SITE_URL}/brands/${brand.slug}/` },
      ],
    },
  ];
}

export const FAQS = [
  {
    q: 'Why do I sometimes buy a Gift Voucher before checkout?',
    a: "It’s usually the cheapest legitimate route: the store’s own official voucher partner sells store credit at a discount. You buy the Gift Voucher, then spend it at checkout exactly like a gift card — same store, same product, lower total. It’s real store credit, not a workaround.",
  },
  {
    q: 'Is this safe?',
    a: 'Yes. Gift Vouchers come from the store’s official partner, and Dealo never handles your money or your card details — you always pay the store directly, on the store’s own site.',
  },
  {
    q: 'Do I need a credit card?',
    a: "No. Our top recommendation never requires one. If you do have a card, we’ll show you when it saves you a little more — never as a requirement.",
  },
];

// Eligible for Google's FAQ rich result — the on-page copy and this data
// are the same three questions, kept in the same array on purpose so they
// can never drift apart.
export const FAQ_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQS.map((f) => ({
    '@type': 'Question',
    name: f.q,
    acceptedAnswer: { '@type': 'Answer', text: f.a },
  })),
};

// ---------------------------------------------------------------------------
// Shop pages (/brands/<slug>/) built from react/src/data/shopPages.json —
// today's rate from every seller side by side. Read by BrandPage.jsx and by
// scripts/prerender.mjs, so the crawled HTML and the live page agree.
// ---------------------------------------------------------------------------

/** The sellers, named once with what they are, as the copy rules require. */
export const SELLER_NAME = { dealo: 'Dealo', gyftr: 'Gyftr', maximize: 'Maximize', buyhatke: 'BuyHatke' };
export const SELLERS_EXPLAINED =
  'Gyftr, Maximize and BuyHatke are official gift voucher sellers; the shop honours their vouchers like store credit. Dealo’s own voucher is issued through Hubble, paid from your bank app, code in seconds.';

export function pct(n) {
  return `${Number(n).toFixed(2).replace(/\.?0+$/, '')}%`;
}

export function bestLine(shop) {
  if (!shop.best) return `${shop.name} gift vouchers`;
  if (shop.hubble) return `${pct(shop.hubble.pct)} off on Dealo`;
  return `${pct(shop.best.pct)} off on ${SELLER_NAME[shop.best.source]}`;
}

/** The rate the page leads with: Dealo's own when it sells the card, else the best seller's. */
export function shownPct(shop) {
  if (shop.hubble) return shop.hubble.pct;
  return shop.best ? shop.best.pct : null;
}

/** Subscriptions and memberships (SonyLIV, Amazon Prime): the voucher buys a
 * plan, not shopping, so these pages never say "gift card". */
export const isSubscription = (shop) => shop.kind === 'subscription';
/** The word people search with for this page: "gift card", "subscription" or "membership". */
export const shopNoun = (shop) => (isSubscription(shop) ? shop.noun : 'gift card');
const rupees = (n) => `₹${Math.round(n).toLocaleString('en-IN')}`;

/** What each plan voucher costs today: face value and what you pay on Dealo. */
export function planPrices(shop, rate = shop.hubble?.pct) {
  if (!isSubscription(shop) || !rate) return [];
  return (shop.hubble?.cards || []).map((face) => ({ face, pay: face * (1 - rate / 100) }));
}
/** "₹999 plan for ₹799": the biggest plan, the line a searcher wants first. */
export function planLine(shop, rate) {
  const plans = planPrices(shop, rate);
  const top = plans[plans.length - 1];
  return top ? `${rupees(top.face)} plan for ${rupees(top.pay)}` : '';
}

function subscriptionMeta(shop) {
  const noun = shop.noun;
  const rate = shownPct(shop);
  const plan = planLine(shop);
  return {
    // People type "<name> subscription offer" and "<name> subscription
    // discount"; the title carries one, the heading the other.
    title: rate ? `${shop.name} ${noun} offer: ${pct(rate)} off today` : `${shop.name} ${noun} offer today`,
    description: `${shop.name} ${noun}: ${bestLine(shop)}${plan ? `, ${plan}` : ''}. ${shop.hubble ? 'Sold by Dealo: pay from your bank app, code in seconds.' : 'Today’s rate from official sellers.'} Checked ${shop.checked}.`,
    heading: `${shop.name} ${noun} discount today`,
    intro: `${bestLine(shop)}. Buy the voucher for the plan you want, then redeem the code on ${shop.name}.`,
  };
}

export function shopPageMeta(shop) {
  if (isSubscription(shop)) return subscriptionMeta(shop);
  const n = shop.sellers.length;
  const compare = showsComparison(shop)
    ? `Sold by Dealo, with ${n} other seller${n === 1 ? '' : 's'} side by side.`
    : shop.hubble
    ? 'Sold by Dealo: pay from your bank app, code in seconds.'
    : `Today’s discount from ${n} official seller${n === 1 ? '' : 's'} side by side, cheapest marked.`;
  return {
    // Search Console, 18 Nov 2026: people type "<shop> gift card discount",
    // and the pages with a plain number in the result got the clicks. So the
    // title uses their words and today's rate (the same one the page shows).
    title: shownPct(shop) ? `${shop.name} gift card discount: ${pct(shownPct(shop))} off today` : `${shop.name} gift card discount today`,
    // Kept short so Google shows the "Checked" date instead of cutting it off.
    description: `${shop.name} gift card (gift voucher): ${bestLine(shop)}. ${compare} Checked ${shop.checked}.`,
    // "gift card" is the phrase people search; "voucher" stays in the body.
    heading: `${shop.name} gift card discount today`,
    // The answer first, with a rupee figure: the sentence AI answers lift.
    intro: `${bestLine(shop)}${shownPct(shop) ? `: a ₹1,000 gift card costs ${rupees(1000 * (1 - shownPct(shop) / 100))}` : ''}. Buy the voucher, pay at ${shop.name} with it, keep the difference.`,
  };
}

/** How far another seller may be ahead of Dealo, in points, for a page to
 * still list the other sellers under Dealo's row. */
export const COMPARE_WITHIN = 0.5;

/**
 * Does this page list the other sellers under Dealo's own row?
 *
 * Owner's call, 24 Nov 2026 (replaces "Dealo alone" of 3 Nov for these
 * pages): AI answers and Google quote pages that compare sellers, so a page
 * shows Gyftr, Maximize and BuyHatke too, but only where Dealo's rate is the
 * best or within COMPARE_WITHIN of it. Where another seller is clearly
 * ahead the page stays Dealo alone. Rates only for the others: no link, no
 * "cheapest" tag. `dealoPct` is the live rate when the page has re-read it.
 */
export function showsComparison(shop, dealoPct = shop.hubble?.pct) {
  if (!dealoPct || isSubscription(shop) || !shop.sellers.length) return false;
  return Math.max(...shop.sellers.map((r) => r.pct)) - dealoPct <= COMPARE_WITHIN;
}

/** The rows of the rate table. `dealo` is Dealo's own voucher (live on the
 * page, the saved one in the prerendered file), or null where Dealo cannot
 * sell it and the sellers are all there is. */
export function sellerRows(shop, dealo = shop.hubble) {
  const others = [...shop.sellers].sort((a, b) => b.pct - a.pct);
  if (!dealo) return others;
  const own = { source: 'dealo', pct: dealo.pct, brand_name: dealo.brand_name };
  return showsComparison(shop, dealo.pct) ? [own, ...others] : [own];
}
export const shownSellers = (shop) => sellerRows(shop);

/** "5 Nov 2026" from "2026-11-05": the date beside another seller's rate. */
export function shortDate(iso) {
  const [y, m, d] = String(iso || '').split('-').map(Number);
  if (!y || !m || !d) return '';
  return `${d} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][m - 1]} ${y}`;
}

export const OTHERS_EXPLAINED =
  'Gyftr, Maximize and BuyHatke are official gift voucher sellers. Dealo re-reads its own rate every day and theirs at each voucher refresh, so each row shows its own date.';

/** What a few round amounts cost on Dealo at this rate, within what the
 * card allows (Flipkart: up to ₹10,000 a card). */
export function payExamples(shop, rate) {
  if (!rate || isSubscription(shop)) return [];
  const max = shop.hubble?.max_amount || Infinity;
  const min = shop.hubble?.min_amount || 0;
  return [1000, 5000, 10000]
    .filter((face) => face >= min && face <= max)
    .map((face) => ({ face, pay: face * (1 - rate / 100), save: (face * rate) / 100 }));
}

/** "Dealo 2% (24 Nov 2026), BuyHatke 2.01% (5 Nov 2026), ...": every rate
 * on the page in one sentence, each with the day it was read. */
export function ratesSentence(shop) {
  return shownSellers(shop)
    .map((r) => `${SELLER_NAME[r.source]} ${pct(r.pct)}${r.source === 'dealo' ? ` (${shortDate(shop.checked)})` : r.checked ? ` (${shortDate(r.checked)})` : ''}`)
    .join(', ');
}

export const DEALO_EXPLAINED = 'Dealo’s own voucher is issued through Hubble, an official gift voucher issuer. Pay from your bank app, the code arrives in seconds, and the shop accepts it like store credit.';

export function whereToRedeemShop(shop) {
  if (shop.online && shop.offline) return 'Online and in store';
  if (shop.offline) return 'In store only';
  return 'Online only';
}

function subscriptionFaqs(shop) {
  const noun = shop.noun;
  const best = shop.best ? bestLine(shop) : 'the rate shown above';
  const plans = planPrices(shop);
  const faqs = [
    {
      q: `Is a discounted ${shop.name} ${noun} voucher safe?`,
      a: shop.hubble
        ? `Yes. Dealo’s own voucher is issued through Hubble, an official gift voucher issuer. Pay from your bank app, the code arrives in seconds, and you redeem it on ${shop.name} itself.`
        : `Yes. ${SELLERS_EXPLAINED} You pay the seller, get a code, and redeem it on ${shop.name} itself.`,
    },
    {
      q: `What is the ${shop.name} ${noun} discount today?`,
      a: `${best} (checked ${shop.checked}). Rates move; this page is rebuilt with every catalogue refresh and the Dealo rate is checked live when the page opens.`,
    },
    {
      q: `How do I get a ${shop.name} ${noun} at a discount?`,
      a: shop.hubble
        ? `Tap Dealo on this page, pick the plan amount and pay from your bank app. The code arrives in seconds; redeem it on ${shop.name}.`
        : `Pick a seller on this page, buy the ${shop.name} voucher for the plan you want, and redeem the code on ${shop.name}.`,
    },
  ];
  if (plans.length) {
    faqs.push({
      q: `Which ${shop.name} plans can I buy on Dealo?`,
      a: `${plans.map((x) => `the ${rupees(x.face)} plan for ${rupees(x.pay)}`).join(', ')}. Check on ${shop.name} which plan each amount buys before you pay.`.replace(/^t/, 'T'),
    });
  }
  return faqs;
}

/** How long Dealo's own card lasts ("1 year", "6 months"), read from the
 * card's own terms. Only for cards Dealo sells: partner cards can differ. */
export function validityOf(shop) {
  const line = (shop.hubble?.terms || []).find((t) => /valid/i.test(t) && /\d+\s*-?\s*(day|month|year)/i.test(t));
  const m = line && line.match(/(\d+)\s*-?\s*(day|month|year)/i);
  if (!m) return null;
  const n = Number(m[1]);
  return `${n} ${m[2].toLowerCase()}${n === 1 ? '' : 's'}`;
}

export function shopFaqs(shop) {
  if (isSubscription(shop)) return subscriptionFaqs(shop);
  const best = shop.best ? bestLine(shop) : 'the rate shown above';
  const validity = validityOf(shop);
  return [
    {
      q: `Is a discounted ${shop.name} gift card safe?`,
      a: shop.hubble
        ? `Yes. ${DEALO_EXPLAINED}`
        : `Yes. ${SELLERS_EXPLAINED} You pay the seller, get a code, and ${shop.name} accepts the code like money at checkout.`,
    },
    {
      q: `What is the ${shop.name} gift card discount today?`,
      // People also type "<shop> gift card highest discount". Said only where
      // the page compares sellers; where Dealo sells the card it shows Dealo alone.
      a: showsComparison(shop)
        ? `${best} (checked ${shop.checked}). Every seller Dealo checks: ${ratesSentence(shop)}. Rates move; Dealo’s own rate is re-read every day.`
        : `${!shop.hubble && shop.best ? `The highest discount today among the sellers Dealo checks is ${best}` : best} (checked ${shop.checked}). Rates move; this page is rebuilt with every catalogue refresh and the Dealo rate is checked live when the page opens.`,
    },
    {
      q: `How do I buy a ${shop.name} gift card at a discount?`,
      a: shop.hubble
        ? `Tap Dealo on this page, pick the amount and pay from your bank app. The code arrives in seconds; enter it at ${shop.name}’s checkout as a gift card.`
        : `Pick a seller on this page, buy the ${shop.name} gift card for the amount you plan to spend, and enter the code at ${shop.name}’s checkout as a gift card.`,
    },
    {
      q: `Does the ${shop.name} gift card work with sale prices and coupon codes?`,
      a: shop.canClub === false
        ? `No. ${shop.name} does not let a gift voucher be combined with other offers; the voucher pays the final price only.`
        : `A gift voucher is store credit, so it pays whatever price is on screen, after any sale or coupon ${shop.name} itself applies.`,
    },
    // Search Console, 24 Nov 2026: "<shop> gift card offer", "<shop> gift
    // voucher" and "<shop> voucher" sat on page 2 because the page hardly
    // used those words. Only asked where there is a rate to answer with.
    ...(shop.best
      ? [{
          q: `Is there any ${shop.name} gift voucher offer today?`,
          a: `Yes: ${best} (checked ${shop.checked}). The ${shop.name} gift voucher itself sells for less than its value, and you pay ${shop.name} with it.`,
        }]
      : []),
    // Search Console, 24 Nov 2026: 75 "<shop> coupon code / promo code /
    // discount code" searches showed Dealo, none clicked. Dealo has no codes,
    // so the answer says that first, then what it does have.
    ...(shop.best
      ? [{
          q: `Is there a ${shop.name} coupon code or promo code?`,
          a:
            `Dealo does not list ${shop.name} coupon codes, promo codes or discount codes. A gift card is another way to pay less, with no code to find: ${best}.` +
            (shop.canClub === true
              ? ` If you have a ${shop.name} discount code, apply it first and pay the rest with the gift card.`
              : shop.canClub === false
                ? ` ${shop.name} does not accept a gift card together with another offer, so use whichever saves more.`
                : ''),
        }]
      : []),
    ...(validity
      ? [{
          q: `How long is a ${shop.name} gift card valid?`,
          a: `Dealo’s ${shop.name} gift card comes with ${validity} validity. Buy it when you are about to spend it.`,
        }]
      : []),
  ];
}

export function shopJsonLd(shop) {
  const faqs = shopFaqs(shop);
  const meta = shopPageMeta(shop);
  return [
    // dateModified = the day the rates on the page were checked, so search
    // engines and AI answers can tell the numbers are current.
    {
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: `${meta.title} — ${SITE_NAME}`,
      description: meta.description,
      url: `${SITE_URL}/brands/${shop.slug}/`,
      dateModified: shop.checked,
      inLanguage: 'en-IN',
      isPartOf: { '@type': 'WebSite', name: SITE_NAME, url: `${SITE_URL}/` },
    },
    {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faqs.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
    },
    {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: SITE_NAME, item: `${SITE_URL}/` },
        { '@type': 'ListItem', position: 2, name: 'Store deals', item: `${SITE_URL}/brands/` },
        { '@type': 'ListItem', position: 3, name: shop.name, item: `${SITE_URL}/brands/${shop.slug}/` },
      ],
    },
  ];
}
