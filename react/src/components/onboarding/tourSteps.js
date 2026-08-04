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
    id: 'picker-first-card',
    text: "Tap the exact listing that's yours — it decides your price.",
  },
  {
    id: 'voucher-buy',
    text: 'Buy the voucher here — this is where the saving actually happens.',
  },
  {
    id: 'checkout-open',
    text: "Add to cart, apply the code, and pay what's left.",
  },
];
