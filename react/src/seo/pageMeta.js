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

export const HOME_TITLE = 'Dealo — Never pay full price, just search the product';
export const DEFAULT_DESCRIPTION =
  'Dealo finds the cheapest legitimate way to buy anything online in India — stacking discounted gift vouchers with cashback cards to cut your final checkout price.';

/** `title` is what usePageTitle gets (it appends " — Dealo"); `heading`/`intro` mirror the page's visible top. */
export const PAGE_META = {
  home: {
    title: null,
    description: DEFAULT_DESCRIPTION,
    heading: 'Never pay full price. Just search.',
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
