/**
 * Shop categories (/gift-cards/<slug>/): each groups the shop pages of one
 * kind of shop, so Google finds every shop page through the site's own links
 * and has a page to send "food gift card discount"-type searches to.
 *
 * Why (18 Nov 2026): Search Console showed "Referring page: none detected"
 * for every new shop page. A page nothing links to gets crawled late and
 * ranks low.
 *
 * Read by BrandsIndexPage, CategoryPage, BrandPage ("more shops like this")
 * and scripts/prerender.mjs. Relative imports only (prerender runs in Node).
 * Every slug in shopPages.json belongs to exactly one category; a test-free
 * guard in prerender.mjs fails the build if a shop page is left out.
 */
import {
  SITE_NAME,
  SITE_URL,
  isSubscription,
  pct,
  planLine,
  shopNoun,
  shownPct,
} from "./pageMeta.js";

export const CATEGORIES = [
  {
    slug: "food",
    name: "Food, coffee & groceries",
    short: "Food",
    shops: [
      "dominos",
      "pizza-hut",
      "kfc",
      "subway",
      "starbucks",
      "third-wave-coffee",
      "zomato",
      "swiggy",
      "bigbasket",
      "eazydiner",
      "bakingo",
      "blue-tokai",
      "baskin-robbins",
      "cafe-coffee-day",
      // added 23 Nov 2026
      "punjab-grill",
      "bikanervala",
      "haute-sauce",
    ],
  },
  {
    slug: "fashion",
    name: "Fashion & footwear",
    short: "Fashion",
    shops: [
      "myntra",
      "ajio",
      "ajio-luxe",
      "nykaa-fashion",
      "lifestyle",
      "westside",
      "max-fashion",
      "snitch",
      "biba",
      "beyoung",
      "jockey",
      "tata-cliq",
      "tata-cliq-luxury",
      "puma",
      "skechers",
      "bata",
      "woodland",
      "birkenstock",
      "decathlon",
      "rare-rabbit",
      "marks-and-spencer",
      "blissclub",
      "freecultr",
      // added 23 Nov 2026
      "soch",
      "kalki",
      "speedo",
      "tego",
      "cosmus",
      "femmella",
      "cloud-tailor",
      "french-accent",
      "aldo",
      "charles-and-keith",
      "superdry",
      "steve-madden",
      "diesel",
      "armani-exchange",
      "michael-kors",
      "coach",
      "hugo-boss",
      "kate-spade",
      "tumi",
      "brooks-brothers",
      "ritu-kumar",
      "satya-paul",
      "indian-terrain",
      "linen-club",
      "raymond",
      "miraggio",
      "victorias-secret",
    ],
  },
  {
    slug: "beauty-jewellery",
    name: "Beauty, eyewear & jewellery",
    short: "Beauty & jewellery",
    shops: [
      "nykaa",
      "nykaa-luxe",
      "giva",
      "titan",
      "lenskart",
      "foxtale",
      "kama-ayurveda",
      "ray-ban",
      // added 23 Nov 2026
      "nua",
      "auric",
      "shiva-organic",
      "kimirica",
      "sri-jagdamba-pearls",
      "soulflower",
      "typsy-beauty",
      "nat-habit",
      "estele",
      "ornaz",
      "bath-and-body-works",
      "health-and-glow",
      "sunglass-hut",
      "helios",
      "naturals-salon",
      "tattva-spa",
      "boditive",
    ],
  },
  {
    slug: "electronics",
    name: "Electronics & online shopping",
    short: "Electronics",
    shops: [
      "amazon",
      "flipkart",
      "croma",
      "reliance-digital",
      "boat",
      "philips",
      // added 23 Nov 2026
      "hammer",
      "skullcandy",
    ],
  },
  {
    slug: "travel",
    name: "Travel & rides",
    short: "Travel",
    shops: [
      "makemytrip",
      "goibibo",
      "cleartrip",
      "yatra",
      "ixigo",
      "easemytrip",
      "uber",
      "mokobara",
      "makemytrip-hotels",
      "goibibo-hotels",
      // added 23 Nov 2026
      "cgh-earth",
      "fabhotels",
      "cordelia-cruises",
      "lohono-stays",
      "ixigo-hotels",
      "makemytrip-holidays",
      "yatra-hotels",
      "easemytrip-hotels",
      "sterling-holidays",
    ],
  },
  {
    slug: "movies",
    name: "Movies & events",
    short: "Movies",
    shops: ["pvr", "cinepolis", "bookmyshow"],
  },
  // Vouchers that buy a plan, not shopping: the pages say "subscription" /
  // "membership", never "gift card" (see isSubscription in pageMeta.js).
  {
    slug: "subscriptions",
    name: "Streaming & memberships",
    short: "Subscription",
    plans: true,
    shops: [
      "sonyliv",
      "zee5",
      "amazon-prime",
      "swiggy-one",
      // added 23 Nov 2026
      "hoichoi",
      "gaana",
      "lionsgate-play",
      "livemint",
      "fitpass",
    ],
  },
  {
    slug: "home",
    name: "Home & furniture",
    short: "Home",
    shops: [
      "ikea",
      "pepperfry",
      "urban-ladder",
      "duroflex",
      "dailyobjects",
      "frido",
      "wonderchef",
      // added 23 Nov 2026
      "cello",
      "pure-home-living",
      "at-home",
      "pottery-barn",
      "west-elm",
      "muji",
      "chumbak",
    ],
  },
  {
    slug: "gifts-kids-health",
    name: "Gifts, kids & health",
    short: "Gifts, kids & health",
    shops: [
      "hamleys",
      "firstcry",
      "archies",
      "netmeds",
      "igp",
      "ferns-n-petals",
      "healthians",
      // added 23 Nov 2026
      "photojaanic",
      "hoora",
      "apollo-diagnostics",
      "flower-aura",
      "wellbeing-nutrition",
      "chicco",
      "vitamin-haat",
      "whats-up-wellness",
      "me-n-moms",
      "mediwheel",
      "mothercare",
      "timezone",
      "just-lil-things",
    ],
  },
];

// Per ₹1,000 rather than a big bill: true whatever card sizes a shop sells
// and however many cards it allows per order.
export const BILL = 1000;
export const inr = (n) => `₹${Math.round(n).toLocaleString("en-IN")}`;
/** What ₹1,000 of shopping costs with the gift card at this rate. */
export const payOn = (rate, bill = BILL) => bill * (1 - rate / 100);

/** The small line under a shop's name in a list: what ₹1,000 of shopping
 * costs, or for a subscription what its biggest plan costs. */
export const costLine = (shop, rate = shownPct(shop)) =>
  isSubscription(shop)
    ? planLine(shop, rate)
    : `Every ${inr(BILL)} costs ${inr(payOn(rate))}`;
/** "Domino's gift card: 16% off" / "SonyLIV subscription: 20% off". */
export const rateLabel = (shop) =>
  `${shop.name} ${shopNoun(shop)}: ${pct(shownPct(shop))} off`;
/** Heading over "more like this" on a shop page. */
export const moreHeading = (cat) =>
  cat.plans
    ? "More subscription discounts"
    : `More ${cat.short.toLowerCase()} gift card discounts`;

export const categoryBySlug = (slug) =>
  CATEGORIES.find((c) => c.slug === slug) || null;
export const categoryOf = (shopSlug) =>
  CATEGORIES.find((c) => c.shops.includes(shopSlug)) || null;

/** The category's shops that have a page, biggest discount first. */
export function categoryShops(cat, shopPages) {
  const bySlug = new Map(shopPages.map((s) => [s.slug, s]));
  return cat.shops
    .map((slug) => bySlug.get(slug))
    .filter((s) => s && shownPct(s))
    .sort((a, b) => shownPct(b) - shownPct(a));
}

/** Up to `n` other shops from the same category, for "more shops like this". */
export function similarShops(shop, shopPages, n = 6) {
  const cat = categoryOf(shop.slug);
  if (!cat) return [];
  return categoryShops(cat, shopPages)
    .filter((s) => s.slug !== shop.slug)
    .slice(0, n);
}

export function categoryMeta(cat, shops) {
  const top = shops.slice(0, 2).map((s) => `${s.name} ${pct(shownPct(s))}`);
  const names = shops.slice(0, 4).map((s) => s.name);
  if (cat.plans) {
    return {
      title: `Subscription discounts today${top.length ? `: ${top.join(", ")}` : ""}`,
      description: `Today's discount on ${names.join(", ")} plans. Buy the plan voucher for less on Dealo and redeem the code on the service.`,
      heading: `${cat.name}: discounts today`,
      intro:
        "Today’s discount on each plan voucher. Tap a service for its plans, terms and how to redeem.",
    };
  }
  return {
    title: `${cat.short} gift card discounts today${top.length ? `: ${top.join(", ")}` : ""}`,
    description: `Today's gift card discount at ${shops.length} ${cat.name.toLowerCase()} shops, including ${names.join(", ")}. Buy the shop's gift card for less and pay with it.`,
    heading: `${cat.name}: gift card discounts today`,
    intro: `What every ${inr(BILL)} you spend at each shop costs with its own gift card, bought for less. Tap a shop for its terms and how to buy.`,
  };
}

export function categoryJsonLd(cat, shops) {
  const meta = categoryMeta(cat, shops);
  const url = `${SITE_URL}/gift-cards/${cat.slug}/`;
  const checked = shops
    .map((s) => s.checked)
    .sort()
    .pop();
  return [
    {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      name: `${meta.title} — ${SITE_NAME}`,
      description: meta.description,
      url,
      ...(checked ? { dateModified: checked } : {}),
      inLanguage: "en-IN",
      mainEntity: {
        "@type": "ItemList",
        itemListElement: shops.map((s, i) => ({
          "@type": "ListItem",
          position: i + 1,
          name: `${s.name} gift card: ${pct(shownPct(s))} off`,
          url: `${SITE_URL}/brands/${s.slug}/`,
        })),
      },
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        {
          "@type": "ListItem",
          position: 1,
          name: SITE_NAME,
          item: `${SITE_URL}/`,
        },
        {
          "@type": "ListItem",
          position: 2,
          name: "Store deals",
          item: `${SITE_URL}/brands/`,
        },
        { "@type": "ListItem", position: 3, name: cat.name, item: url },
      ],
    },
  ];
}
