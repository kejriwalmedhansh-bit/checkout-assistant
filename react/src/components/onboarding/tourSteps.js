/**
 * The live, first-search guided tour (see Spotlight.jsx). Each step names a
 * real on-screen element via its `data-tour` attribute — the tour finds it
 * live rather than showing a static screenshot, so it always matches
 * whatever's actually on screen. Steps advance when the user does the real
 * thing (submits a search, picks a product, taps a step's action), never on
 * a timer or a "Next" button.
 */
export const TOUR_STEPS = [
  {
    id: 'search-box',
    text: "Paste a product link, or type what you're looking for.",
  },
  {
    id: 'picker-list',
    // No dim/ring here — every listing is tappable, so highlighting only
    // the first one would wrongly suggest the rest aren't (see Spotlight's
    // `noDim` handling).
    noDim: true,
    text: "Tap the exact listing that's yours — any of these work. Tap a photo to see it up close and swipe between listings to compare.",
  },
  {
    id: 'voucher-buy',
    text: "This isn't Dealo selling anything — you're buying a real Gift Voucher from our trusted partner, for less than its value. You'll use it to pay in the next step.",
  },
  {
    id: 'checkout-open',
    text: "Add to cart, apply the code, and pay what's left.",
  },
];
