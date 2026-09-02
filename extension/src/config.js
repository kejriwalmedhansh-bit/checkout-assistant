// Shared by the content script and the background worker — `self` is the
// global in both contexts (a service worker has no `window`).
self.__dealoConfig = {
  // Point this at the local backend while testing, switch to the deployed one
  // (https://dealo-backend.onrender.com) before real distribution.
  API_BASE: "http://localhost:8000",
  // URL must contain one of these (case-insensitive) to count as a
  // checkout-like page — generic, not a per-site list.
  CHECKOUT_URL_KEYWORDS: ["cart", "checkout", "bag", "payment"],
  // How often to re-check the address bar for a cart page that loaded
  // without a full page reload (common on single-page-app storefronts).
  URL_POLL_MS: 700,
  // Don't interrupt a checkout for a saving that isn't worth the errand.
  // Buying a voucher is real effort — leave the site, pay, wait for a code,
  // come back, redeem it. A deal has to clear ONE of these two bars:
  //
  //   * a decent amount of money (MIN_SAVING_TO_OFFER), or
  //   * a decent rate (MIN_RATE_TO_OFFER), which is worth doing even on a
  //     small basket and gets better as the basket grows.
  //
  // Both are needed because either bar alone is wrong. Amazon's 0.75% rate
  // is capped by its own ₹50,000 monthly wallet ceiling, so even a ₹200,000
  // basket only saves ₹375 — never worth the errand, which is exactly the
  // case that prompted this. But a flat ₹500 bar alone would also silence
  // Croma at 3% (₹450 on a ₹15,000 order) and Myntra at 5.29%, which are
  // clearly worth doing.
  MIN_SAVING_TO_OFFER: 500,
  MIN_RATE_TO_OFFER: 3,
  // Anything actually offered therefore saves at least the amount above, so
  // a known saving is always shown in rupees — the concrete figure lands
  // harder than a percentage. The percentage is only used when the order
  // total couldn't be read at all.
  RUPEE_HEADLINE_FROM: 500,
};
