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
  FAQS,
  FAQ_JSON_LD,
  HOME_TITLE,
  PAGE_META,
  SITE_NAME,
  SITE_URL,
  brandJsonLd,
  brandPageMeta,
  brandsIndexMeta,
  canClubText,
  multiUseText,
  whereToRedeem,
} from '../src/seo/pageMeta.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIST = path.join(HERE, '..', 'dist');

// Same live-rate lookup BrandPage.jsx does, so the prerendered "x% off"
// matches what the page shows once it boots.
// Privacy, Terms and the chat-apps help page, rendered from their real
// components by the SSR build step in package.json (see src/seo/staticPages.jsx).
const { renderStaticPage } = await import(path.join(HERE, '..', 'dist-ssr', 'staticPages.js'));

const ALL_BRAND_DEALS = JSON.parse(
  await readFile(path.join(HERE, '..', 'src', 'data', 'allBrandDeals.json'), 'utf8'),
);
const normalizeKey = (name) => name.toLowerCase().replace(/[^a-z0-9]/g, '');
const LIVE_DEAL_BY_KEY = new Map(ALL_BRAND_DEALS.map((b) => [normalizeKey(b.name), b]));
const brandRate = (b) => LIVE_DEAL_BY_KEY.get(normalizeKey(b.name))?.pct ?? b.ratePct;

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

function brandBody(b) {
  const rate = brandRate(b);
  const meta = brandPageMeta(b, rate);
  return [
    head(meta),
    p(`${rate}% off${b.online ? ' · Works online' : ''}${b.offline ? ' · Works in-store' : ''}`),
    p(b.blurb),
    '<h2>How to get the discount</h2>',
    list(b.steps.map(esc), 'ol'),
    '<h2>Quick facts</h2>',
    list([
      `Where to redeem: ${esc(whereToRedeem(b))}`,
      `Multi-use or single-use: ${esc(multiUseText(b))}`,
      `Can be clubbed with offers: ${esc(canClubText(b))}`,
    ]),
    p(b.notes),
  ].join('');
}

const brandLinks = () =>
  list(BRAND_DEALS.map((b) => link(`/brands/${b.slug}/`, `${b.name} Gift Voucher — ${brandRate(b)}% off`)));

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
    body: () =>
      head(PAGE_META.home) +
      list([esc('Paste a link'), esc('Buy a voucher — 30 sec · verified'), esc('Pay less')], 'ol') +
      p('Paying by credit card? There’s something for you on your results.'),
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
    body: () => head(brandsIndexMeta(ALL_BRAND_DEALS.length)) + brandLinks(),
  },
  ...BRAND_DEALS.map((b) => ({
    path: `/brands/${b.slug}/`,
    changefreq: 'weekly',
    priority: '0.7',
    meta: brandPageMeta(b, brandRate(b)),
    jsonLd: brandJsonLd(b),
    body: () => brandBody(b),
  })),
  { path: '/about/', changefreq: 'yearly', priority: '0.4', meta: PAGE_META.about },
  { path: '/contact/', changefreq: 'yearly', priority: '0.4', meta: PAGE_META.contact },
  { path: '/join/', changefreq: 'monthly', priority: '0.4', meta: PAGE_META.join },
  { path: '/privacy/', changefreq: 'yearly', priority: '0.2', meta: PAGE_META.privacy, body: () => renderStaticPage('/privacy/') },
  { path: '/terms/', changefreq: 'yearly', priority: '0.2', meta: PAGE_META.terms, body: () => renderStaticPage('/terms/') },
  { path: '/chatgpt-claude/', changefreq: 'monthly', priority: '0.5', meta: PAGE_META.chatApps, body: () => renderStaticPage('/chatgpt-claude/') },
];

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
  const url = `${SITE_URL}${route.path}`;
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
${ROUTES.map(
  (r) => `  <url>
    <loc>${SITE_URL}${r.path}</loc>
    <changefreq>${r.changefreq}</changefreq>
    <priority>${r.priority}</priority>
  </url>`,
).join('\n')}
</urlset>
`;
await writeFile(path.join(DIST, 'sitemap.xml'), sitemap);

console.log(`prerender: wrote ${ROUTES.length} pages + sitemap.xml`);
