// Background service worker.
//
// Owns every call to the Dealo backend. Content scripts deliberately don't
// fetch directly: a request made from inside the store's own page is subject
// to that page's network restrictions, and big storefronts (Flipkart in
// particular) block outbound requests from their pages. A request made here
// belongs to the extension, so the page can't interfere with it — this is
// also Chrome's own recommended pattern for MV3 cross-origin requests.
//
// Also owns the toolbar badge: a small green dot on the Dealo icon whenever
// the current tab has a deal, so a missed or closed popup isn't the only
// signal the shopper ever gets.
importScripts("config.js");

const BADGE_DOT = "●";
// Terracotta — the brand kit's own "labels, tags, CTA" colour.
const BADGE_COLOR = "#C2712F";

// The live backend, unless a developer has pointed this copy at a local one.
// Read per call rather than cached in a variable: a service worker is torn
// down after ~30s idle, so anything cached here is gone by the next lookup
// anyway, and reading storage is cheap.
async function apiBase() {
  const cfg = self.__dealoConfig;
  const stored = await chrome.storage.local.get(cfg.API_BASE_OVERRIDE_KEY);
  return stored[cfg.API_BASE_OVERRIDE_KEY] || cfg.API_BASE;
}

async function fetchVoucherCheck(domain, price) {
  const base = await apiBase();
  const params = new URLSearchParams({ domain });
  if (price != null) params.set("price", String(price));
  const res = await fetch(`${base}/voucher-check?${params.toString()}`);
  if (!res.ok) throw new Error(`voucher-check failed: ${res.status}`);
  return res.json();
}

// One silent retry — a single network blip shouldn't mean the shopper never
// sees a deal that exists.
async function voucherCheckWithRetry(domain, price) {
  try {
    return await fetchVoucherCheck(domain, price);
  } catch (e) {
    return fetchVoucherCheck(domain, price);
  }
}

// The tab can be gone by the time an answer comes back — the shopper closed
// it, or navigated on. That's normal, not an error worth surfacing, but left
// unhandled it throws "No tab with id" into the extension's error list.
function setBadge(tabId, on) {
  if (tabId == null) return;
  Promise.all([
    chrome.action.setBadgeBackgroundColor({ tabId, color: BADGE_COLOR }),
    chrome.action.setBadgeText({ tabId, text: on ? BADGE_DOT : "" }),
  ]).catch(() => {});
}

// --- The trip -------------------------------------------------------------
//
// Dealo's journey crosses two different websites and several page loads: the
// store's checkout, the voucher partner's site, then back to the store. Each
// popup on its own is a goldfish — it wakes up, reads one page, speaks, and
// forgets. The trip is the single note that carries the shopper's intent
// across all of it: "part-way through saving ₹240 on Nykaa, needs to buy
// ₹4,000 of credit, no code yet."
//
// Kept in chrome.storage.local so it survives closing the browser (a voucher
// code can arrive by email minutes later). One trip at a time — a person is
// checking out of one shop; starting a new one replaces the old.
const TRIP_KEY = "dealo_trip";
// A trip outranks everything — it stops Dealo checking the cart at all, because
// finishing a purchase matters more than starting another. That makes a stale
// one actively harmful: it takes over the shop for as long as it lives.
//
// A week was chosen so a code arriving by email overnight still finds its trip.
// But a shopper who abandons one mid-way gets a shop that will not check their
// cart for seven days, and has no idea why. Seen on 2026-09-09, when a trip
// left over from Sunday's testing greeted the product owner with a three-day-old
// voucher code the moment they opened Frido.
//
// Two days covers every real overnight-code case and bounds the damage of an
// abandoned one. "Start over" on the panel ends a trip immediately, which is
// the real fix; this is the backstop for someone who never sees that button.
const TRIP_TTL_MS = 2 * 24 * 60 * 60 * 1000;

async function tripGet() {
  const stored = await chrome.storage.local.get(TRIP_KEY);
  const trip = stored[TRIP_KEY];
  if (!trip) return null;
  if (Date.now() - trip.startedAt > TRIP_TTL_MS) {
    await chrome.storage.local.remove(TRIP_KEY);
    return null;
  }
  return trip;
}

async function tripStart({ domain, returnUrl, cartTotal, deal }) {
  const trip = {
    startedAt: Date.now(),
    status: "buying_voucher", // -> "has_code" -> cleared when done
    store: { domain, returnUrl, cartTotal: cartTotal ?? null, brandName: deal.brand_name },
    deal: {
      pct: deal.pct,
      saving: deal.saving,
      effectivePrice: deal.effective_price,
      voucherUrl: deal.voucher_url,
      voucherSource: deal.voucher_source,
      voucherAmount: deal.voucher_amount,
      purchaseBreakdown: deal.purchase_breakdown,
      denominationBreakdown: deal.denomination_breakdown,
      txnsNeeded: deal.txns_needed,
      remainder: deal.remainder,
      cartTotal: deal.cart_total,
      cardPct: deal.card_pct,
      howToRedeemShort: deal.how_to_redeem_short,
      howToRedeemSteps: deal.how_to_redeem_steps,
      restrictions: deal.restrictions,
      priced: deal.priced,
    },
    codes: [], // one {code, pin} per voucher purchased — stays on this machine only, never sent anywhere
  };
  await chrome.storage.local.set({ [TRIP_KEY]: trip });
  return trip;
}

async function tripUpdate(patch) {
  const trip = await tripGet();
  if (!trip) return null;
  const next = { ...trip, ...patch };
  await chrome.storage.local.set({ [TRIP_KEY]: next });
  return next;
}

// How many voucher CODES this deal ends with — which is not the same number as
// how many checkouts it takes, and conflating the two lost people's codes.
//
// Six ₹5,000 vouchers bought from Gyftr is ONE checkout (Gyftr lets several
// into one basket) but SIX codes, one printed per voucher. The code-collecting
// loop used to stop at `txnsNeeded`, so after the first code it declared the
// shopper finished and sent them back to the store holding ₹5,000 of the
// ₹30,000 they had just paid for. Reported from live use 2026-09-07: "it asked
// me to buy 8 vouchers and then would not let me paste the other 7."
//
// The panel was already counting vouchers rather than checkouts, which is why
// it said "VOUCHER 1 OF 8" while the state machine thought one was enough.
function vouchersNeeded(deal) {
  const breakdown = deal?.denominationBreakdown || [];
  const total = breakdown.reduce((n, b) => n + (b.count || 1), 0);
  return total || deal?.txnsNeeded || 1;
}

// Collects one code per voucher as each arrives, rather than asking for all of
// them at once before any exist. Only once every voucher has a code does the
// trip move on to "has_code" and send the shopper back to the store.
async function tripAddCode(code, pin) {
  const trip = await tripGet();
  if (!trip) return null;
  const codes = [...(trip.codes || []), { code, pin: pin || null }];
  const needed = vouchersNeeded(trip.deal);
  const next = { ...trip, codes, status: codes.length >= needed ? "has_code" : "buying_voucher" };
  await chrome.storage.local.set({ [TRIP_KEY]: next });
  return next;
}

async function tripClear() {
  await chrome.storage.local.remove(TRIP_KEY);
}

const HANDLERS = {
  voucherCheck: async (msg, tabId) => {
    const result = await voucherCheckWithRetry(msg.domain, msg.price);
    setBadge(tabId, Boolean(result.has_voucher));
    return { result };
  },
  tripStart: async (msg) => ({ trip: await tripStart(msg.trip) }),
  tripGet: async () => ({ trip: await tripGet() }),
  tripUpdate: async (msg) => ({ trip: await tripUpdate(msg.patch) }),
  tripAddCode: async (msg) => ({ trip: await tripAddCode(msg.code, msg.pin) }),
  tripClear: async () => {
    await tripClear();
    return {};
  },
};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const handler = HANDLERS[msg?.type];
  if (!handler) return false;
  handler(msg, sender.tab?.id)
    .then((payload) => sendResponse({ ok: true, ...payload }))
    .catch(() => {
      if (msg.type === "voucherCheck") setBadge(sender.tab?.id, false);
      sendResponse({ ok: false });
    });
  return true; // keep the message channel open for the async response
});

// --- Telling the page when to look again -----------------------------------
//
// A content script runs once per real page load, but storefronts swap the cart
// in without one — boAt opens /#cart, most single-page storefronts never
// reload at all. Dealo used to catch that by re-reading the address bar every
// 700ms, forever, in every open tab. That timer ran on every page on the
// internet for the whole life of the tab, to notice something the browser
// already knows the moment it happens.
//
// tabs.onUpdated fires on those in-page navigations too, so the browser can
// simply say when to look again. No timer, and nothing running on pages where
// nothing is happening.
function nudge(tabId, force) {
  return chrome.tabs.sendMessage(tabId, { type: "dealoRecheck", force: Boolean(force) });
}

// --- Where Dealo is allowed to run -----------------------------------------
//
// Dealo used to be declared in the manifest as a content script on every http
// and https page, which meant the browser loaded ~75KB of Dealo into Gmail,
// into a banking page, into every article anyone read — and only then did
// Dealo work out it wasn't a shop and go quiet. Being quiet is not the same
// as not being there.
//
// It is now injected deliberately, one page at a time, and only where there
// is a reason. Three rules, in order of authority:
//
//   1. A trip in progress outranks everything. The shopper is mid-purchase on
//      the voucher partner's site or back at the store, and those pages don't
//      reliably have a checkout-ish address — losing them there would strand
//      someone who has already paid for a voucher.
//   2. Never on the listed inbox/social/document hosts, whatever the address
//      says, and never on a voucher site outside a trip.
//   3. Otherwise, the address has to look like a checkout — the same
//      whole-word test the content script has always used, moved earlier so
//      that failing it costs nothing instead of costing an injection. The
//      page-content check (hasCommerceSignal) still runs afterwards, so a
//      page like github.com/actions/checkout gets Dealo loaded but never sees
//      a popup.
const HOST_PERMS = { origins: ["http://*/*", "https://*/*"] };

function hostOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch (e) { return null; }
}

function hostMatches(host, listed) {
  return host === listed || host.endsWith("." + listed);
}

function urlLooksLikeCheckout(url) {
  let u;
  try { u = new URL(url); } catch (e) { return false; }
  const target = (u.pathname + " " + u.search + " " + u.hash).toLowerCase();
  return self.__dealoConfig.CHECKOUT_URL_KEYWORDS.some((kw) =>
    new RegExp(`(^|[^a-z])${kw}([^a-z]|$)`).test(target)
  );
}

async function shouldRunOn(url) {
  if (!url || !/^https?:/.test(url)) return false;
  const host = hostOf(url);
  if (!host) return false;
  const cfg = self.__dealoConfig;

  // 1. Mid-trip: the two hosts this shopper is actually travelling between.
  const trip = await tripGet();
  if (trip) {
    const voucherHost = hostOf(trip.deal?.voucherUrl);
    if (voucherHost && hostMatches(host, voucherHost)) return true;
    if (trip.store?.domain && hostMatches(host, trip.store.domain)) return true;
  }

  // 2. Never here.
  if (cfg.NEVER_RUN_HOSTS.some((h) => hostMatches(host, h))) return false;
  if (cfg.VOUCHER_HOSTS.some((h) => hostMatches(host, h))) return false;

  // 3. Does the address look like somewhere money changes hands?
  return urlLooksLikeCheckout(url);
}

// Injects Dealo into one tab. Same three files, in the same order, as the
// manifest used to declare — order matters: config defines __dealoConfig,
// popup defines __dealoPopup, content uses both.
async function inject(tabId) {
  await chrome.scripting.insertCSS({ target: { tabId }, files: ["src/popup.css"] });
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["src/config.js", "src/popup.js", "src/content.js"],
  });
}

// Ask the page to look again; if nobody answers, Dealo isn't in that tab yet,
// so put it there. Injecting runs content.js, which checks on load — so there
// is deliberately no nudge after a successful injection, or the page would be
// checked twice.
// Flip to true and reload the extension to trace every decision in the service
// worker console. Off by default — this fires on every navigation.
const TRACE = true;
const trace = (...a) => { if (TRACE) console.log("[Dealo]", ...a); };

async function nudgeOrInject(tabId, url, force) {
  const granted = await chrome.permissions.contains(HOST_PERMS);
  if (!granted) { trace("no host access yet, skipping", url); return; }
  const wanted = force || (await shouldRunOn(url));
  trace(wanted ? "will run on" : "skipping", url);
  if (!wanted) return;
  try {
    await nudge(tabId, force);
    trace("already there, asked it to look again:", url);
  } catch (e) {
    trace("not there yet (" + (e && e.message) + "), injecting into", url);
    try {
      await inject(tabId);
      trace("INJECTED OK:", url);
    } catch (err) {
      // Nothing is filtered here, on purpose. An earlier version treated
      // "Cannot access contents of..." as routine noise and swallowed it —
      // and that turned out to be the one message that mattered, so an
      // extension injecting nowhere at all looked, from outside, like it was
      // working. Silence must never again be indistinguishable from success.
      console.error("[Dealo] INJECT FAILED:", url, "->", err && err.message);
    }
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // A badge belongs to the page it was set for — clear it when that tab moves on.
  if (changeInfo.status === "loading") setBadge(tabId, false);
  // changeInfo.url is set for in-page navigations as well as full loads, and
  // is visible to us once the shopper has granted host access.
  // Deliberately NOT on "loading". A fresh page load fires onUpdated with the
  // new address long before the page has drawn anything, and Dealo injected
  // that early looks at an empty document, decides it isn't a checkout, and —
  // because it only checks a given view once — never looks again. boAt was
  // the case that showed this: /cart lands on /#cart, Dealo went in too soon,
  // and the ₹350 panel only appeared if you jogged the address bar by hand.
  //
  // "complete" covers real page loads. A bare url change with no status is a
  // storefront swapping the cart in without a reload (a hash or history
  // change) — the document is already there, so that one is safe to act on.
  const settled = changeInfo.status === "complete";
  const inPageNav = Boolean(changeInfo.url) && changeInfo.status !== "loading";
  if (settled || inPageNav) {
    nudgeOrInject(tabId, changeInfo.url || tab?.url);
  }
});

// --- First run --------------------------------------------------------------
//
// Dealo asks for access on its own screen rather than through Chrome's install
// warning, so there has to be a screen.
//
// Shown on update as well as install, and this is not belt-and-braces — it is
// the only thing that saves the people who already have Dealo. Version 0.1.0
// declared host access as *required*, so Chrome granted it at install. 0.2.0
// makes it optional, and Chrome does not carry a required grant across to an
// optional one: on updating, every existing shopper silently loses access.
// Without this, Dealo would simply stop appearing for them, with no screen, no
// message and nothing to click. Caught on the first real reload, 2026-09-07.
//
// The permission check is what stops it being annoying: someone who has
// already said yes never sees this tab, on install or update.
chrome.runtime.onInstalled.addListener(async ({ reason }) => {
  if (reason !== "install" && reason !== "update") return;
  if (await chrome.permissions.contains(HOST_PERMS)) return;
  chrome.tabs.create({ url: chrome.runtime.getURL("src/welcome.html") });
});

// Clicking the toolbar icon did nothing at all — no popup is declared in the
// manifest and nothing listened for the click, so the one deliberate gesture a
// curious shopper makes was met with silence. It now re-runs the check on the
// spot, ignoring both the "already looked at this page" guard and any earlier
// dismissal: an explicit click is the shopper asking, which outranks Dealo's
// own judgement about when to keep quiet.
chrome.action.onClicked.addListener(async (tab) => {
  if (tab?.id == null) return;
  // No access yet — the click is someone looking for Dealo, so show them the
  // screen that asks for it rather than doing nothing.
  if (!(await chrome.permissions.contains(HOST_PERMS))) {
    chrome.tabs.create({ url: chrome.runtime.getURL("src/welcome.html") });
    return;
  }
  // `force` skips the shouldRunOn test as well as the dismissal guard: an
  // explicit click outranks Dealo's own judgement about where it belongs, so
  // it works even on a page the address test would have passed over.
  nudgeOrInject(tab.id, tab.url, true);
});
