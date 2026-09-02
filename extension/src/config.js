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
  // Below this, a rupee saving reads as trivial ("You save ₹35") while the
  // percentage sounds worth doing; above it, the concrete rupee figure lands
  // harder than any percentage. So the headline switches at this amount.
  RUPEE_HEADLINE_FROM: 500,
};
