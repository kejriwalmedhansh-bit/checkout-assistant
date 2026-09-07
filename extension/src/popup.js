// Builds and injects the floating checkout popup. Two variants:
//   Case A — a real voucher deal was found (renderVoucherFound)
//   Case B — nothing found, "Honey"-style Okay button (renderNoDeal)
window.__dealoPopup = (() => {
  let escHandler = null;

  function esc(str) {
    const d = document.createElement("div");
    d.textContent = str == null ? "" : String(str);
    return d.innerHTML;
  }

  const SOURCE_NAMES = { gyftr: "Gyftr", maximize: "Maximize", buyhatke: "BuyHatke" };
  function sourceName(src) {
    return SOURCE_NAMES[(src || "").toLowerCase()] || "our voucher partner";
  }

  function rupees(n) {
    return Math.round(n).toLocaleString("en-IN");
  }

  // Copying the code is the single most important action in the journey, and
  // the modern clipboard API is blocked outright on some pages. Fall back to
  // the old select-and-copy trick rather than silently failing there.
  function copyText(text) {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => legacyCopy(text));
    } else {
      legacyCopy(text);
    }
  }

  function legacyCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.cssText = "position:fixed;opacity:0;pointer-events:none;";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* nothing more we can do */ }
    ta.remove();
  }

  // "a AJIO Gift Voucher" read as broken in live testing — brand names start
  // with every letter, so the article has to follow the name.
  function article(name) {
    return /^[aeiou]/i.test((name || "").trim()) ? "an" : "a";
  }

  // Line-drawn icons, inline so nothing is fetched and nothing depends on the
  // host page's own styles. Each one replaces words that were doing its job.
  const ICON = {
    voucher: `<path d="M3 7h18v4a2 2 0 0 0 0 4v4H3v-4a2 2 0 0 0 0-4V7z"/><path d="M12 7v12" stroke-dasharray="2 2.5"/>`,
    bag: `<path d="M4 8h16l-1.2 11a2 2 0 0 1-2 1.8H7.2a2 2 0 0 1-2-1.8L4 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>`,
    check: `<path d="M20 6L9 17l-5-5"/>`,
    arrow: `<path d="M5 12h13M13 6l6 6-6 6"/>`,
    cross: `<path d="M18 6L6 18M6 6l12 12"/>`,
    copy: `<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>`,
    target: `<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.6"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>`,
    info: `<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.6v.1"/>`,
    lock: `<rect x="4" y="10.5" width="16" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>`,
    heart: `<path d="M12 20s-7-4.4-7-9.3A3.9 3.9 0 0 1 12 8a3.9 3.9 0 0 1 7 2.7C19 15.6 12 20 12 20z"/>`,
    link: `<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7L12.5 19.5"/>`,
  };

  function svg(name, size = 16, color = "currentColor", width = 2) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none"
      stroke="${color}" stroke-width="${width}" stroke-linecap="round"
      stroke-linejoin="round" aria-hidden="true">${ICON[name]}</svg>`;
  }

  // Cut a brand's redemption paragraph down to its first instruction: drop
  // the "Alternatively…" branch, the sign-up aside, and everything after the
  // first sentence. Amazon's step 2 is 3 sentences long as written.
  function shortenStep(text) {
    let s = String(text || "").replace(/\s+/g, " ").trim();
    s = s.split(/\.\s+(?:Alternatively|If you are not|Please note|Note:)/i)[0];
    const firstSentence = s.match(/^.*?[.!?](?=\s|$)/);
    if (firstSentence && firstSentence[0].length > 25) s = firstSentence[0];
    return s.length > 110 ? s.slice(0, 107).trimEnd() + "…" : s;
  }

  function firstUrlIn(steps) {
    for (const s of steps) {
      const m = String(s || "").match(/https?:\/\/[^\s,)"']+|(?:^|\s)(www\.[^\s,)"']+)/i);
      if (m) {
        const raw = (m[0] || "").trim().replace(/[.,]$/, "");
        return raw.startsWith("http") ? raw : `https://${raw}`;
      }
    }
    return null;
  }

  function prettyHost(url) {
    try {
      const u = new URL(url);
      return (u.hostname.replace(/^www\./, "") + u.pathname).replace(/\/$/, "");
    } catch (e) {
      return url;
    }
  }

  function dots(step) {
    return `<span class="dealo-dots">${[1, 2, 3]
      .map((n) => `<span class="dealo-dot${n < step ? " dealo-dot-done" : n === step ? " dealo-dot-on" : ""}"></span>`)
      .join("")}</span>`;
  }

  // The headline switches between a percentage and a rupee figure at a
  // threshold, because "You save ₹35" undersells a real 7% deal while
  // "You save ₹850" beats any percentage. Falls back to the percentage
  // whenever the order total couldn't be read at all.
  function headlineFigure(deal) {
    const d = deal.deal ?? deal;
    const saving = d.saving;
    const priced = d.priced;
    const orderTotal = d.cartTotal ?? deal.cart_total;

    // Rupees whenever the order total is known — which, given the minimum
    // saving rule, is every offer that gets this far. A concrete figure beats
    // a percentage, and the percentage was hiding the number that persuades.
    if (priced && saving != null) {
      return { big: `₹${rupees(saving)}`, caption: "saved on this order" };
    }
    // No total read, so no rupee figure can be stated honestly. The voucher's
    // own rate is all we know — and it's the rate on the voucher, not on the
    // order, so it's captioned as such rather than "off this order".
    return { big: `${d.pct}%`, caption: "off with a voucher" };
  }

  // Most storefronts park a support-chat bubble in the bottom-right — landing
  // our card on top of theirs looks broken and buries whichever is behind.
  // If something fixed is already sitting there, move to the other side.
  function cornerIsOccupied() {
    const x = window.innerWidth - 60;
    const y = window.innerHeight - 60;
    return document.elementsFromPoint(x, y).some((el) => {
      if (el === document.body || el === document.documentElement) return false;
      if (el.closest("#dealo-popup-root")) return false;
      return getComputedStyle(el).position === "fixed";
    });
  }

  function mount() {
    let root = document.getElementById("dealo-popup-root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "dealo-popup-root";
    document.documentElement.appendChild(root);
    if (cornerIsOccupied()) root.classList.add("dealo-shifted");
    return root;
  }

  function close() {
    const root = document.getElementById("dealo-popup-root");
    if (root) root.remove();
    if (escHandler) {
      document.removeEventListener("keydown", escHandler, true);
      escHandler = null;
    }
  }

  // `step` (1-3) shows progress as dots in place of a "Step 2 of 3" line;
  // omitted on screens that aren't part of the journey.
  function card(innerHtml, step) {
    const root = mount();
    root.innerHTML = `
      <div class="dealo-card" role="dialog" aria-live="polite" aria-label="Dealo savings">
        <div class="dealo-header">
          <span class="dealo-brand">deal<span class="dealo-brand-o">o</span></span>
          ${step ? dots(step) : ""}
          <button class="dealo-close" aria-label="Dismiss">&times;</button>
        </div>
        ${innerHtml}
      </div>
    `;
    root.querySelector(".dealo-close").addEventListener("click", close);
    escHandler = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", escHandler, true);
    return root;
  }

  // design-system/dealo/MASTER.md: a "buy a code first, then use it" flow
  // MUST come with a plain explanation of why it's legitimate — without one
  // it reads as a scam pattern. Kept behind a toggle so the card stays small.
  // The same trade drawn rather than described. This was four sentences of
  // prose, and the shopper's verdict on it was "so much text, make it symbolic
  // to make it easy to understand" (2026-09-07). Two amounts and an arrow say
  // it: this much credit, for this much money.
  function explanationBody(deal) {
    const brand = esc(deal.brand_name);
    if (!deal.priced || deal.effective_price == null) {
      return `<div class="dealo-trade-note">${brand} vouchers sell for
              ${esc(deal.pct)}% less than they are worth. Spend one here like a gift card.</div>`;
    }
    const face = rupees(deal.effective_price + deal.saving);
    const paid = rupees(deal.effective_price);
    return `
      <div class="dealo-trade">
        <div class="dealo-trade-half">
          <div class="dealo-trade-amount">₹${face}</div>
          <div class="dealo-trade-label">of ${brand} credit</div>
        </div>
        ${svg("arrow", 15, "#C7BFAF", 2.2)}
        <div class="dealo-trade-half">
          <div class="dealo-trade-amount dealo-trade-pay">₹${paid}</div>
          <div class="dealo-trade-label">is all you pay</div>
        </div>
      </div>
      <div class="dealo-trade-note">Spend it on this order, like a gift card.</div>`;
  }

  // Dots reflect whichever code card is actually scrolled into view, and
  // clicking one scrolls there — the same swipe-or-tap pattern as the rest
  // of the journey, just for moving between codes instead of screens.
  function wireCodeCarousel(root) {
    const carousel = root.querySelector(".dealo-code-carousel");
    const dots = [...root.querySelectorAll(".dealo-code-dot")];
    if (!carousel || !dots.length) return;
    dots.forEach((dot, i) => {
      dot.addEventListener("click", () => {
        const target = carousel.children[i];
        if (target) carousel.scrollTo({ left: target.offsetLeft, behavior: "smooth" });
      });
    });
    let ticking = false;
    carousel.addEventListener("scroll", () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const idx = Math.round(carousel.scrollLeft / carousel.clientWidth);
        dots.forEach((d, i) => d.classList.toggle("dealo-code-dot-on", i === idx));
        ticking = false;
      });
    });
  }

  // `onToggle` lets a caller remember the choice. Without it, a disclosure
  // reopens closed on the next page — which is how a shopper who had opened
  // the redemption steps on the cart page arrived at checkout to find them
  // gone, at exactly the moment they needed them. Reported 2026-09-07:
  // "it left me lost as a user."
  function wireExplainToggle(root, onToggle) {
    const toggle = root.querySelector(".dealo-explain-toggle");
    const panel = root.querySelector(".dealo-explain");
    if (!toggle || !panel) return;
    // Keep the original label (icon included) rather than overwriting it with
    // hardcoded text — each screen's toggle now says something different.
    const original = toggle.innerHTML;
    const paint = () => {
      toggle.setAttribute("aria-expanded", String(!panel.hidden));
      toggle.innerHTML = panel.hidden ? original : "hide";
    };
    paint();
    toggle.addEventListener("click", () => {
      panel.hidden = !panel.hidden;
      paint();
      onToggle?.(!panel.hidden);
    });
  }

  function renderVoucherFound(deal, onOpenVoucher) {
    const { big, caption } = headlineFigure(deal);
    // The three-icon strip answers "how does this work?" before it's asked:
    // buy a voucher, pay with it, done. That used to be a link to a paragraph.
    const strip = `
      <div class="dealo-journey">
        <div class="dealo-j-step">${svg("voucher", 20, "#C2712F", 1.8)}<span>voucher</span></div>
        ${svg("arrow", 13, "#C7BFAF", 2.2)}
        <div class="dealo-j-step">${svg("bag", 20, "#1F3A5F", 1.8)}<span>pay</span></div>
        ${svg("arrow", 13, "#C7BFAF", 2.2)}
        <div class="dealo-j-step">${svg("check", 20, "#4A9B8E", 2)}<span>done</span></div>
      </div>`;

    // What they are about to be sent to buy, stated BEFORE they agree to go.
    // Being sent to a voucher site and only then told "voucher 1 of 8" is what
    // a shopper described as being asked to buy blindly: "I wouldn't trust
    // Dealo to randomly have me buy vouchers and then expect everything to
    // work out. That's not how a user thinks." (2026-09-07)
    const plan = deal.purchase_breakdown
      ? `<div class="dealo-plan">
           <span class="dealo-plan-buy">${esc(deal.purchase_breakdown)}</span>
           <span class="dealo-plan-where">at ${esc(sourceName(deal.voucher_source))}</span>
         </div>`
      : "";

    const root = card(`
      <div class="dealo-figure dealo-figure-tight">${big}</div>
      <div class="dealo-caption">${caption} at ${esc(deal.brand_name)}</div>
      ${plan}
      ${strip}
      <button class="dealo-button dealo-ring dealo-withicon" id="dealo-open-voucher">
        ${svg("voucher", 16, "currentColor", 1.9)} Get voucher
      </button>
      <button class="dealo-explain-toggle dealo-centered" aria-expanded="false">
        ${svg("info", 13, "currentColor", 2)} how it works
      </button>
      <div class="dealo-explain" hidden>${explanationBody(deal)}</div>
    `, 1);
    wireExplainToggle(root);
    root.querySelector("#dealo-open-voucher").addEventListener("click", () => {
      onOpenVoucher();
      close();
    });
  }

  // `smallDeal` is a real voucher that didn't clear the worth-the-errand bar
  // (see config.js). Naming the figure is deliberate: "no discounts available"
  // on a shop that plainly has one reads as Dealo being broken or lazy, where
  // "only ₹83 off" reads as Dealo having checked and made a judgement. Same
  // two choices either way.
  //
  // The affiliate click is a CHOICE here, not a side effect of dismissing the
  // panel. It used to be the latter: "Okay" quietly sent the shopper through
  // Dealo's affiliate link and back, which places Dealo's cookie last and
  // takes the commission from whoever actually sent them to the shop.
  //
  // That is precisely what Honey was doing, and in the eighteen months after a
  // YouTuber demonstrated it Honey lost seven million users, was thrown out of
  // Awin and Rakuten Advertising for policy violations, and is still in court.
  // Rakuten's own model is the answer, and the one adopted here: the shopper
  // presses a button that says what it does, so the commission is consented to
  // rather than swapped in behind them. Product decision, 2026-09-07.
  function renderNoDeal(onSupport, onDismiss, smallDeal = null) {
    const message = !smallDeal
      ? "No discounts available, unfortunately."
      : smallDeal.priced && smallDeal.saving != null
        ? `Only ₹${rupees(smallDeal.saving)} off here — not worth the extra steps.`
        // No readable total, so no honest rupee figure — the rate is all we
        // know, and it's the rate on the voucher, not on this order.
        : `Only ${smallDeal.pct}% off here — not worth the extra steps.`;
    const root = card(`
      <div class="dealo-message">${esc(message)}</div>
      <button class="dealo-button dealo-ring dealo-withicon" id="dealo-support">
        ${svg("heart", 16, "currentColor", 1.9)} Shop with Dealo's link
      </button>
      <div class="dealo-support-note">Pays Dealo a commission from the shop. Your price is the same.</div>
      <button class="dealo-link dealo-centered" id="dealo-okay">No thanks</button>
    `);
    root.querySelector("#dealo-support").addEventListener("click", () => {
      onSupport();
      close();
    });
    root.querySelector("#dealo-okay").addEventListener("click", () => {
      onDismiss();
      close();
    });
  }

  // --- The guided journey ---------------------------------------------------
  // Everything below reads the saved trip, so Dealo can pick up the thread on
  // a completely different website from where it started.

  // Step 2 of the journey: they've landed on the voucher partner's site.
  //
  // Rebuilt 2026-09-07. This screen used to be captioned "VOUCHER 1 OF 8" and
  // showed one amount at a time, because a plan could once mean several
  // separate purchases. It cannot any more — every plan Dealo recommends is
  // buyable in one checkout — so the sequence was describing a journey the
  // product no longer takes, and a shopper's verdict on it was "what is
  // happening here looks so confusing, forget the user".
  //
  // It now shows the whole basket at once: what to add, what it costs, what
  // it is worth, and how to pay. Collecting the codes afterwards is a
  // different job and has its own screen — six vouchers is one purchase but
  // six codes, and one screen cannot honestly be both.
  function renderVoucherSiteStep(trip, { want } = {}, { onHaveCode, onAbandon, onShowMe }) {
    const d = trip.deal;
    const where = sourceName(d.voucherSource);

    // The basket, as tiles that mirror the buttons they are about to press.
    // Recognition instead of arithmetic — as a sentence this was invisible.
    const chips = (d.denominationBreakdown || []).length
      ? `<div class="dealo-chips">${d.denominationBreakdown
          .map((b) => `<span class="dealo-chip">${b.count > 1 ? `<span class="dealo-mult">${b.count}×</span>` : ""}₹${rupees(b.denom)}</span>`)
          .join("")}</div>`
      : (want ? `<div class="dealo-chips"><span class="dealo-chip">₹${rupees(want)}</span></div>` : "");

    // The three numbers that matter, in the order a person asks for them:
    // what do I pay, what do I get, what do I save.
    const priced = d.priced && d.effectivePrice != null;
    const figure = priced ? `₹${rupees(d.effectivePrice)}` : (want ? `₹${rupees(want)}` : esc(trip.store.brandName));
    const caption = priced
      ? `for ₹${rupees(d.voucherAmount)} of ${esc(trip.store.brandName)} credit${d.saving != null ? ` · saves ₹${rupees(d.saving)}` : ""}`
      : `of ${esc(trip.store.brandName)} credit`;

    // The rate promised back at the store is the UPI rate. A tick against a
    // crossed-out number rather than two sentences — it is a comparison, and
    // a comparison is a picture.
    const payRows = (d.cardPct != null && d.pct - d.cardPct >= 0.5)
      ? `<div class="dealo-pay">
           <div class="dealo-pay-row dealo-good">${svg("check", 17, "#4A9B8E", 2.4)} Pay by UPI <span class="dealo-pct">${esc(d.pct)}%</span></div>
           <div class="dealo-pay-row dealo-bad">${svg("cross", 17, "currentColor", 2.2)} By card <span class="dealo-pct">${esc(d.cardPct)}%</span></div>
         </div>`
      : `<div class="dealo-pay">
           <div class="dealo-pay-row dealo-good">${svg("check", 17, "#4A9B8E", 2.4)} Pay by UPI <span class="dealo-pct">${esc(d.pct)}%</span></div>
         </div>`;

    const root = card(`
      <div class="dealo-eyebrow">Add to your ${esc(where)} basket</div>
      ${chips}
      <div class="dealo-figure dealo-figure-tight">${figure}</div>
      <div class="dealo-caption">${caption}</div>
      ${payRows}
      <button class="dealo-button dealo-ring dealo-withicon" id="dealo-show-me">
        ${svg("target", 17, "currentColor", 2)} Show me how
      </button>
      <button class="dealo-button dealo-secondary dealo-withicon" id="dealo-have-code">
        ${svg("check", 16, "currentColor", 2.2)} I've bought them
      </button>
      <button class="dealo-link dealo-centered" id="dealo-abandon">Not doing this now</button>
    `, 1);

    root.querySelector("#dealo-show-me").addEventListener("click", () => onShowMe());
    root.querySelector("#dealo-have-code").addEventListener("click", () => onHaveCode());
    root.querySelector("#dealo-abandon").addEventListener("click", () => { onAbandon(); close(); });
  }

  // Collecting the codes. A separate job from buying them, and shaped like
  // one: six vouchers arrive as six codes, one at a time, out of an email.
  //
  // The progress is shown because it is the answer to the question a shopper
  // actually has here — how much of this is left. Reported 2026-09-07: asked
  // for eight codes, allowed to enter one, and told nothing about either.
  function renderCodeEntry(trip, { index = 0, total = 1 } = {}, { onSave }) {
    const multi = total > 1;
    const isLast = index >= total - 1;
    const remaining = Math.max(0, total - index - 1);
    // Filled by codes already saved, not by the one being typed — the bar
    // must never claim progress the shopper has not made.
    const pctDone = multi ? Math.round((index / total) * 100) : 0;

    const progress = multi
      ? `<div class="dealo-eyebrow">Code ${index + 1} of ${total}</div>
         <div class="dealo-bar"><i style="width:${pctDone}%"></i></div>`
      : `<div class="dealo-eyebrow">Step 2 of 3</div>`;

    const root = card(`
      ${progress}
      <div class="dealo-message">Paste your voucher code</div>
      <input class="dealo-input" id="dealo-code" type="text" placeholder="Voucher code" autocomplete="off">
      <input class="dealo-input" id="dealo-pin" type="text" placeholder="PIN (if there is one)" autocomplete="off">
      <button class="dealo-button" id="dealo-save-code">${isLast ? `Save &amp; go back to ${esc(trip.store.brandName)}` : "Save, next code"}</button>
      ${remaining ? `<div class="dealo-remaining">${remaining} more after this</div>` : ""}
      <div class="dealo-private">
        ${svg("lock", 14, "#4A9B8E", 1.9)}
        <span>Stays on your device</span>
      </div>
    `, 2);
    const codeEl = root.querySelector("#dealo-code");
    codeEl.focus();
    const save = () => {
      const code = codeEl.value.trim();
      if (!code) { codeEl.focus(); return; }
      onSave(code, root.querySelector("#dealo-pin").value.trim());
    };
    root.querySelector("#dealo-save-code").addEventListener("click", save);
    // Six codes is six round trips to the keyboard; Enter saves, so the
    // shopper never has to reach for the mouse between them.
    root.querySelectorAll(".dealo-input").forEach((el) =>
      el.addEventListener("keydown", (e) => { if (e.key === "Enter") save(); }));
  }

  // Draws a highlight ring and a pointing label around a real element on the
  // store's own page — "the gift card box is HERE". Purely visual: Dealo
  // points, the shopper types. Nothing is filled in for them.
  function pointAt(el, label, { persist = false } = {}) {
    document.getElementById("dealo-pointer")?.remove();
    el.scrollIntoView({ behavior: "smooth", block: "center" });

    const wrap = document.createElement("div");
    wrap.id = "dealo-pointer";
    wrap.innerHTML = `<div class="dealo-ring-box"></div><div class="dealo-ring-label">${esc(label)}</div>`;
    document.documentElement.appendChild(wrap);

    const place = () => {
      const r = el.getBoundingClientRect();
      const box = wrap.querySelector(".dealo-ring-box");
      const tag = wrap.querySelector(".dealo-ring-label");
      box.style.cssText += `top:${r.top - 6}px;left:${r.left - 6}px;width:${r.width + 12}px;height:${r.height + 12}px;`;
      // Sit the label above the box, unless that would go off the top.
      const above = r.top > 54;
      tag.style.cssText += `top:${above ? r.top - 42 : r.bottom + 12}px;left:${Math.max(8, r.left - 6)}px;`;
      tag.classList.toggle("dealo-ring-label-below", !above);
    };
    place();

    const onMove = () => place();
    window.addEventListener("scroll", onMove, true);
    window.addEventListener("resize", onMove);
    const cleanup = () => {
      wrap.remove();
      window.removeEventListener("scroll", onMove, true);
      window.removeEventListener("resize", onMove);
    };
    // A guided step stays put until the shopper does it; a one-off hint fades.
    if (!persist) setTimeout(cleanup, 9000);
    return cleanup;
  }

  // Walks the shopper through a short sequence on someone else's page, one
  // highlighted control at a time — "tap this amount", then "choose UPI".
  // Advances when they actually click the thing, so it follows them rather
  // than racing ahead. Dealo never clicks anything itself.
  // A step may be a plain {el, label}, or a FUNCTION returning one. Prefer the
  // function: it is looked up at the moment the shopper reaches that step,
  // not when the sequence starts.
  //
  // That matters on the voucher sites, which redraw as you use them. Tapping
  // an amount on Maximize re-renders the price options underneath — so a step
  // that grabbed the "instant discount" box up front would, by the time the
  // shopper got there, be holding an element the page had already thrown
  // away, and the pointer would simply never appear. Resolving late is the
  // difference between the guidance working and silently doing nothing.
  //
  // Returns false when nothing could be found to point at, so the caller can
  // fall back to written instructions instead of a sequence that shows
  // nothing.
  function guide(steps) {
    const resolve = (s) => (typeof s === "function" ? s() : s);
    // Counted up front so the shopper sees a stable "2 of 3" rather than a
    // total that shrinks under them. Re-resolved at show time regardless.
    let total = steps.reduce((n, s) => n + (resolve(s) ? 1 : 0), 0);
    if (!total) return false;

    let i = 0;
    let shown = 0;
    let clearPointer = null;

    const show = () => {
      clearPointer?.();
      if (i >= steps.length) return;
      const step = resolve(steps[i]);
      // Not there any more, or no longer needed — the shopper may have already
      // done this one themselves.
      if (!step || !step.el || !step.el.isConnected) {
        i += 1;
        total = Math.max(total - 1, shown);
        return show();
      }
      shown += 1;
      clearPointer = pointAt(step.el, `${shown}/${total} · ${step.label}`, { persist: true });
      const onDone = () => {
        step.el.removeEventListener("click", onDone, true);
        i += 1;
        // Let the page react to their click before pointing at the next thing.
        setTimeout(show, 500);
      };
      step.el.addEventListener("click", onDone, true);
    };

    show();
    return true;
  }

  // When the gift-card box can't be found on this particular page, say so and
  // open the written steps, instead of pointing at something and being wrong.
  function showWhereFallback() {
    const root = document.getElementById("dealo-popup-root");
    const btn = root?.querySelector("#dealo-where");
    if (btn) {
      btn.textContent = "Couldn't find it on this page";
      btn.disabled = true;
    }
    const toggle = root?.querySelector(".dealo-explain-toggle");
    const panel = root?.querySelector(".dealo-explain");
    if (toggle && panel && panel.hidden) toggle.click();
  }

  function guideUnavailable() {
    const btn = document.getElementById("dealo-popup-root")?.querySelector("#dealo-show-me");
    if (btn) {
      btn.textContent = "Can't find the buttons here";
      btn.disabled = true;
    }
  }

  // Step 3 done: the moment the shopper actually feels the win.
  function renderTripComplete(trip) {
    const { big, caption } = headlineFigure(trip.deal);
    card(`
      <div class="dealo-done-mark">${svg("check", 26, "#4A9B8E", 2.4)}</div>
      <div class="dealo-figure dealo-figure-tight">${big}</div>
      <div class="dealo-caption">${caption} at ${esc(trip.store.brandName)}</div>
    `);
    setTimeout(close, 6000);
  }

  return {
    renderVoucherFound, renderNoDeal, close, copyText, pointAt, guide, showWhereFallback, guideUnavailable,
    renderVoucherSiteStep, renderCodeEntry, renderBackAtStore, renderPlaceOrder, renderTripComplete,
  };
})();
