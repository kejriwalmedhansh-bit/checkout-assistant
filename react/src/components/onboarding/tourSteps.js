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
    id: 'picker-first-thumbnail',
    // Rings the first card's photo specifically, but skips the full-page
    // dim (see Spotlight's `dim: false` handling) — a ring on one small
    // thumbnail reads as "here's an example," not "only this card works,"
    // the way dimming every other card did before.
    dim: false,
    text: "Tap any photo like this one to see it up close and swipe between listings. Any of these work — pick the exact one that's yours.",
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
