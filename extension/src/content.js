// Orchestrator: is this a checkout page? -> read domain + price -> ask the
// background worker -> show whichever popup case applies.
(() => {
  const DISMISS_KEY_PREFIX = "dealo-dismissed:";
  // Keyed on host+path+hash, not the full URL: storefronts rewrite their own
  // query string constantly (tracking params, step markers, login referrers),
  // and keying on href made one AJIO visit fire four identical backend calls
  // in live testing. Everything except the query string distinguishes "a
  // different page" — see the note where the key is built.
  let lastCheckedKey = null;
  let lastCheckedAt = 0;
  const MIN_RECHECK_MS = 3000;

  // A cart-shaped address whose page has not drawn its prices yet is the
  // ordinary state of a single-page storefront for the first second or so
  // after it opens — the address changes before the cart is rendered. Dealo
  // used to conclude "not a checkout" from that empty page and, because it
  // checks a given view only once, never look again: on boAt the ₹350 panel
  // appeared only if you jogged the address bar. So a cart-shaped address
  // that hasn't produced a commerce signal yet is treated as "too early",
  // not as "no", and is looked at again a few times before giving up.
  const SIGNAL_RETRY_MS = 1200;
  const SIGNAL_RETRIES = 4;
  let retriesLeftForKey = SIGNAL_RETRIES;
  let retryKey = null;

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
    // 1. The page prices something in rupees. Dealo's own panel is full of
    // them, so it must not be allowed to vouch for the page it is sitting on.
    const text = pageTextWithoutDealo();
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
  const TOTAL_LABEL = /(total amount|amount payable|amount to pay|order total|grand total|total price|total payable|net payable|you pay|to be paid)/i;
  // "applied" earns its place here: shops render the discount as a badge —
  // Frido's is "₹8,001 applied!" — and put it inside the row labelled Total
  // Price, so a reader looking for a total finds the discount instead. That
  // read a ₹16,999 order as ₹8,001 and quoted vouchers for less than half of
  // it. A figure the page describes as applied is a reduction, never a total.
  const NOT_A_TOTAL = /(mrp|saved|savings|you save|discount|applied|cashback|coupon)/i;

  // Every rupee figure in a piece of text, in the order they appear.
  function amountsIn(text) {
    return [...text.matchAll(/(?:₹|rs\.?)\s?([\d,]+(?:\.\d{1,2})?)/gi)]
      .map((m) => parseFloat(m[1].replace(/,/g, "")))
      .filter((n) => Number.isFinite(n) && n > 0);
  }

  // Dealo's own panel is part of the page once it renders, and it is full of
  // rupee figures next to the exact words the reader below looks for. Its
  // trade diagram says "₹14,562 is all you pay", and "you pay" is a total
  // label — so on its second look Dealo read its own output back as the
  // shop's price, asked the server about that smaller number, and quoted a
  // smaller plan. A ₹16,999 Frido order came back as ₹8,000 of vouchers.
  //
  // Every read of the page must therefore skip anything Dealo drew itself.
  // Reported 2026-09-09; caused by copy added the day before.
  const DEALO_OWN = "#dealo-popup-root, #dealo-pointer";

  function isDealoOwn(el) {
    return Boolean(el.closest && el.closest(DEALO_OWN));
  }

  // The page's text with Dealo's own contribution removed.
  function pageTextWithoutDealo() {
    const body = document.body?.innerText || "";
    let text = body;
    for (const own of document.querySelectorAll(DEALO_OWN)) {
      const mine = own.innerText;
      if (mine) text = text.split(mine).join(" ");
    }
    return text;
  }

  function labelledTotal() {
    let last = null;
    for (const el of document.querySelectorAll("div,span,p,td,th,li,section,strong,b,h1,h2,h3,h4")) {
      if (isDealoOwn(el)) continue;
      const t = (el.textContent || "").replace(/\s+/g, " ").trim();
      if (!t || t.length > 60) continue;
      if (!TOTAL_LABEL.test(t) || NOT_A_TOTAL.test(t)) continue;
      const nums = amountsIn(t);
      if (!nums.length) continue;
      // The LAST figure in the row, not the first. A discounted total renders
      // the old price struck through and the real one after it — Frido's
      // "Total Price ₹40,000 ₹29,999" — and taking the first figure there
      // reads the price nobody is paying. Live-tested 2026-09-07: that read
      // sized a voucher purchase at ₹40,000 for a ₹29,999 order.
      const n = nums[nums.length - 1];
      // And the last matching row wins: the final payable line renders below
      // the breakdown.
      if (Number.isFinite(n) && n > 0) last = n;
    }
    return last;
  }

  // Never plan a purchase bigger than what the shopper is actually going to
  // pay. When two credible reads disagree, the lower one wins.
  //
  // This is not fussiness. Shopify's own /cart.js reports the cart before
  // discounts applied by a third-party checkout — Frido runs GoKwik, which
  // takes ₹10,001 off at the checkout step, so cart.js said ₹40,000 while the
  // shopper owed ₹29,999. Trusting the platform figure there told someone to
  // buy ₹40,000 of store credit for a ₹29,999 order and strand ₹10,001 in a
  // wallet they may never spend. Found in live testing 2026-09-07.
  //
  // The two errors are not symmetrical, which is why the tie-break is "lower"
  // and not "the platform knows best": buying too little means paying the
  // small remainder by card, an annoyance. Buying too much means money the
  // shopper cannot get back.
  async function readPrice() {
    const fromPlatform = await shopifyCartTotal();
    const labelled = labelledTotal();
    if (fromPlatform && labelled) return Math.min(fromPlatform, labelled);
    return fromPlatform ?? labelled ?? extractPrice();
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

    const itemprop = [...document.querySelectorAll('[itemprop="price"]')].find((el) => !isDealoOwn(el));
    if (itemprop) {
      const raw = itemprop.getAttribute("content") || itemprop.textContent;
      const n = parseFloat(String(raw).replace(/[^0-9.]/g, ""));
      if (!Number.isNaN(n) && n > 0) return n;
    }

    // Plain-text fallback: a rupee figure sitting right next to a
    // total-like word, e.g. "Order Total ₹1,289" or "To Pay: Rs. 1,289".
    const totalWordPattern = /(order total|grand total|amount payable|to pay|total amount|total)[^₹\d]{0,20}(?:₹|rs\.?)\s?([\d,]+(?:\.\d+)?)/i;
    const match = pageTextWithoutDealo().match(totalWordPattern);
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
  // them. Found in real use 2026-09-01 — an already-open tab threw "Cannot
  // read properties of undefined (reading 'sendMessage')" on every check. A
  // Web Store update does this in every tab a shopper has open, so the orphan
  // has to notice and stay quiet until the tab reloads.
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

  // The instant-discount option — the whole reason the promised saving is real.
  //
  // This is the single most dangerous gap Dealo has had. Maximize sells the
  // same voucher two ways and DEFAULTS to the wrong one:
  //
  //   ₹930.00  "7% Off"   — Instant ₹70 off. MaxCoins excluded.
  //   ₹1000.00 "7.1% Earn" — Pay full amount, earn 71 MaxCoins.  <- preselected,
  //                                                    and badged "Best Discount"
  //
  // Dealo quotes the 7% instant figure, because cashback and loyalty coins are
  // never counted as a saving. But it used to guide the shopper through the
  // amount and the payment method and say nothing about this — so someone who
  // did exactly what Dealo told them paid full price, collected coins they
  // never asked for, and the rupees Dealo promised never arrived. Reported by
  // the product owner 2026-09-07; a wrong result that looks like it worked is
  // the worst thing this product can do.
  //
  // Matching is on the seller's own words rather than any per-site selector.
  // "Instant" is the discriminator, and "earn" is the counter-signal — note
  // the instant option's text mentions MaxCoins too ("MaxCoins excluded"), so
  // matching on that word alone would pick exactly the wrong box.
  const INSTANT_OFFER = /instant/i;
  const EARNS_INSTEAD = /\bearn(s|ed|ing)?\b/i;

  function isSelected(input) {
    return input.checked === true || input.getAttribute("aria-checked") === "true";
  }

  function findInstantDiscountControl() {
    for (const input of document.querySelectorAll('input[type="radio"], [role="radio"]')) {
      // Climb out of the input to the small box that carries the option's
      // wording. Bounded, and it stops at the first box with real text — one
      // more level up is the whole list, where both options' words run
      // together and the counter-signal would be meaningless.
      let node = input;
      for (let up = 0; up < 5 && node; up += 1) {
        const text = (node.innerText || "").replace(/\s+/g, " ").trim();
        if (text.length >= 12 && text.length <= 220) {
          if (INSTANT_OFFER.test(text) && !EARNS_INSTEAD.test(text)) {
            // Already chosen — there is nothing to tell them to do, and
            // pointing at a done thing wastes a step.
            if (isSelected(input)) return null;
            const box = node.offsetParent !== null ? node : input;
            return { el: box, label: "Choose the instant discount, not coins" };
          }
          break;
        }
        node = node.parentElement;
      }
    }
    return null;
  }

  // The UPI payment option — the whole reason the promised rate holds.
  function findUpiControl() {
    const el = visibleControls().find((c) => /^upi$/i.test(textOf(c)));
    return el ? { el, label: "Choose UPI — that's the better rate" } : null;
  }

  // The last button in the journey. Same conservative, word-based matching
  // as the gift-card box: a short label that reads like the real thing, or
  // nothing at all — Dealo never guesses at the store's own "Buy Now" or
  // "Add to Cart" buttons elsewhere on the page.
  const ORDER_WORDS = /^(place( your)? order|pay now|make( the)? payment|confirm( and)? (pay|order)|proceed to pay|complete (purchase|payment)|pay\s?₹?\s?[\d,]*)$/i;
  function findPlaceOrderControl() {
    const el = visibleControls().find((c) => {
      const t = textOf(c);
      return t.length < 40 && ORDER_WORDS.test(t);
    });
    return el ? { el, label: "Place your order here" } : null;
  }

  // Whether the page itself is saying the order actually went through —
  // checked before ever declaring the trip complete on Dealo's own say-so.
  // The same "look at the real page, don't assume" approach already used to
  // catch Myntra's "Site Maintenance" placeholder page elsewhere in Dealo.
  const CONFIRM_URL = /order[-_]?(confirm|success|placed|received)|thank[-_]?you/i;
  const CONFIRM_TEXT = /order (confirmed|placed|successful)|thank you for (your|the) order|your order has been placed|order\s*(id|number)\s*[:#]/i;
  function looksLikeOrderConfirmed() {
    if (CONFIRM_URL.test(location.pathname)) return true;
    const bodyText = (document.body?.innerText || "").slice(0, 4000);
    return CONFIRM_TEXT.test(bodyText);
  }

  // Some deals need several separate voucher purchases rather than one
  // combined checkout (a reseller limits how many of a denomination it'll
  // sell per order). `denominationBreakdown` is {denom, count} pairs — this
  // flattens it into one amount per purchase, e.g. [{denom:2500,count:2},
  // {denom:1000,count:1}] -> [2500, 2500, 1000], so each purchase in turn can
  // be guided at its own amount. Falls back to the single headline amount
  // when there's no breakdown at all.
  function perTxnAmounts(deal) {
    const list = [];
    (deal.denominationBreakdown || []).forEach((b) => {
      for (let i = 0; i < (b.count || 1); i++) list.push(b.denom);
    });
    return list.length ? list : [deal.voucherAmount].filter(Boolean);
  }

  // The hand-holding sequence on the voucher site, in the order the shopper
  // has to do it: which amount, then take the discount as money rather than
  // coins, then which payment method.
  //
  // Every step is a function, not a resolved element. The page redraws its
  // price options as soon as an amount is tapped, so the instant-discount box
  // that exists now is not the one that will be there when the shopper
  // reaches that step — see guide() in popup.js. Anything genuinely absent is
  // skipped rather than approximated.
  function voucherSiteGuideSteps(want) {
    return [
      () => findAmountControl(want),
      () => findInstantDiscountControl(),
      () => findUpiControl(),
    ];
  }

  // Collecting the codes, one after another, without leaving the loop.
  //
  // This used to hand control back to runJourney after every code, which
  // re-rendered the BUYING screen — "add these to your basket" — at a shopper
  // who had already bought them. Harmless-looking and completely
  // disorienting: the six codes they were part-way through entering looked
  // like six more purchases they had to make.
  //
  // Calls itself instead, so entering six codes is six presses of Enter, and
  // only the last one sends them back to the store.
  function collectCode(trip, index, total) {
    window.__dealoPopup.renderCodeEntry(trip, { index, total }, {
      onSave: async (code, pin) => {
        const next = await ask({ type: "tripAddCode", code, pin });
        const updated = next?.trip;
        if (!updated) return;
        if (updated.status === "has_code") {
          location.href = trip.store.returnUrl;
          return;
        }
        collectCode(updated, (updated.codes || []).length, total);
      },
    });
  }

  async function runJourney(trip) {
    if (trip.status === "buying_voucher" && onVoucherSiteFor(trip)) {
      const codes = trip.codes || [];
      const index = codes.length; // how many codes are already in hand
      // Every plan is one checkout now, so the buying screen shows the whole
      // basket rather than stepping through it. `want` is only the amount the
      // guided pointer aims at — the first denomination in the plan, which is
      // the button they have to press on the voucher site.
      const total = Math.max(perTxnAmounts(trip.deal).length, 1);
      const want = (trip.deal.denominationBreakdown || [])[0]?.denom
        || perTxnAmounts(trip.deal)[0]
        || trip.deal.voucherAmount;

      window.__dealoPopup.renderVoucherSiteStep(trip, { want }, {
        onShowMe: () => {
          // guide() reports whether it found anything at all to point at, so
          // a page it can't read falls back to written steps instead of a
          // sequence that shows nothing.
          if (!window.__dealoPopup.guide(voucherSiteGuideSteps(want))) {
            window.__dealoPopup.guideUnavailable();
          }
        },
        onHaveCode: () => collectCode(trip, index, total),
        // Without this, someone who changes their mind gets guided at on every
        // page of the voucher site until the trip expires a week later.
        onAbandon: () => ask({ type: "tripClear" }),
      });
      return true;
    }

    if (trip.status === "has_code" && backAtStoreFor(trip)) {
      window.__dealoPopup.renderBackAtStore(trip, {
        // "Start over" — see renderBackAtStore. Clears the trip so the next
        // look at this cart is a fresh one.
        onAbandon: () => ask({ type: "tripClear" }),
        // Remembered on the trip rather than in the page, because the whole
        // point is that it survives the shopper moving from cart to checkout.
        onStepsToggle: (open) => ask({ type: "tripUpdate", patch: { stepsOpen: open } }),
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
        // The code is applied, not the order — this used to clear the trip
        // and declare victory right here, leaving nobody pointing at "Place
        // Order" and nothing checking whether the order actually went
        // through. Advance the trip instead of ending it.
        onDone: async () => {
          const next = await ask({ type: "tripUpdate", patch: { status: "placing_order" } });
          await runJourney(next?.trip || { ...trip, status: "placing_order" });
        },
      });
      return true;
    }

    // Last leg: the code is in, and the only thing left is the shopper's own
    // final tap. Dealo never takes that tap for them (see the "point, don't
    // push" rule) — it points at the button, then watches the page itself
    // for proof the order went through, the same way `check()` already
    // re-runs on every page-view change (a poll, not a new mechanism).
    if (trip.status === "placing_order" && backAtStoreFor(trip)) {
      if (looksLikeOrderConfirmed()) {
        await ask({ type: "tripClear" });
        window.__dealoPopup.renderTripComplete(trip);
        return true;
      }
      window.__dealoPopup.renderPlaceOrder(trip, {
        onShowMe: () => {
          const found = findPlaceOrderControl();
          if (found) {
            window.__dealoPopup.pointAt(found.el, found.label);
          } else {
            window.__dealoPopup.showWhereFallback();
          }
        },
        // A fallback for a confirmation page Dealo doesn't recognise — the
        // shopper's own word closes the loop rather than the popup lingering
        // on a store that phrases its confirmation unusually.
        onDone: async () => {
          await ask({ type: "tripClear" });
          window.__dealoPopup.renderTripComplete(trip);
        },
      });
      return true;
    }
    return false;
  }

  // `force` is a shopper clicking the Dealo icon: an explicit request, which
  // outranks both the "already looked at this page" guard and an earlier
  // dismissal of this store.
  async function check(force = false, isRetry = false) {
    // An orphaned copy of this script — the extension was reloaded or removed
    // out from under this tab — can't do anything useful. Go quiet.
    if (extensionGone()) return;

    const now = Date.now();
    // The hash counts as part of "which page is this", because it counts in
    // urlLooksLikeCheckout: boAt and others open the cart as a drawer at /#cart
    // rather than a path. Keying on path alone meant arriving at the cart from
    // the same page's home view looked like the page hadn't changed, and the
    // check was skipped. The query string stays out — storefronts rewrite it
    // constantly with tracking parameters that change nothing.
    const key = location.hostname + location.pathname + location.hash;
    if (!force && !isRetry) {
      if (key === lastCheckedKey) return;               // one check per page/view
      if (now - lastCheckedAt < MIN_RECHECK_MS) return; // and never in a burst
    }
    // A retry is Dealo looking again at a page it has not yet made up its mind
    // about, so the burst limiter must not swallow it — the retries are
    // 1.2s apart and the limiter is 3s, which would have made the whole
    // too-early fix inert. It is still bounded: SIGNAL_RETRIES attempts, and
    // only ever on an address that already looks like a checkout.
    // lastCheckedAt rate-limits bursts straight away, but lastCheckedKey — the
    // "already looked at this view" guard — is only set once an actual
    // decision has been reached, so a too-early look doesn't count as one.
    lastCheckedAt = now;
    if (retryKey !== key) {
      retryKey = key;
      retriesLeftForKey = SIGNAL_RETRIES;
    }

    // A trip in progress outranks everything: the shopper is part-way through
    // saving money, so the next instruction matters more than a fresh check.
    // Asked once per page view (the guards above), not on every poll tick.
    const tripRes = await ask({ type: "tripGet" });
    const trip = tripRes?.trip || null;
    if (trip && await runJourney(trip)) return;

    if (!isCheckoutPage()) {
      if (urlLooksLikeCheckout() && retriesLeftForKey > 0) {
        retriesLeftForKey -= 1;
        setTimeout(() => check(force, true), SIGNAL_RETRY_MS);
        return; // deliberately without setting lastCheckedKey — not a decision
      }
      lastCheckedKey = key;
      return;
    }
    lastCheckedKey = key;

    const domain = getDomain();
    if (!force && isDismissed(domain)) return;

    const price = await readPrice();
    const result = await askBackground(domain, price);
    if (!result) return; // backend unreachable — stay silent, no broken UI

    // A voucher worth less than the errand is worse than no voucher: the
    // shopper spends real effort for a trivial saving and stops trusting the
    // popup. Only applies when the total is known — with no total there's no
    // rupee figure to judge, and the percentage is all anyone has.
    //
    // Two ways to be worth the errand, and a good rate is no longer enough on
    // its own: 7% of a small basket is small. See config.js for the numbers
    // and why they moved.
    const cfg = self.__dealoConfig;
    const saving = result.saving ?? 0;
    const pct = result.pct ?? 0;
    const worthTheErrand =
      pct >= cfg.MIN_RATE_FLOOR &&
      ((pct >= cfg.MIN_RATE_TO_OFFER && saving >= cfg.MIN_SAVING_AT_RATE) ||
        saving >= cfg.MIN_SAVING_ALONE);
    // A rate under the floor is too thin whatever the basket, so it doesn't
    // need a readable total to be judged — and it must not need one. Without
    // this, an Amazon cart whose total Dealo couldn't read fell straight past
    // the rupee test and got offered as a real deal, headlined "0.75% off".
    // Found 2026-09-07 while checking what Amazon actually shows.
    const rateTooThin = pct > 0 && pct < cfg.MIN_RATE_FLOOR;
    const tooSmall =
      result.has_voucher &&
      (rateTooThin || (result.priced && result.saving != null && !worthTheErrand));

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
      // Two different silences, and saying "no discounts available" for both
      // was a small lie: on a too-small deal there IS one, it just isn't worth
      // the errand. Saying so is the more trustworthy answer and it shows the
      // shopper Dealo actually looked. Either way the Okay button is the same
      // — it routes through the affiliate link before returning them to the
      // page they were on, which is how Dealo is paid when it has nothing to
      // sell them.
      // Two different actions now, and the difference is the whole point.
      // Dismissing costs Dealo nothing and earns Dealo nothing; the affiliate
      // hop happens only when the shopper presses the button that says so.
      // See renderNoDeal for why that separation exists.
      const onSupport = () => {
        markDismissed(domain);
        location.href = affiliateRedirectUrl(location.href);
      };
      const onDismiss = () => markDismissed(domain);
      window.__dealoPopup.renderNoDeal(onSupport, onDismiss, tooSmall ? result : null);
    }
  }

  // --- When to look again --------------------------------------------------
  //
  // Storefronts routinely swap in the cart without a full page load, so one
  // run at page load isn't enough. This used to be a 700ms timer that ran for
  // the life of every tab on every site. Two things replace it, both of which
  // fire exactly when something actually happens and cost nothing in between:
  //
  //   * the background worker, which the browser tells about every navigation
  //     including the in-page kind (see nudge() in background.js), and
  //   * popstate/hashchange here, which catch a cart drawer opening on the
  //     spot without waiting for a round trip.
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "dealoRecheck") check(msg.force);
  });
  addEventListener("popstate", () => check());
  addEventListener("hashchange", () => check());

  check();
})();
