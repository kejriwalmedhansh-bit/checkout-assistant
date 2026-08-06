import { ROUTES } from '@/routes/paths';
import { I } from '@/components/common/icons';

// What actually happens, in the order it happens, said as pictures instead
// of sentences — per PRODUCT.md, design for the lower end of reading
// comfort by default. Shown inline on the homepage (SearchPage.jsx) and
// reused as the step list order the live tour below also follows.
export const HOW_IT_WORKS = [
  { icon: I.link, label: 'Paste a link' },
  { icon: I.ticket, label: 'Buy a small voucher' },
  { icon: I.pay, label: 'Pay less' },
];

/**
 * The live, first-search guided tour (see Spotlight.jsx). Each step names a
 * real on-screen element via its `data-tour` attribute — the tour finds it
 * live rather than showing a static screenshot, so it always matches
 * whatever's actually on screen. Steps advance when the user does the real
 * thing (submits a search, picks a product, taps a step's action), never on
 * a timer or a "Next" button.
 *
 * `page` is the route each step's target actually lives on — Spotlight
 * checks it against the current location before rendering the bottom bar,
 * so client-side navigation that lands somewhere other than where
 * `tourStep` expects (a stale route, browser back/forward, a direct link)
 * can't show instructions for a step that isn't the one on screen.
 */
export const TOUR_STEPS = [
  {
    id: 'search-box',
    page: ROUTES.home,
    // The home page has a lot around the search box (logo, headline, the
    // "how it works" icons, the heads-up banner) — dimming all of it to
    // black made the whole page feel like it "vanished" for one box that
    // already has its own strong brand-colored border/glow. Ring only.
    dim: false,
    text: "Paste a product link, or type what you're looking for.",
  },
  {
    id: 'picker-first-thumbnail',
    page: ROUTES.select,
    // Rings the first card's photo specifically, but skips the full-page
    // dim (see Spotlight's `dim: false` handling) — a ring on one small
    // thumbnail reads as "here's an example," not "only this card works,"
    // the way dimming every other card did before.
    dim: false,
    text: 'Tap a photo for a closer look. Any listing works — pick yours.',
  },
  {
    id: 'voucher-buy',
    page: ROUTES.results,
    // No full-page dim, same reasoning as the two steps above (and now
    // consistent across the whole tour) — this screen already has its own
    // real content (price, voucher breakdown) the user needs to read
    // alongside the tour text, which a dark overlay fights against.
    dim: false,
    text: "This isn't Dealo selling anything — you're buying a real Gift Voucher from our trusted partner, for less than its value. You'll use it to pay in the next step.",
  },
  {
    id: 'checkout-open',
    page: ROUTES.results,
    dim: false,
    text: "Add to cart, apply the code, and pay what's left.",
  },
];
