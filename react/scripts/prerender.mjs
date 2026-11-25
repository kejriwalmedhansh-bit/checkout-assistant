/**
 * Post-build step: give every real page its own file on disk.
 *
 * Dealo is a single-page app — the bundle ships one index.html and React
 * Router swaps the page contents client-side. That works fine once you're on
 * the site, but the host only has that single file, so a direct request for
 * /privacy/ has no object to serve and comes back as HTTP 404. The page still
 * *renders* (the host returns index.html as its error body, and the router
 * takes over), but the status line says "not found", and that is what a
 * crawler or a link checker reads — which is why every URL in sitemap.xml was
 * being reported as a dead page even though a human could see it fine.
 *
 * Fix: after `vite build`, copy the built index.html to dist/<route>/index.html
 * for every crawlable route. Same app, same bundle — the only difference is
 * that the path now exists, so it answers with a genuine 200. Unknown paths
 * still 404, which is correct.
 *
 * ROUTES is also the single source for sitemap.xml (written here rather than
 * kept by hand in public/), so the sitemap can no longer list a URL that this
 * script hasn't produced a file for.
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { BRAND_DEALS } from '../src/data/brandDeals.js';
import {
  DEFAULT_DESCRIPTION,
  FAQS,
  FAQ_JSON_LD,
  HOME_TITLE,
  PAGE_META,
  SELLER_NAME,
  SELLERS_EXPLAINED,
  SITE_NAME,
  SITE_URL,
  brandsIndexMeta,
  isSubscription,
  pct,
  planPrices,
  shopFaqs,
  shopJsonLd,
  shopNoun,
  shopPageMeta,
  shownPct,
  shownSellers,
  showsComparison,
  shortDate,
  payExamples,
  OTHERS_EXPLAINED,
  whereToRedeemShop,
} from '../src/seo/pageMeta.js';
import {
  BILL,
  CATEGORIES,
  categoryJsonLd,
  categoryMeta,
  categoryOf,
  categoryShops,
  costLine,
  inr,
  moreHeading,
  payOn,
  rateLabel,
  similarShops,
} from '../src/seo/categories.js';
import { buildGuides, guideJsonLd } from '../src/seo/guides.js';
import { CAMPAIGNS, CHANNELS } from '../src/seo/shortLinks.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.join(HERE, '..', 'dist');

// Same live-rate lookup BrandPage.jsx does, so the prerendered "x% off"
// matches what the page shows once it boots.
// Privacy, Terms and the chat-apps help page, rendered from their real
// components by the SSR build step in package.json (see src/seo/staticPages.jsx).
const { renderStaticPage } = await import(path.join(HERE, '..', 'dist-ssr', 'staticPages.js'));

// Every voucher Hubble sells gets a /buy/<slug>/ file, so a link shared on
// WhatsApp answers 200 with its own title (the preview reads the file, never
// the app). Same slug rule as buy_slug() in src/services/hubble_service.py.
// Out of the sitemap and disallowed in robots.txt: hand-off pages, not content.
const HUBBLE_CATALOGUE = JSON.parse(
  await readFile(path.join(HERE, '..', '..', 'data', 'hubble_catalogue.json'), 'utf8'),
);
/** Rupees with paise when there are any: a 2.01% and a 2% card differ by 10 paise. */
const inr2 = (n) => `₹${n.toLocaleString('en-IN', { minimumFractionDigits: Number.isInteger(Math.round(n * 100) / 100) ? 0 : 2, maximumFractionDigits: 2 })}`;
const buySlug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
const BUY_PAGES = [...new Map(HUBBLE_CATALOGUE.map((b) => [buySlug(b.name), b.name])).entries()];

const ALL_BRAND_DEALS = JSON.parse(
  await readFile(path.join(HERE, '..', 'src', 'data', 'allBrandDeals.json'), 'utf8'),
);

// The shop pages: today's rate from every seller side by side, built by
// scripts/build_shop_pages.py from the seller catalogues + the live Dealo
// rate. The six hand-written pages in brandDeals.js lend their copy.
const SHOP_PAGES = JSON.parse(await readFile(path.join(HERE, '..', 'src', 'data', 'shopPages.json'), 'utf8'));
const CURATED = new Map(BRAND_DEALS.map((b) => [b.slug, b]));

// Every shop page must sit in a category, or nothing on the site links to it.
const UNFILED = SHOP_PAGES.filter((s) => !categoryOf(s.slug)).map((s) => s.slug);
if (UNFILED.length) throw new Error(`prerender: add these shop pages to src/seo/categories.js: ${UNFILED.join(', ')}`);


// Trailing slashes on purpose: the host 301-redirects /privacy to /privacy/,
// so the slashed form is the URL that actually answers. Publishing the
// unslashed one would send every crawler and every shared link through a
// needless redirect hop first.
const esc = (t) =>
  String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const p = (t) => (t ? `<p>${esc(t)}</p>` : '');
const list = (items, tag = 'ul') => `<${tag}>${items.map((i) => `<li>${i}</li>`).join('')}</${tag}>`;
const link = (href, text) => `<a href="${href}">${esc(text)}</a>`;

/** Visible top of a page, as plain HTML: its h1 and subtitle. */
const head = (meta) => `<h1>${esc(meta.heading)}</h1>${p(meta.intro)}`;

/** A subscription page: plan prices, then the service's own terms and
 * redeem steps, word for word. Mirrors BrandPage.jsx. */
function subscriptionBody(shop, meta, table) {
  const plans = planPrices(shop);
  const steps = shop.hubble?.steps?.length ? shop.hubble.steps : shop.steps;
  const terms = shop.hubble?.terms || [];
  return [
    head(meta),
    p(`Checked ${shop.checked}.`),
    `<h2>${shop.hubble ? 'Today’s rate' : 'Today’s rate, every seller'}</h2>`,
    table,
    plans.length ? '<h2>What each plan costs today</h2>' + list(plans.map((x) => `${inr(x.face)} plan: you pay ${inr(x.pay)}`)) : '',
    p(shop.hubble ? `Issued through Hubble, an official gift voucher issuer. You redeem the code on ${esc(shop.name)} itself.` : SELLERS_EXPLAINED),
    terms.length ? `<h2>Good to know, in ${esc(shop.name)}’s words</h2>` + list(terms.map(esc)) : '',
    '<h2>How to redeem</h2>',
    list(
      [shop.hubble ? 'Tap Dealo above and pick the plan amount.' : 'Pick the seller above with the best rate.', ...(steps.length ? steps : [`Redeem the code on ${shop.name}.`])].map(esc),
      'ol',
    ),
    '<h2>Questions people ask</h2>',
    shopFaqs(shop).map((f) => `<h3>${esc(f.q)}</h3>${p(f.a)}`).join(''),
    similarBlock(shop),
  ].join('');
}

function shopBody(shop) {
  const meta = shopPageMeta(shop);
  const curated = CURATED.get(shop.slug);
  const rows = shownSellers(shop);
  const top = shop.hubble ? null : rows[0]?.pct;
  // Dealo with the other sellers under it (see showsComparison): rates and
  // the day each was read, no link out and no "cheapest" tag.
  const compare = showsComparison(shop);
  const table =
    `<table><thead><tr><th>Seller</th><th>Discount</th>${compare ? `<th>${inr(BILL)} gift card costs</th><th>Checked</th>` : ''}</tr></thead><tbody>` +
    rows
      .map((r) => {
        const own = r.source === 'dealo';
        const name = own ? 'Dealo (sold by Dealo, code in seconds)' : SELLER_NAME[r.source];
        const who = own ? link(`/buy/${buySlug(shop.hubble.brand_name || shop.name)}/`, name) : compare ? esc(name) : link(r.url, name);
        const extra = compare ? `<td>${inr2(payOn(r.pct))}</td><td>${esc(shortDate(own ? shop.checked : r.checked))}</td>` : '';
        return `<tr><td>${who}${r.pct === top ? ' — cheapest today' : ''}</td><td>${esc(pct(r.pct))} off</td>${extra}</tr>`;
      })
      .join('') +
    '</tbody></table>';
  const examples = shop.hubble ? payExamples(shop, shop.hubble.pct) : [];
  const steps = curated?.steps?.length
    ? curated.steps
    : [
        shop.hubble ? 'Tap Dealo above and pick the voucher amount.' : 'Pick the seller above with the best rate.',
        `Buy a ${shop.name} gift voucher for the amount you plan to spend.`,
        // Where Dealo sells the voucher, the steps are the ones for Dealo's own
        // voucher, not a partner's (a partner's can name its own app).
        ...(shop.hubble?.steps?.length ? shop.hubble.steps : shop.steps.length ? shop.steps.slice(0, 2) : [`Pay at ${shop.name} with the voucher code and keep the difference.`]),
      ];
  if (isSubscription(shop)) return subscriptionBody(shop, meta, table);
  const multi = shop.multiUse === true ? 'Multi-use, spend it across orders' : shop.multiUse === false ? 'Must use the full value in one go' : 'Not stated by the shop';
  const club = shop.canClub === true ? 'Yes, it pays the price after sale and coupons' : shop.canClub === false ? 'No, not with other offers' : 'Not stated, treat it as store credit';
  return [
    head(meta),
    // Where it works is in the opening lines (quickAnswer); not said twice.
    p(`Checked ${shop.checked}.`),
    `<h2>${compare ? 'Every seller Dealo checks' : shop.hubble ? 'Today’s rate' : 'Today’s rate, every seller'}</h2>`,
    table,
    rows[0]?.pct > 0 && examples.length < 2 ? p(`Every ${inr(BILL)} you spend at ${shop.name} costs ${inr(payOn(rows[0].pct))} with the gift card.`) : '',
    examples.length > 1 ? '<h2>What you pay on Dealo</h2>' + list(examples.map((x) => `${inr(x.face)} gift card: you pay ${inr(x.pay)}, you save ${inr(x.save)}`)) : '',
    p(shop.hubble ? 'Issued through Hubble, an official gift voucher issuer. The shop accepts it like store credit.' : SELLERS_EXPLAINED),
    compare ? p(OTHERS_EXPLAINED) : '',
    '<h2>About this voucher</h2>',
    list([
      `Where to redeem? ${esc(whereToRedeemShop(shop))}`,
      `How do I pay? ${shop.hubble ? 'From your bank app; the code arrives in seconds' : 'On the seller’s site, best rate from your bank app'}`,
      `Multi-use or single-use? ${esc(multi)}`,
      `Can it be clubbed with other offers? ${esc(club)}`,
      ...(shop.stack ? [`Several vouchers in one order? ${esc(shop.stack)}`] : []),
      ...(shop.restrictions.length ? [`Not valid for: ${esc(shop.restrictions.join(' · '))}`] : []),
    ]),
    '<h2>How to redeem</h2>',
    list(steps.map(esc), 'ol'),
    p(curated?.notes),
    '<h2>Questions people ask</h2>',
    shopFaqs(shop).map((f) => `<h3>${esc(f.q)}</h3>${p(f.a)}`).join(''),
    similarBlock(shop),
  ].join('');
}

// The homepage as AI crawlers and search engines read it (they don't run the
// app). AI check, 18 Nov 2026: this used to be 45 words. Everything here is
// also on the live homepage or one tap from it: the ticks, the six shop
// tiles (same shops as HomeExamples.jsx, priced from the same catalogue),
// the three steps, and links to the shop pages.
const HOME_SHOPS = ['lifestyle', 'ajio', 'nykaa', 'myntra', 'croma', 'pvr'];

function homeBody() {
  const bySlug = new Map(SHOP_PAGES.map((s) => [s.slug, s]));
  const tiles = HOME_SHOPS.map((slug) => bySlug.get(slug))
    .filter((s) => s && shownPct(s))
    .map((s) => link(`/brands/${s.slug}/`, `${s.name}: every ${inr(BILL)} you spend costs ${inr(payOn(shownPct(s)))}`));
  const top = [...SHOP_PAGES]
    .filter((s) => shownPct(s))
    .sort((a, b) => shownPct(b) - shownPct(a))
    .slice(0, 12)
    .map((s) => link(`/brands/${s.slug}/`, rateLabel(s)));
  return [
    head(PAGE_META.home),
    p('✓ Free · ✓ No login · ✓ Works on sale prices'),
    p(DEFAULT_DESCRIPTION),
    '<h2>What you pay today</h2>',
    list(tiles),
    '<h2>How it works</h2>',
    list(
      [
        'Paste a link, or type the shop or product. Dealo finds the cheapest way to pay.',
        'Buy a voucher: the shop’s own gift card, sold below face value. It takes about 30 seconds and the seller is verified.',
        'Pay less: pay at the shop with the gift card code, like store credit. Each shop page says if it also works on sale prices.',
      ].map(esc),
      'ol',
    ),
    p('Paying by credit card? Your results also show when a card saves you more.'),
    '<h2>Biggest gift card discounts today</h2>',
    list(top),
    '<h2>Gift card discounts by kind of shop</h2>',
    categoryLinks(),
    '<h2>Guides</h2>',
    guideLinks(),
    `<p>${link('/brands/', 'See every shop')} · ${link('/how-it-works/', 'How it works')} · ${link('/chatgpt-claude/', 'Use Dealo in ChatGPT and Claude')}</p>`,
  ].join('');
}

// /llms.txt: a plain summary for AI tools (ChatGPT, Perplexity, Claude),
// following llmstxt.org. Rebuilt on every build, so rates stay current.
function llmsTxt() {
  const shops = [...SHOP_PAGES]
    .filter((s) => shownPct(s))
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((s) => `- [${s.name} ${shopNoun(s)} discount](${SITE_URL}/brands/${s.slug}/): ${pct(shownPct(s))} off${s.hubble ? ', sold by Dealo' : ''} (checked ${s.checked})`);
  return `# Dealo

> Dealo (getdealo.in) shows the cheapest way to pay at Indian shops. Many shops' own gift cards (gift vouchers) sell below face value; buying one and paying with it at checkout is a direct discount anyone can use, with no coupon or bank card needed. Each shop page says whether the card also works on sale prices. Free, no login. Covers Myntra, Nykaa, AJIO, Tata CLiQ, Lifestyle, MakeMyTrip, PVR and 800+ shops.

How it works:
1. Type a shop or product, or paste a product link, on ${SITE_URL}/
2. Buy the shop's gift card for less (Dealo sells many itself through Hubble, an official issuer; others come from Gyftr, Maximize or BuyHatke, which are official gift voucher sellers).
3. Pay at the shop with the gift card code. Dealo never handles card details.

Dealo does not count cashback as a saving and only shows cards that are in stock.

## Main pages
- [Home: search any shop or product](${SITE_URL}/)
- [How it works](${SITE_URL}/how-it-works/)
- [All shops with gift card deals](${SITE_URL}/brands/)
- [Dealo in ChatGPT and Claude](${SITE_URL}/chatgpt-claude/)
- [About](${SITE_URL}/about/)
- [Contact](${SITE_URL}/contact/)

## Guides
${GUIDES.map((g) => `- [${g.title}](${SITE_URL}/guides/${g.slug}/): ${g.description}`).join('\n')}

## Gift card discounts by kind of shop
${CATEGORIES.map((c) => `- [${c.name}](${SITE_URL}/gift-cards/${c.slug}/)`).join('\n')}

## Gift card discount by shop
${shops.join('\n')}
`;
}

const shopItem = (s) => link(`/brands/${s.slug}/`, `${rateLabel(s)}, ${costLine(s).replace(/^E/, 'e')}`);

function similarBlock(shop) {
  const cat = categoryOf(shop.slug);
  const similar = similarShops(shop, SHOP_PAGES);
  if (!cat || !similar.length) return '';
  return `<h2>${esc(moreHeading(cat))}</h2>${list(similar.map(shopItem))}<p>${link(`/gift-cards/${cat.slug}/`, `All ${cat.name.toLowerCase()}`)}</p>`;
}

const GUIDES = buildGuides(SHOP_PAGES);
const LAST_CHECKED = SHOP_PAGES.map((s) => s.checked).sort().pop();
const BY_SLUG = new Map(SHOP_PAGES.map((s) => [s.slug, s]));

function guideBody(g) {
  return [
    head({ heading: g.heading, intro: g.intro }),
    ...g.sections.map(
      (sec) =>
        `<h2>${esc(sec.h)}</h2>` +
        (sec.p || []).map(p).join('') +
        (sec.ol ? list(sec.ol.map(esc), 'ol') : '') +
        (sec.ul ? list(sec.ul.map(esc)) : '') +
        (sec.links ? `<p>Read the threads:</p>${list(sec.links.map((l) => `<a href="${l.href}" rel="nofollow noopener">${esc(l.label)}</a>`))}` : '') +
        (sec.table
          ? `<table><thead><tr>${sec.table.cols.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${sec.table.rows
              .map((r) => `<tr><td>${link(r.href, r.label)}</td><td>${r.count}</td><td>${esc(r.best)}</td><td>${esc(r.least)}</td></tr>`)
              .join('')}</tbody></table>`
          : '') +
        (sec.shops ? list(sec.shops.map((sl) => BY_SLUG.get(sl)).filter(Boolean).map(shopItem)) + p(`Rates checked ${LAST_CHECKED}.`) : ''),
    ),
    '<h2>Questions people ask</h2>',
    g.faqs.map((f) => `<h3>${esc(f.q)}</h3>${p(f.a)}`).join(''),
    p(g.note),
    list(GUIDES.filter((o) => o.slug !== g.slug).map((o) => link(`/guides/${o.slug}/`, o.title))),
  ].join('');
}

const guideLinks = () => list(GUIDES.map((g) => link(`/guides/${g.slug}/`, g.title)));

const categoryLinks = () => list(CATEGORIES.map((c) => link(`/gift-cards/${c.slug}/`, c.plans ? `${c.name} discounts` : `${c.name} gift card discounts`)));

// Each route: its URL, the <head> text (title/description/JSON-LD) and the
// plain-HTML body a crawler reads before React boots. Everything is drawn
// from src/seo/pageMeta.js + the brand data — the same copy the live page
// renders — so the static file never claims something the page doesn't.
const ROUTES = [
  {
    path: '/',
    changefreq: 'weekly',
    priority: '1.0',
    meta: PAGE_META.home,
    body: homeBody,
  },
  {
    path: '/how-it-works/',
    changefreq: 'monthly',
    priority: '0.8',
    meta: PAGE_META.howItWorks,
    jsonLd: [FAQ_JSON_LD],
    body: () =>
      head(PAGE_META.howItWorks) +
      FAQS.map((f) => `<h2>${esc(f.q)}</h2>${p(f.a)}`).join(''),
  },
  {
    path: '/brands/',
    changefreq: 'weekly',
    priority: '0.8',
    meta: brandsIndexMeta(ALL_BRAND_DEALS.length),
    body: () =>
      head(brandsIndexMeta(ALL_BRAND_DEALS.length)) +
      CATEGORIES.map((c) => `<h2>${link(`/gift-cards/${c.slug}/`, c.name)}</h2>${list(categoryShops(c, SHOP_PAGES).map(shopItem))}`).join(''),
  },
  ...CATEGORIES.map((c) => {
    const shops = categoryShops(c, SHOP_PAGES);
    return {
      path: `/gift-cards/${c.slug}/`,
      lastmod: shops.map((x) => x.checked).sort().pop(),
      changefreq: 'weekly',
      priority: '0.7',
      meta: categoryMeta(c, shops),
      jsonLd: categoryJsonLd(c, shops),
      body: () =>
        head(categoryMeta(c, shops)) +
        list(shops.map(shopItem)) +
        `<h2>Other kinds of shops</h2>` +
        list(CATEGORIES.filter((o) => o.slug !== c.slug).map((o) => link(`/gift-cards/${o.slug}/`, o.name))),
    };
  }),
  ...GUIDES.map((g) => ({
    path: `/guides/${g.slug}/`,
    lastmod: LAST_CHECKED,
    changefreq: 'weekly',
    priority: '0.8',
    meta: { title: g.title, description: g.description, heading: g.heading, intro: g.intro },
    jsonLd: guideJsonLd(g, LAST_CHECKED),
    body: () => guideBody(g),
  })),
  ...SHOP_PAGES.map((shop) => ({
    path: `/brands/${shop.slug}/`,
    lastmod: shop.checked,
    changefreq: 'weekly',
    priority: '0.7',
    meta: shopPageMeta(shop),
    jsonLd: shopJsonLd(shop),
    body: () => shopBody(shop),
  })),
  { path: '/about/', changefreq: 'yearly', priority: '0.4', meta: PAGE_META.about },
  { path: '/contact/', changefreq: 'yearly', priority: '0.4', meta: PAGE_META.contact },
  { path: '/join/', changefreq: 'monthly', priority: '0.4', meta: PAGE_META.join },
  { path: '/privacy/', changefreq: 'yearly', priority: '0.2', meta: PAGE_META.privacy, body: () => renderStaticPage('/privacy/') },
  { path: '/terms/', changefreq: 'yearly', priority: '0.2', meta: PAGE_META.terms, body: () => renderStaticPage('/terms/') },
  { path: '/chatgpt-claude/', changefreq: 'monthly', priority: '0.5', meta: PAGE_META.chatApps, body: () => renderStaticPage('/chatgpt-claude/') },
  ...BUY_PAGES.map(([slug, name]) => ({
    path: `/buy/${slug}/`,
    sitemap: false,
    meta: {
      title: `Buy ${name} Gift Voucher`,
      description: `Buy a discounted ${name} gift voucher on Dealo. Pay by UPI, voucher in seconds.`,
      heading: `${name} Gift Voucher`,
      intro: 'Sold by Dealo. Pay by UPI, voucher in seconds.',
    },
  })),
];

// Short links for posts (src/seo/shortLinks.js): a real file each, so the
// link answers 200 and a preview (WhatsApp, LinkedIn) shows the page it opens.
// Every channel's own link, the two channels where previews matter most for
// every shop page, and each named campaign. Any other /<code>/<name> still
// opens in a browser; it just has no preview. Canonical points at the page
// the link opens, and none of them go in the sitemap.
const SHOP_BY_SLUG = new Map(SHOP_PAGES.map((s) => [s.slug, s]));
const shortRoute = (code, name) => {
  const shop = name ? SHOP_BY_SLUG.get(name) : null;
  return {
    path: name ? `/${code}/${name}/` : `/${code}/`,
    sitemap: false,
    canonical: shop ? `/brands/${shop.slug}/` : '/',
    meta: shop ? shopPageMeta(shop) : PAGE_META.home,
  };
};
const PREVIEW_CHANNELS = ['ig', 'wa'];
const SHORT_ROUTES = [
  ...Object.keys(CHANNELS).map((code) => shortRoute(code)),
  ...PREVIEW_CHANNELS.flatMap((code) => SHOP_PAGES.map((s) => shortRoute(code, s.slug))),
  ...CAMPAIGNS.map((c) => shortRoute(...c.split('/'))),
];
const TAKEN = new Set(ROUTES.map((r) => r.path));
for (const r of SHORT_ROUTES) {
  if (TAKEN.has(r.path)) continue;
  TAKEN.add(r.path);
  ROUTES.push(r);
}

// Deliberately absent: /select and /results. They only mean anything with a
// live search behind them, so they stay out of the sitemap and out of the
// crawler's way (robots.txt disallows both).

const shell = await readFile(path.join(DIST, 'index.html'), 'utf8');

/** Replace a <meta> tag's content whether it's written on one line or several. */
function setMeta(html, attr, key, value) {
  const re = new RegExp(`<meta\\s+${attr}="${key}"\\s+content="[^"]*"\\s*/>`);
  if (!re.test(html)) throw new Error(`prerender: index.html has no <meta ${attr}="${key}">`);
  return html.replace(re, `<meta ${attr}="${key}" content="${esc(value)}" />`);
}

const NAV = [
  ['/', SITE_NAME],
  ['/how-it-works/', 'How it works'],
  ['/brands/', 'Store deals'],
  ['/about/', 'About'],
  ['/contact/', 'Contact'],
];

/**
 * Give the copy its own title, description, canonical URL, structured data
 * and readable text. index.html hardcodes all of these to the homepage;
 * usePageTitle / useJsonLd rewrite them once React boots, but a crawler that
 * reads the raw file (and every link preview — WhatsApp, Slack, LinkedIn —
 * which never runs the JS at all) sees only what's in the file as served.
 *
 * The body goes inside #root, so createRoot() replaces it on first render —
 * visitors see the app, and at most a moment of this plain text on a slow
 * connection instead of a blank screen. The JSON-LD blocks are tagged
 * data-prerendered and removed by main.jsx on boot, because useJsonLd adds
 * its own copy and a page must not carry two FAQ blocks.
 */
function renderRoute(html, route) {
  const url = `${SITE_URL}${route.canonical ?? route.path}`;
  const title = route.meta.title ? `${route.meta.title} — ${SITE_NAME}` : HOME_TITLE;
  const { description } = route.meta;

  let out = html
    .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(/<link rel="canonical" href="[^"]*" \/>/, `<link rel="canonical" href="${url}" />`);
  out = setMeta(out, 'name', 'description', description);
  out = setMeta(out, 'property', 'og:title', title);
  out = setMeta(out, 'property', 'og:description', description);
  out = setMeta(out, 'property', 'og:url', url);
  out = setMeta(out, 'name', 'twitter:title', title);
  out = setMeta(out, 'name', 'twitter:description', description);

  const jsonLd = (route.jsonLd ?? [])
    .map((d) => `<script type="application/ld+json" data-prerendered>${JSON.stringify(d).replace(/</g, '\\u003c')}</script>`)
    .join('\n    ');
  if (jsonLd) out = out.replace('</head>', `    ${jsonLd}\n  </head>`);

  const body = route.body ? route.body() : head(route.meta);
  const nav = `<nav>${NAV.map(([href, text]) => link(href, text)).join(' · ')}</nav>`;
  const block =
    '<div data-prerendered style="max-width:600px;margin:0 auto;padding:56px 16px;' +
    'font-family:system-ui,sans-serif;color:#16202B;line-height:1.55">' +
    `${nav}${body}</div>`;
  if (!out.includes('<div id="root"></div>')) throw new Error('prerender: index.html has no empty #root');
  return out.replace('<div id="root"></div>', `<div id="root">${block}</div>`);
}

for (const route of ROUTES) {
  const dir = path.join(DIST, route.path);
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, 'index.html'), renderRoute(shell, route));
}

const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by scripts/prerender.mjs on every build. Don't edit by hand. -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${ROUTES.filter((r) => r.sitemap !== false).map(
  (r) => `  <url>
    <loc>${SITE_URL}${r.path}</loc>${r.lastmod ? `\n    <lastmod>${r.lastmod}</lastmod>` : ''}
    <changefreq>${r.changefreq}</changefreq>
    <priority>${r.priority}</priority>
  </url>`,
).join('\n')}
</urlset>
`;
await writeFile(path.join(DIST, 'sitemap.xml'), sitemap);
await writeFile(path.join(DIST, 'llms.txt'), llmsTxt());

console.log(`prerender: wrote ${ROUTES.length} pages (${BUY_PAGES.length} buy pages, ${SHORT_ROUTES.length} short links) + sitemap.xml + llms.txt`);
