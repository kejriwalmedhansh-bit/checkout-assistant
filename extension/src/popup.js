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
  function explanationBody(deal) {
    const brand = esc(deal.brand_name);
    return deal.priced && deal.effective_price != null
      ? `A Gift Voucher is the same thing you'd buy someone as a present — our voucher partner sells them for less than they're worth. You buy ₹${rupees(deal.effective_price + deal.saving)} of ${brand} credit for ₹${rupees(deal.effective_price)}, then pay for this order with it, exactly like a gift card. Same store, same order.`
      : `A Gift Voucher is the same thing you'd buy someone as a present — our voucher partner sells ${brand} vouchers for ${esc(deal.pct)}% less than they're worth. You buy one, then pay for this order with it, exactly like a gift card. Same store, same order.`;
  }

  function wireExplainToggle(root) {
    const toggle = root.querySelector(".dealo-explain-toggle");
    const panel = root.querySelector(".dealo-explain");
    if (!toggle || !panel) return;
    // Keep the original label (icon included) rather than overwriting it with
    // hardcoded text — each screen's toggle now says something different.
    const original = toggle.innerHTML;
    toggle.addEventListener("click", () => {
      const open = !panel.hidden;
      panel.hidden = open;
      toggle.setAttribute("aria-expanded", String(!open));
      toggle.innerHTML = open ? original : "hide";
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

    const root = card(`
      <div class="dealo-figure dealo-figure-tight">${big}</div>
      <div class="dealo-caption">${caption} at ${esc(deal.brand_name)}</div>
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

  function renderNoDeal(onOkay) {
    const root = card(`
      <div class="dealo-message">No discounts available, unfortunately.</div>
      <button class="dealo-button dealo-secondary" id="dealo-okay">Okay</button>
    `);
    root.querySelector("#dealo-okay").addEventListener("click", () => {
      onOkay();
      close();
    });
  }

  // --- The guided journey ---------------------------------------------------
  // Everything below reads the saved trip, so Dealo can pick up the thread on
  // a completely different website from where it started.

  // Step 2 of the journey: they've landed on the voucher partner's site.
  // Tells them exactly what to buy, and — critically — how to pay for it.
  function renderVoucherSiteStep(trip, { onHaveCode, onAbandon, onShowMe }) {
    const d = trip.deal;
    // No amount when the cart total couldn't be read — the layout falls back
    // to naming the brand rather than rendering a sentence with a hole in it
    // ("Buy of Boat credit", seen in live testing).
    const amount = d.voucherAmount ? `₹${rupees(d.voucherAmount)}` : "";
    // The denominations become tiles that mirror the amount buttons they're
    // about to press on the voucher site — recognition instead of arithmetic.
    // As a sentence ("That's 1×₹7,500 + 1×₹1,000") it was near-invisible.
    const tiles = (d.denominationBreakdown || []).length
      ? `<div class="dealo-chips">${d.denominationBreakdown
          .map((b) => `<span class="dealo-chip">${b.count > 1 ? `<span class="dealo-mult">${b.count}×</span>` : ""}₹${rupees(b.denom)}</span>`)
          .join("")}</div>`
      : "";

    // The rate promised back at the store is the UPI rate. Shown as a tick
    // against a crossed-out number rather than two sentences — it's a
    // comparison, and a comparison is a picture.
    const payRows = (d.cardPct != null && d.pct - d.cardPct >= 0.5)
      ? `<div class="dealo-pay">
           <div class="dealo-pay-row dealo-good">${svg("check", 17, "#4A9B8E", 2.4)} UPI <span class="dealo-pct">${esc(d.pct)}%</span></div>
           <div class="dealo-pay-row dealo-bad">${svg("cross", 17, "currentColor", 2.2)} Card <span class="dealo-pct">${esc(d.cardPct)}%</span></div>
         </div>`
      : `<div class="dealo-pay">
           <div class="dealo-pay-row dealo-good">${svg("check", 17, "#4A9B8E", 2.4)} UPI <span class="dealo-pct">${esc(d.pct)}%</span></div>
         </div>`;

    const root = card(`
      <div class="dealo-figure dealo-figure-tight">${amount || esc(trip.store.brandName)}</div>
      ${amount ? `<div class="dealo-caption">of ${esc(trip.store.brandName)} credit</div>` : `<div class="dealo-caption">credit for your order</div>`}
      ${tiles}
      ${payRows}
      <button class="dealo-button dealo-ring dealo-withicon" id="dealo-show-me">
        ${svg("target", 17, "currentColor", 2)} Show me
      </button>
      <button class="dealo-button dealo-secondary dealo-withicon" id="dealo-have-code">
        ${svg("check", 16, "currentColor", 2.2)} Got the code
      </button>
      <button class="dealo-link" id="dealo-abandon">Not doing this now</button>
    `, 2);
    root.querySelector("#dealo-show-me").addEventListener("click", () => onShowMe());
    root.querySelector("#dealo-have-code").addEventListener("click", () => onHaveCode());
    root.querySelector("#dealo-abandon").addEventListener("click", () => { onAbandon(); close(); });
  }

  // Step 2b: somewhere to put the code. Stays on this machine — never sent
  // to Dealo's servers, which is both the honest promise and less to secure.
  function renderCodeEntry(trip, { onSave }) {
    const root = card(`
      <div class="dealo-step">Step 2 of 3</div>
      <div class="dealo-message">Paste your voucher code</div>
      <input class="dealo-input" id="dealo-code" type="text" placeholder="Voucher code" autocomplete="off">
      <input class="dealo-input" id="dealo-pin" type="text" placeholder="PIN (if there is one)" autocomplete="off">
      <button class="dealo-button" id="dealo-save-code">Save &amp; go back to ${esc(trip.store.brandName)}</button>
      <div class="dealo-private">
        ${svg("lock", 14, "#4A9B8E", 1.9)}
        <span>Stays on your device</span>
      </div>
    `, 2);
    const codeEl = root.querySelector("#dealo-code");
    codeEl.focus();
    root.querySelector("#dealo-save-code").addEventListener("click", () => {
      const code = codeEl.value.trim();
      if (!code) { codeEl.focus(); return; }
      onSave(code, root.querySelector("#dealo-pin").value.trim());
    });
  }

  // Step 3: they're back at the store's checkout, holding a code they now
  // have to actually use. This is where people give up without help.
  function renderBackAtStore(trip, { onDone, onShowWhere }) {
    const d = trip.deal;
    // The store's own one-liner becomes the label on the steps toggle rather
    // than a sentence sitting on the card — one tap away, not in the way.
    const how = d.howToRedeemShort || "";
    // Only claim the voucher covers the order when we actually read the order
    // total. Saying "that covers the whole order" off an unpriced trip is a
    // statement we have no basis for — caught in live testing on boAt.
    // A number, not a sentence: "₹0 left to pay" is read at a glance.
    const left = !d.priced
      ? ""
      : `<div class="dealo-left">₹${rupees(d.remainder)} <span>left to pay</span></div>`;
    // The brands write these as paragraphs — Amazon's middle step is three
    // sentences with an "Alternatively…" branch and a sign-up aside. Nobody
    // reads that mid-checkout, so each step is cut to its first instruction.
    const steps = (d.howToRedeemSteps || []).slice(0, 3)
      .map((s) => `<li>${esc(shortenStep(s))}</li>`).join("");

    // The single most useful thing buried in those paragraphs is the redeem
    // page's address. Pulled out as a button, it replaces reading entirely.
    // What THIS voucher can't be used for, straight from whoever sold it.
    // The three sellers genuinely differ — BuyHatke's AJIO card excludes H&M
    // products, which appears on no other source — so this is never borrowed
    // from another seller and never silently dropped.
    const limits = (d.restrictions || []).filter(Boolean).slice(0, 2);
    const limitBlock = limits.length
      ? `<div class="dealo-limits">${svg("info", 13, "#C2712F", 2)}
           <span>${limits.map((l) => esc(shortenStep(l))).join(" ")}</span>
         </div>`
      : "";

    const redeemUrl = firstUrlIn(d.howToRedeemSteps || []);
    const openBtn = redeemUrl
      ? `<a class="dealo-button dealo-secondary dealo-withicon" id="dealo-open-redeem"
            href="${esc(redeemUrl)}" target="_blank" rel="noopener noreferrer">
           ${svg("link", 15, "currentColor", 1.9)} ${esc(prettyHost(redeemUrl))}
         </a>`
      : "";

    // Code and PIN are two separate things typed into two separate boxes, so
    // they get two separate rows with their own Copy buttons. Showing them as
    // "code · pin" on one line read as a single value, and copying gave you
    // only half of what you needed at the second box.
    const field = (label, value, id) => `
      <div class="dealo-field">
        <div class="dealo-field-label">${esc(label)}</div>
        <div class="dealo-field-row">
          <span class="dealo-code">${esc(value)}</span>
          <button class="dealo-copy-btn" data-copy="${esc(value)}" id="${id}" aria-label="Copy ${esc(label)}" title="Copy">
            ${svg("copy", 16, "currentColor", 1.8)}
          </button>
        </div>
      </div>`;

    const root = card(`
      ${field("Code", trip.code, "dealo-copy-code")}
      ${trip.pin ? field("PIN", trip.pin, "dealo-copy-pin") : ""}
      ${left}
      ${limitBlock}
      <button class="dealo-button dealo-ring dealo-withicon" id="dealo-where">
        ${svg("target", 17, "currentColor", 2)} Show me where
      </button>
      ${openBtn}
      ${steps ? `<button class="dealo-explain-toggle dealo-centered" aria-expanded="false">${svg("info", 13, "currentColor", 2)} steps</button>
                 <div class="dealo-explain" hidden><ol class="dealo-steps">${steps}</ol></div>` : ""}
      <button class="dealo-link dealo-withicon" id="dealo-done">
        ${svg("check", 13, "#4A9B8E", 2.4)} done
      </button>
    `, 3);
    wireExplainToggle(root);
    // Confirmation is the icon turning into a tick — "Copied" no longer fits
    // an icon-sized button, and the tick reads faster anyway.
    root.querySelectorAll(".dealo-copy-btn").forEach((btn) => {
      const original = btn.innerHTML;
      btn.addEventListener("click", () => {
        copyText(btn.dataset.copy);
        btn.innerHTML = svg("check", 16, "#4A9B8E", 2.4);
        setTimeout(() => { btn.innerHTML = original; }, 1600);
      });
    });
    root.querySelector("#dealo-where").addEventListener("click", () => onShowWhere());
    root.querySelector("#dealo-done").addEventListener("click", () => { onDone(); close(); });
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
  function guide(steps) {
    let i = 0;
    let clearPointer = null;

    const show = () => {
      clearPointer?.();
      if (i >= steps.length) return;
      const step = steps[i];
      if (!step.el || !step.el.isConnected) { i += 1; return show(); }
      clearPointer = pointAt(step.el, `${i + 1}/${steps.length} · ${step.label}`, { persist: true });
      const onDone = () => {
        step.el.removeEventListener("click", onDone, true);
        i += 1;
        // Let the page react to their click before pointing at the next thing.
        setTimeout(show, 500);
      };
      step.el.addEventListener("click", onDone, true);
    };

    show();
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
    renderVoucherSiteStep, renderCodeEntry, renderBackAtStore, renderTripComplete,
  };
})();
