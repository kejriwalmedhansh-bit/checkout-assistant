// Shared by the content script and the background worker — `self` is the
// global in both contexts (a service worker has no `window`).
self.__dealoConfig = {
  // The live backend. This is what ships — pointing it at localhost was the
  // single reason a correctly-installed Dealo could look completely dead:
  // with no server on this machine every lookup failed silently, and silence
  // is exactly what Dealo does when it finds nothing.
  //
  // To develop against a local backend, don't edit this line (it gets shipped
  // by accident). Run this once in the service worker console instead:
  //   chrome.storage.local.set({ dealo_api_base: "http://localhost:8000" })
  // and to go back to live:
  //   chrome.storage.local.remove("dealo_api_base")
  API_BASE: "https://dealo-backend.onrender.com",
  // Where the dev override above is kept.
  API_BASE_OVERRIDE_KEY: "dealo_api_base",
  // URL must contain one of these (case-insensitive) to count as a
  // checkout-like page — generic, not a per-site list.
  CHECKOUT_URL_KEYWORDS: ["cart", "checkout", "bag", "payment"],
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
