/**
 * How each shop's gift card discount moved between a fixed starting day and
 * the latest reading, for /guides/gift-card-discount-changes-india/.
 *
 * Why (27 Nov 2026): Dealo has read these prices since July and nobody else
 * publishes how they move. It is the one page on the site a writer has a
 * reason to quote and link to.
 *
 * Like with like, or the page lies: a seller counts for a shop only if Dealo
 * had read its price on or before BASE_DAY. Dealo began reading some sellers'
 * full lists in October and its own rates in November; counting those would
 * show a "rise" on the day we started looking, not the day a price changed.
 * (First draft of this page did exactly that: 36 rises, 20 of them fake.)
 *
 * No seller is named or ranked here (owner's rule, 18 Nov 2026): a shop's
 * number is the best discount among the sellers compared.
 *
 * Read by guides.js, so by GuidePage.jsx and scripts/prerender.mjs. Relative
 * imports only (prerender runs in plain Node).
 */
import { isSubscription } from './pageMeta.js';
import { CATEGORIES } from './categories.js';

/** The starting point. Move it forward by hand when the comparison gets stale. */
export const BASE_DAY = '2026-08-31';
/** A change smaller than this is "the same": sellers shave hundredths off daily. */
export const MIN_MOVE = 0.5;
/** How many shops each "biggest" list shows. */
const LIST = 8;
/** A type of shop needs this many shops before we call it "the jumpy one". */
const MIN_FOR_SHARE = 10;

const round2 = (n) => Math.round(n * 100) / 100;

/** A seller's rate on `day`: the last one read on or before it. */
function rateOn(points, day) {
  let rate = null;
  for (const [d, r] of points) if (d <= day) rate = r;
  return rate;
}

function shopChange(shop) {
  if (isSubscription(shop)) return null;
  const compared = (shop.sellers || [])
    .filter((s) => s.pct)
    .map((s) => ({ now: s.pct, checked: s.checked, points: Object.entries(shop.history?.[s.source] || {}).sort() }))
    .filter((s) => rateOn(s.points, BASE_DAY) !== null);
  if (!compared.length) return null;

  const bestOn = (day) => Math.max(...compared.map((s) => rateOn(s.points, day)).filter((r) => r !== null));
  const was = bestOn(BASE_DAY);
  const now = Math.max(...compared.map((s) => s.now));
  const days = [...new Set(compared.flatMap((s) => s.points.map(([d]) => d)))].sort();
  const diff = round2(now - was);
  const dealo = shop.hubble?.pct;
  return {
    slug: shop.slug,
    name: shop.name,
    was,
    now,
    diff,
    dir: diff >= MIN_MOVE ? 'up' : diff <= -MIN_MOVE ? 'down' : 'same',
    // The line drawn beside the shop: the best compared rate on each day one of them changed.
    points: days.map((d) => [d, bestOn(d)]),
    days,
    lastRead: compared.map((s) => s.checked).filter(Boolean).sort().pop() || days[days.length - 1],
    // Dealo's own rate, only where it beats the others today. Shown, never counted.
    dealo: dealo && dealo > now ? dealo : null,
  };
}

/** Everything the guide prints, counted from shopPages.json. */
export function rateChanges(shopPages) {
  const rows = shopPages.map(shopChange).filter(Boolean);
  const of = (dir, list = rows) => list.filter((r) => r.dir === dir);
  const catOf = (slug) => CATEGORIES.find((c) => c.shops.includes(slug));
  for (const r of rows) r.cat = catOf(r.slug)?.short || 'Other';

  const byCat = [...new Set(rows.map((r) => r.cat))]
    .map((name) => {
      const list = rows.filter((r) => r.cat === name);
      return { name, total: list.length, up: of('up', list).length, down: of('down', list).length, same: of('same', list).length };
    })
    .sort((a, b) => b.total - a.total);

  const sorted = [...rows.map((r) => r.was)].sort((a, b) => a - b);
  const allDays = [...new Set(rows.flatMap((r) => r.days))].sort();
  return {
    rows,
    total: rows.length,
    up: of('up').length,
    down: of('down').length,
    same: of('same').length,
    rises: of('up').sort((a, b) => b.diff - a.diff).slice(0, LIST),
    falls: of('down').sort((a, b) => a.diff - b.diff).slice(0, LIST),
    byCat,
    /** The type of shop with the most falls. */
    mostFalls: [...byCat].sort((a, b) => b.down - a.down)[0],
    /** The type of shop where the biggest share changed, and the biggest type to set beside it. */
    jumpy: [...byCat].filter((c) => c.total >= MIN_FOR_SHARE).sort((a, b) => (b.up + b.down) / b.total - (a.up + a.down) / a.total)[0],
    biggest: byCat[0],
    /** The usual discount at the start: the middle one. */
    typical: sorted.length ? sorted[Math.floor(sorted.length / 2)] : null,
    checks: allDays.length,
    firstDay: allDays[0],
    lastDay: rows.map((r) => r.lastRead).sort().pop(),
  };
}
