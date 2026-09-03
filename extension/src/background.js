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

async function fetchVoucherCheck(domain, price) {
  const base = self.__dealoConfig.API_BASE;
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
const TRIP_TTL_MS = 7 * 24 * 60 * 60 * 1000; // abandoned trips expire after a week

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

// A deal needing several separate voucher purchases (txnsNeeded > 1 — e.g.
// three ₹2,500 buys instead of one combined checkout) collects one code per
// purchase as each arrives, rather than asking for all of them at once before
// any exist. Only once every purchase has a code does the trip move on to
// "has_code" and send the shopper back to the store.
async function tripAddCode(code, pin) {
  const trip = await tripGet();
  if (!trip) return null;
  const codes = [...(trip.codes || []), { code, pin: pin || null }];
  const txnsNeeded = trip.deal.txnsNeeded || 1;
  const next = { ...trip, codes, status: codes.length >= txnsNeeded ? "has_code" : "buying_voucher" };
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

// A badge belongs to the page it was set for — clear it when that tab moves on.
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "loading") setBadge(tabId, false);
});
