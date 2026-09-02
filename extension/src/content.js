// Orchestrator: is this a checkout page? -> read domain + price -> ask the
// background worker -> show whichever popup case applies.
(() => {
  const DISMISS_KEY_PREFIX = "dealo-dismissed:";
  // Keyed on host+path, not the full URL: storefronts rewrite their own query
  // string constantly (tracking params, step markers, login referrers), and
  // keying on href made one AJIO visit fire four identical backend calls in
  // live testing. The path is what actually distinguishes "a different page".
  let lastCheckedKey = null;
  let lastCheckedAt = 0;
  let pollTimer = null;
  const MIN_RECHECK_MS = 3000;

  // A checkout-looking URL is necessary but NOT sufficient. Found in real use
  // 2026-08-31: the popup appeared on github.com, because "github.com/actions/
  // checkout" contains the word "checkout". A plain substring match also hits
  // "descartes", "cartography", "baggage" and so on. So the URL is matched on
  // whole path/query words only, and then the page itself has to actually look
  // like somewhere money changes hands (see hasCommerceSignal).
  // The hash counts: plenty of stores open the cart as a drawer addressed by a
  // fragment rather than a path (boAt redirects /cart to /#cart — caught in
  // live testing, path-only matching missed it entirely). The hostname is
  // deliberately excluded, so a store called "cartify.com" isn't a permanent
  // false positive on every page it serves.
  function urlLooksLikeCheckout() {
    const target = (location.pathname + " " + location.search + " " + location.hash).toLowerCase();
    return self.__dealoConfig.CHECKOUT_URL_KEYWORDS.some((kw) =>
      new RegExp(`(^|[^a-z])${kw}([^a-z]|$)`).test(target)
    );
  }

  // Real evidence this is a shop's checkout, not a page that merely says
  // "checkout". Any ONE of these is enough; none of them is true of GitHub,
  // documentation, or a repo about shopping carts.
  function hasCommerceSignal() {
    // 1. The page prices something in rupees.
    const text = document.body?.innerText || "";
    if (/(?:₹|\brs\.?\s|\binr\s)\s?\d/i.test(text)) return true;

    // 2. The page declares itself a product/order in standard structured data.
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
      if (/"@type"\s*:\s*"(Product|Offer|Order|AggregateOffer)"/i.test(script.textContent || "")) {
        return true;
      }
    }

    // 3. The page says the things only a real checkout says.
    return /\b(place order|proceed to pay|proceed to checkout|order total|order summary|add to cart|delivery address|payment method)\b/i.test(text);
  }

  function isCheckoutPage() {
    return urlLooksLikeCheckout() && hasCommerceSignal();
  }

  function getDomain() {
    return location.hostname.replace(/^www\./, "");
  }

  // Best-effort price read. Tries the two standard, structured places a
  // page's own price data lives (never a per-site scraper) before falling
  // back to a plain-text heuristic. Returns null (not a guess) when nothing
  // reliable is found — the popup then shows a % only, per the trust rule.
  // Shopify publishes the real cart total at /cart.js on every store it runs,
  // which is a large share of Indian direct-to-brand shops (boAt among them).
  // This is a platform-level read, not a per-store scraper: one request that
  // either works or doesn't, and it beats every guess below because it's the
  // shop's own number. Live testing on boAt found 53 rupee amounts on the cart
  // page and no safe way to pick the right one — this is that fix.
  async function shopifyCartTotal() {
    try {
      const res = await fetch("/cart.js", { credentials: "same-origin" });
      if (!res.ok) return null;
      // Deliberately no content-type check: reading that header proved
      // unreliable in testing, and parsing is the real test anyway — a
      // non-Shopify store returns HTML, .json() throws, and we fall through.
      const cart = await res.json();
      // Shopify reports money in paise; item_count guards against empty carts.
      if (!cart || !cart.item_count || typeof cart.total_price !== "number") return null;
      return cart.total_price / 100;
    } catch (e) {
      return null; // not a Shopify store, or it declined — fall through
    }
  }

  // The payable total, read from the small box that holds BOTH the label and
  // the figure. Stores almost always put them in one container even when they
  // render as separate lines — which is why the plain text-pattern reader
  // below found nothing on Myntra ("Total Amount" and "₹4,049" are siblings,
  // not one string).
  //
  // Only strong, unambiguous labels count, and rows that look like MRP,
  // savings or discounts are excluded outright: on Myntra the pre-discount
  // "Total MRP ₹8,596" sits right above the real "Total Amount ₹4,049", and
  // picking the wrong one would size the voucher twice too large.
  const TOTAL_LABEL = /(total amount|amount payable|amount to pay|order total|grand total|total payable|net payable|you pay|to be paid)/i;
  const NOT_A_TOTAL = /(mrp|saved|savings|discount|cashback|coupon)/i;

  function labelledTotal() {
    let last = null;
    for (const el of document.querySelectorAll("div,span,p,td,th,li,section,strong,b,h1,h2,h3,h4")) {
      const t = (el.textContent || "").replace(/\s+/g, " ").trim();
      if (!t || t.length > 60) continue;
      if (!TOTAL_LABEL.test(t) || NOT_A_TOTAL.test(t)) continue;
      const m = t.match(/(?:₹|rs\.?)\s?([\d,]+(?:\.\d{1,2})?)/i);
      if (!m) continue;
      const n = parseFloat(m[1].replace(/,/g, ""));
      // Last match wins: the final payable line renders below the breakdown.
      if (Number.isFinite(n) && n > 0) last = n;
    }
    return last;
  }

  async function readPrice() {
    const fromPlatform = await shopifyCartTotal();
    if (fromPlatform) return fromPlatform;
    return labelledTotal() ?? extractPrice();
  }

  function extractPrice() {
    for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const data = JSON.parse(script.textContent);
        const items = Array.isArray(data) ? data : [data];
        for (const item of items) {
          const offers = item.offers || (item["@graph"] || []).flatMap((g) => (g.offers ? [g.offers] : []));
          const offer = Array.isArray(offers) ? offers[0] : offers;
          const price = offer && (offer.price || offer.lowPrice);
          if (price) {
            const n = parseFloat(String(price).replace(/,/g, ""));
            if (!Number.isNaN(n) && n > 0) return n;
          }
        }
      } catch (e) {
        // not valid/expected JSON-LD shape — skip
      }
    }

    const itemprop = document.querySelector('[itemprop="price"]');
    if (itemprop) {
      const raw = itemprop.getAttribute("content") || itemprop.textContent;
      const n = parseFloat(String(raw).replace(/[^0-9.]/g, ""));
      if (!Number.isNaN(n) && n > 0) return n;
    }

    // Plain-text fallback: a rupee figure sitting right next to a
    // total-like word, e.g. "Order Total ₹1,289" or "To Pay: Rs. 1,289".
    const totalWordPattern = /(order total|grand total|amount payable|to pay|total amount|total)[^₹\d]{0,20}(?:₹|rs\.?)\s?([\d,]+(?:\.\d+)?)/i;
    const match = document.body.innerText.match(totalWordPattern);
    if (match) {
      const n = parseFloat(match[2].replace(/,/g, ""));
      if (!Number.isNaN(n) && n > 0) return n;
    }
    return null;
  }

  function isDismissed(domain) {
    return sessionStorage.getItem(DISMISS_KEY_PREFIX + domain) === "1";
  }

  function markDismissed(domain) {
    sessionStorage.setItem(DISMISS_KEY_PREFIX + domain, "1");
  }

  function affiliateRedirectUrl(pageUrl) {
    return `${self.__dealoConfig.API_BASE}/go?url=${encodeURIComponent(pageUrl)}`;
  }

  // When the extension reloads or auto-updates, content scripts already
  // injected into open tabs are orphaned: chrome.runtime disappears from under
  // them while their timers keep firing. Found in real use 2026-09-01 — an
  // already-open tab threw "Cannot read properties of undefined (reading
  // 'sendMessage')" every poll tick, forever. A Web Store update would do this
  // in every tab a shopper had open, so the orphan has to notice and stop.
  function extensionGone() {
    try { return !chrome.runtime?.id; } catch (e) { return true; }
  }

  function ask(message) {
    return new Promise((resolve) => {
      if (extensionGone()) return resolve(null);
      try {
        chrome.runtime.sendMessage(message, (response) => {
          if (chrome.runtime.lastError || !response?.ok) return resolve(null);
          resolve(response);
        });
      } catch (e) {
        resolve(null); // context died between the check above and the call
      }
    });
  }

  async function askBackground(domain, price) {
    const res = await ask({ type: "voucherCheck", domain, price });
    return res ? res.result : null;
  }

  function hostOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return null; }
  }

  // The shopper is mid-journey and has landed on the voucher partner's site —
  // pick the thread back up instead of behaving like a fresh page.
  function onVoucherSiteFor(trip) {
    const voucherHost = hostOf(trip?.deal?.voucherUrl);
    return Boolean(voucherHost) && getDomain() === voucherHost;
  }

  // ...or they've come back to the store they started from, code in hand.
  function backAtStoreFor(trip) {
    return getDomain() === trip?.store?.domain;
  }

  // Finds the store's gift-card / voucher-code box so Dealo can point at it.
  // No per-store selectors: it looks for the words a gift-card field uses,
  // which is how a person finds it too. Deliberately conservative — pointing
  // at the wrong box is worse than not pointing, so a weak guess returns
  // nothing and the shopper gets the written steps instead.
  const GIFT_WORDS = /gift\s*(card|voucher|certificate)|e-?gift|voucher\s*(code|number)|gift\s*code/i;

  function findGiftCardField() {
    // 1. A text box that names itself — placeholder, label, name or aria text.
    for (const el of document.querySelectorAll("input[type=text], input:not([type]), input[type=tel]")) {
      const selfText = [
        el.placeholder, el.name, el.id, el.getAttribute("aria-label"),
        el.closest("label")?.innerText,
        el.labels?.[0]?.innerText,
      ].filter(Boolean).join(" ");
      if (GIFT_WORDS.test(selfText) && el.offsetParent !== null) {
        return { el, label: "Enter your voucher code here" };
      }
    }

    // 2. Otherwise the payment option you must pick first — on most Indian
    // stores the code box only appears after choosing "Gift Card".
    const clickable = document.querySelectorAll(
      "button, [role=button], label, a, [role=radio], [role=tab]"
    );
    for (const el of clickable) {
      const text = (el.innerText || el.getAttribute("aria-label") || "").trim();
      if (text.length < 40 && GIFT_WORDS.test(text) && el.offsetParent !== null) {
        return { el, label: "Choose this, then enter your code" };
      }
    }
    return null;
  }

  function visibleControls() {
    return [...document.querySelectorAll("button, [role=button], label, [role=radio], a")]
      .filter((el) => el.offsetParent !== null);
  }

  function textOf(el) {
    return (el.innerText || el.getAttribute("aria-label") || "").replace(/\s+/g, " ").trim();
  }

  // The amount button matching what they need to buy. Voucher sites offer a
  // fixed ladder (₹250 / ₹500 / ₹1,000 / ₹2,000 …) plus "Custom", so point at
  // the exact tile when one matches and at Custom when nothing does.
  function findAmountControl(want) {
    if (!want) return null;
    const controls = visibleControls();
    for (const el of controls) {
      const t = textOf(el);
      const m = t.match(/^₹\s?([\d,]+)$/);
      if (m && parseFloat(m[1].replace(/,/g, "")) === want) {
        return { el, label: `Tap ₹${want.toLocaleString("en-IN")}` };
      }
    }
    const custom = controls.find((el) => /^custom$/i.test(textOf(el)));
    if (custom) {
      return { el: custom, label: `Tap Custom, then enter ₹${want.toLocaleString("en-IN")}` };
    }
    return null;
  }

  // The UPI payment option — the whole reason the promised rate holds.
  function findUpiControl() {
    const el = visibleControls().find((c) => /^upi$/i.test(textOf(c)));
    return el ? { el, label: "Choose UPI — that's the better rate" } : null;
  }

  // The hand-holding sequence on the voucher site: which amount, then which
  // payment method. Skips anything it genuinely can't find rather than
  // pointing at something plausible and being wrong.
  function voucherSiteGuideSteps(trip) {
    const d = trip.deal;
    const first = (d.denominationBreakdown || [])[0];
    const want = first ? first.denom : d.voucherAmount;
    return [findAmountControl(want), findUpiControl()].filter(Boolean);
  }

  async function runJourney(trip) {
    if (trip.status === "buying_voucher" && onVoucherSiteFor(trip)) {
      window.__dealoPopup.renderVoucherSiteStep(trip, {
        onShowMe: () => {
          const steps = voucherSiteGuideSteps(trip);
          if (steps.length) window.__dealoPopup.guide(steps);
          else window.__dealoPopup.guideUnavailable();
        },
        onHaveCode: () => {
          window.__dealoPopup.renderCodeEntry(trip, {
            onSave: async (code, pin) => {
              await ask({ type: "tripUpdate", patch: { code, pin, status: "has_code" } });
              // Send them back to the exact page they were buying from.
              location.href = trip.store.returnUrl;
            },
          });
        },
        // Without this, someone who changes their mind gets guided at on every
        // page of the voucher site until the trip expires a week later.
        onAbandon: () => ask({ type: "tripClear" }),
      });
      return true;
    }

    if (trip.status === "has_code" && backAtStoreFor(trip)) {
      window.__dealoPopup.renderBackAtStore(trip, {
        onShowWhere: () => {
          const found = findGiftCardField();
          if (found) {
            window.__dealoPopup.pointAt(found.el, found.label);
          } else {
            // Couldn't find it — say so plainly and fall back to the store's
            // own written steps rather than pointing somewhere hopeful.
            window.__dealoPopup.showWhereFallback();
          }
        },
        onDone: async () => {
          await ask({ type: "tripClear" });
          window.__dealoPopup.renderTripComplete(trip);
        },
      });
      return true;
    }
    return false;
  }

  async function check() {
    // An orphaned copy of this script can't do anything useful and would throw
    // on every tick — stop the timer and let this tab go quiet until it reloads.
    if (extensionGone()) {
      clearInterval(pollTimer);
      return;
    }

    const now = Date.now();
    const key = location.hostname + location.pathname;
    if (key === lastCheckedKey) return;               // one check per page/view
    if (now - lastCheckedAt < MIN_RECHECK_MS) return; // and never in a burst
    lastCheckedKey = key;
    lastCheckedAt = now;

    // A trip in progress outranks everything: the shopper is part-way through
    // saving money, so the next instruction matters more than a fresh check.
    // Asked once per page view (the guards above), not on every poll tick.
    const tripRes = await ask({ type: "tripGet" });
    const trip = tripRes?.trip || null;
    if (trip && await runJourney(trip)) return;

    if (!isCheckoutPage()) return;

    const domain = getDomain();
    if (isDismissed(domain)) return;

    const price = await readPrice();
    const result = await askBackground(domain, price);
    if (!result) return; // backend unreachable — stay silent, no broken UI

    // A voucher worth less than the errand is worse than no voucher: the
    // shopper spends real effort for a trivial saving and stops trusting the
    // popup. Only applies when the total is known — with no total there's no
    // rupee figure to judge, and the percentage is all anyone has.
    const cfg = self.__dealoConfig;
    const tooSmall =
      result.has_voucher &&
      result.priced &&
      result.saving != null &&
      result.saving < cfg.MIN_SAVING_TO_OFFER &&
      (result.pct ?? 0) < cfg.MIN_RATE_TO_OFFER;

    if (result.has_voucher && !tooSmall) {
      // Carry the order total through: the popup needs it to state the saving
      // as a share of THIS order rather than the voucher's headline rate.
      result.cart_total = price;
      window.__dealoPopup.renderVoucherFound(result, async () => {
        // Save the trip BEFORE handing them off. This is the moment Dealo used
        // to forget everything — the shopper leaves for the voucher site and
        // there was no way back to what they were buying, for how much, or
        // what to do next. Everything downstream reads this note.
        await ask({
          type: "tripStart",
          trip: { domain, returnUrl: location.href, cartTotal: price, deal: result },
        });
        window.open(result.voucher_url, "_blank");
        markDismissed(domain);
      });
    } else {
      window.__dealoPopup.renderNoDeal(() => {
        markDismissed(domain);
        location.href = affiliateRedirectUrl(location.href);
      });
    }
  }

  // Storefronts routinely swap in the cart without a full page load, and a
  // content script only runs once per real navigation — so without this the
  // popup would silently never appear on those sites. Polling the address
  // bar (rather than patching history, which a content script's isolated
  // world can't intercept, or asking for the webNavigation permission,
  // which widens the install warning) is the cheap, permission-free way to
  // catch it.
  pollTimer = setInterval(check, self.__dealoConfig.URL_POLL_MS);
  check();
})();
