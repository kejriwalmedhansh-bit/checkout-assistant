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

  // The three voucher partners. Dealo has to be able to run here — the whole
  // guided middle of the journey happens on these sites — but it must NOT
  // appear when someone is merely browsing vouchers, which looks unhinged:
  // a voucher popup on a voucher site. So these are injected ONLY while a
  // trip is actually in progress (see shouldRunOn in background.js).
  VOUCHER_HOSTS: ["gyftr.com", "maximize.money", "buyhatke.com"],

  // Places Dealo must never appear, whatever the address says. The keyword
  // test below already excludes almost everything that isn't a shop, but
  // these are the sites where being wrong is most alarming — a shopping
  // extension surfacing over someone's inbox reads as spyware even when it
  // does nothing. Matched on the registrable host and its subdomains.
  NEVER_RUN_HOSTS: [
    // mail
    "mail.google.com", "outlook.com", "outlook.live.com", "outlook.office.com",
    "mail.yahoo.com", "mail.proton.me", "zoho.com", "rediffmail.com",
    // messaging and social
    "web.whatsapp.com", "facebook.com", "messenger.com", "instagram.com",
    "x.com", "twitter.com", "linkedin.com", "reddit.com", "threads.net",
    "snapchat.com", "discord.com", "telegram.org", "web.telegram.org",
    // documents and work
    "docs.google.com", "drive.google.com", "calendar.google.com",
    "notion.so", "slack.com", "figma.com", "github.com",
    // Dealo's own site — the extension has nothing to say here
    "getdealo.in",
  ],
  // Don't interrupt a checkout for a saving that isn't worth the errand.
  // Buying a voucher is real effort — leave the site, pay, wait for a code,
  // come back, redeem it. A deal has to clear ONE of two bars:
  //
  //   * a good rate that is also real money — MIN_RATE_TO_OFFER and
  //     MIN_SAVING_AT_RATE, which must BOTH hold, or
  //   * enough money that the rate stops mattering — MIN_SAVING_ALONE.
  //
  // Set 2026-09-07, replacing a flat "₹500 or 3%" where either bar alone was
  // enough. Rate alone was too loose: boAt's genuine 7% on a ₹1,189 basket is
  // ₹83, and Dealo was interrupting a checkout to offer it — seen live while
  // shooting the store screenshots. Money alone was too tight: at a ₹500 bar
  // Croma's 3% stayed silent until a ₹16,700 basket. Pairing the rate with a
  // small rupee floor keeps the good rates and drops the trivial ones, while
  // the standalone rupee bar still catches a big basket at a poor rate.
  //
  // MIN_RATE_FLOOR is the exception to MIN_SAVING_ALONE, added 2026-09-07.
  // Amazon's 0.75% is capped by a ₹50,000 monthly wallet ceiling, so a
  // ₹200,000 basket saves ₹375 and no more however big the basket gets
  // (checked live, not assumed). Under the rupee bar alone that cleared ₹300
  // and Dealo offered it — five separate ₹10,000 vouchers, covering a quarter
  // of the order, for ₹375. Below this floor the rate is so thin that no
  // basket size makes the errand worth it, so the rupee bar doesn't apply.
  // Set at 1% deliberately: the product decision was "₹300 is worth showing
  // even at 1%", so 1% still qualifies and 0.75% does not.
  MIN_RATE_TO_OFFER: 3,
  MIN_SAVING_AT_RATE: 100,
  MIN_SAVING_ALONE: 300,
  MIN_RATE_FLOOR: 1,
  // A third way through, added 2026-09-09. A rate this good is worth naming
  // whatever the basket: DailyObjects discounts 15%, which on a ₹1,078 order
  // is ₹150 — a bigger share of the bill than the ₹350 boAt deal that was
  // considered obviously worth showing, and it was being silenced by a flat
  // rupee floor. The floor itself also drops from ₹200 to ₹100.
  STRONG_RATE: 10,
};
