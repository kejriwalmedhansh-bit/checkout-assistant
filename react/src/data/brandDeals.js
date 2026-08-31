/**
 * Hand-picked brand pages for SEO — a small, curated subset of the ~380
 * brands actually live in the search engine (see db/gyftr_master.json).
 * Kept as static copy (not fetched from the live engine) since these are
 * indexed pages, not the product itself: the search flow still checks
 * everything live, this is just the landing content search engines can
 * crawl. Discount rates are the last-checked rate as of the date below —
 * revisit periodically so a stale page doesn't undersell (or oversell) the
 * live number.
 */
export const BRAND_DEALS = [
  {
    slug: 'amazon',
    name: 'Amazon',
    tagline: 'Save on almost anything on Amazon.in',
    ratePct: 0.75,
    lastChecked: '2026-08-26',
    online: true,
    offline: false,
    blurb:
      "Amazon's own voucher partner sells Amazon Pay Gift Vouchers at a small discount. Add one to your Amazon Pay balance before you buy, and it works exactly like store credit at checkout — same Amazon, same product, less money out.",
    steps: [
      'Search your product on Dealo and pick the exact one you want.',
      'Buy the Amazon Gift Voucher at the discounted rate — real store credit, not a workaround.',
      'Add it to your Amazon Pay balance and check out on amazon.in as usual.',
    ],
    notes: 'Up to ₹50,000 in Gift Vouchers can be added to your Amazon Pay balance per calendar month.',
  },
  {
    slug: 'flipkart',
    name: 'Flipkart',
    tagline: 'Save on Flipkart before you check out',
    ratePct: 1.5,
    lastChecked: '2026-08-26',
    online: true,
    offline: false,
    blurb:
      "Flipkart Gift Vouchers are issued by Flipkart's official payments partner and sell at a discount. Load one into your Flipkart wallet and spend it like store credit — same store, same product, lower total.",
    steps: [
      'Search your product on Dealo and pick the exact listing you mean.',
      'Buy the Flipkart Gift Voucher at the discounted rate.',
      'Add it under Saved Cards & Wallets on Flipkart, then pay with it at checkout.',
    ],
    notes: 'Up to 15 Gift Vouchers can be combined in a single Flipkart order.',
  },
  {
    slug: 'myntra',
    name: 'Myntra',
    tagline: 'Save on fashion and beauty on Myntra',
    ratePct: 3,
    lastChecked: '2026-08-26',
    online: true,
    offline: false,
    blurb:
      "Myntra Gift Vouchers sell at a discount through Myntra's official partner. Add one to your Myntra Credit balance and it spends like store credit on any regular order.",
    steps: [
      'Search your product on Dealo and pick the exact item you want.',
      'Buy the Myntra Gift Voucher at the discounted rate.',
      'Add it under Myntra Credit in your profile, then pay with it at checkout.',
    ],
    notes: "Doesn't apply to Gold & Silver coins or Fine Jewellery on Myntra.",
  },
  {
    slug: 'croma',
    name: 'Croma',
    tagline: 'Save on electronics at Croma',
    ratePct: 3,
    lastChecked: '2026-08-26',
    online: true,
    offline: true,
    blurb:
      "Croma Gift Vouchers work both on croma.com and at any Croma store — hand the voucher code to the cashier before billing, or apply it at checkout online.",
    steps: [
      'Search your product on Dealo and pick the exact model you want.',
      'Buy the Croma Gift Voucher at the discounted rate.',
      'Apply it at checkout on croma.com, or show it to the cashier in-store before billing.',
    ],
    notes: 'Up to 5 Gift Vouchers can be used on a single Croma.com order; it can also be combined with other Croma offers.',
  },
  {
    slug: 'reliance-digital',
    name: 'Reliance Digital',
    tagline: 'Save on electronics at Reliance Digital stores',
    ratePct: 0.5,
    lastChecked: '2026-08-26',
    online: false,
    offline: true,
    blurb:
      'Reliance Digital Gift Vouchers are redeemed in-store only, at any listed Reliance Digital outlet. Show the voucher code to the cashier before billing to apply it.',
    steps: [
      'Search your product on Dealo to confirm the best price and check store stock separately.',
      'Buy the Reliance Digital Gift Voucher at the discounted rate.',
      'Visit the store and share the voucher code with the cashier before billing.',
    ],
    notes: "Doesn't apply to Gold/Silver coins, Fine Jewellery, or a few excluded brands — check with the store before you buy.",
  },
  {
    slug: 'ajio',
    name: 'AJIO',
    tagline: 'Save on fashion on AJIO',
    ratePct: 5,
    lastChecked: '2026-08-26',
    online: true,
    offline: false,
    blurb:
      "AJIO Gift Vouchers sell at one of the largest discounts we track. Add one to your AJIO Wallet and it spends like AJIO Cash on any regular order.",
    steps: [
      'Search your product on Dealo and pick the exact item you want.',
      'Buy the AJIO Gift Voucher at the discounted rate.',
      "Add it under 'Have a Gift Card?' in your AJIO Wallet, then pay with it at checkout.",
    ],
    notes: "Doesn't apply to gold/silver idols, coins, or fine jewellery on AJIO.",
  },
];

export function getBrandDeal(slug) {
  return BRAND_DEALS.find((b) => b.slug === slug);
}
