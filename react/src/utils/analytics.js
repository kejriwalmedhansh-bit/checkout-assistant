// The async-recorder build leaves session replay's recorder (rrweb, most of
// the SDK's weight) out of the main bundle and fetches it only once a
// consented session starts recording — every visitor used to download it on
// first paint, consent or not. The recorder is served from our own site
// (RECORDER_URL) rather than Mixpanel's CDN, which doesn't host the hashed
// file this build asks for. The glob makes an SDK upgrade pick up the new
// hash by itself instead of silently pointing at a file that no longer exists.
import mixpanel from 'mixpanel-browser/dist/mixpanel-with-async-recorder.cjs.js';

import { API_BASE_URL, MIXPANEL_TOKEN } from '@/config';
import { clearAnalyticsStorage, isGranted, onConsentChange } from '@/utils/consent';

const RECORDER_URL = Object.values(
  import.meta.glob('/node_modules/mixpanel-browser/dist/async-modules/mixpanel-recorder-*.min.js', {
    query: '?url',
    import: 'default',
    eager: true,
  }),
)[0];

const USER_ID_KEY = 'dealo_user_id';
const INTERNAL_TESTER_KEY = 'dealo_internal_tester';
const FIRST_TOUCH_KEY = 'dealo_first_touch';
const ATTRIBUTION_PARAMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'gclid', 'fbclid'];

/**
 * Elements whose text is the visitor's own words rather than ours: the search
 * box, and the two places the query is echoed back on screen. Session replay
 * blanks these out.
 *
 * Masking inputs alone would not have worked. The query is typed into an
 * input, but the very next screen prints it as an <h1> — plain page text, not
 * an input — so "hide what they typed" has to name that heading too, or the
 * recording simply shows the search a screen later in 24-point type.
 *
 * Marked with an attribute rather than by tag or position: a selector tied to
 * markup silently stops matching the first time someone restyles a page, and
 * nothing about the replay would look wrong when it did.
 */
export const PRIVATE_TEXT_ATTR = 'data-dealo-private';
const PRIVATE_TEXT_SELECTOR = `[${PRIVATE_TEXT_ATTR}]`;

/** Fallback id holder for browsers where localStorage throws (Safari private mode). */
let memoryUserId = null;

/** True when the id was read back from storage rather than minted this visit. */
let isReturningVisitor = false;

/** Mixpanel is only initialised once, and only after consent. */
let started = false;

function newId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  // Older Safari/WebView: good enough for an anonymous analytics handle.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * A stable, anonymous per-browser id, minted on first visit and reused after
 * that. Not tied to a person — it's a handle for stitching one visitor's events
 * together across sessions, and it resets if they clear site data.
 *
 * Only ever called once consent has been given: it writes to storage, and a
 * visitor who said no gets nothing written.
 */
function getUserId() {
  if (memoryUserId) return memoryUserId;
  try {
    let id = window.localStorage.getItem(USER_ID_KEY);
    if (id) {
      isReturningVisitor = true;
    } else {
      id = newId();
      window.localStorage.setItem(USER_ID_KEY, id);
    }
    memoryUserId = id;
  } catch {
    memoryUserId = newId();
  }
  return memoryUserId;
}

/**
 * True once this browser has ever loaded the site with ?internal=1 — the
 * one-time link the team uses to mark their own devices. Set once, then
 * remembered forever on that browser, so every later visit (even through
 * the normal link) keeps tagging events as internal, not real traffic.
 */
function getIsInternalTester() {
  try {
    if (new URLSearchParams(window.location.search).get('internal') === '1') {
      window.localStorage.setItem(INTERNAL_TESTER_KEY, '1');
    }
    return window.localStorage.getItem(INTERNAL_TESTER_KEY) === '1';
  } catch {
    return false;
  }
}

const APP_VERSION = import.meta.env.VITE_APP_VERSION || 'dev';

function environment() {
  return window.location.hostname === 'getdealo.in' ? 'production' : 'development';
}

/**
 * Visitors who haven't agreed to be recorded are still counted — every event,
 * but stripped to facts about the page and the deal, never about the person.
 *
 * What makes this lawful without consent is what is NOT done: nothing is
 * written to or read from the browser (no cookie, no localStorage id), no IP
 * address is kept (ip=0, so no location either), no session replay, and
 * nothing that could point back at a person is carried (see the allow-list
 * below). Two visits by the same person look like two strangers, which is
 * the point. Sent by fetch rather than through the SDK, because the SDK would
 * write its own identifier into storage on the way past.
 *
 * Owner's decision, 3 Nov 2026: track the most that is allowed without
 * consent, so the 85% who never answer the banner still show where people
 * stop, which shops they looked at and which link brought them.
 */

/**
 * A random id that lives only in this page's memory: it ties one visit's
 * steps together (search -> deal -> buy) so funnels work for anonymous
 * visitors, and it is gone the moment the tab closes. Never stored, so it
 * cannot recognise anyone on a later visit. For anonymous visitors, "unique
 * users" in Mixpanel therefore means visits.
 */
const VISIT_ID = `visit:${newId()}`;

/**
 * Event properties a visitor who hasn't agreed may carry. Everything here is
 * about the page, the search or the deal — words searched, shop, price,
 * saving, voucher rate, which button, which step, where the visit came from.
 * Left off on purpose: anything stored on the device (is_returning_visitor),
 * ad click ids that identify one click (gclid, fbclid, ad_click_id), free
 * text people type (note), and anything from the buy flow's login (name,
 * phone, code, PIN — which no event carries anyway).
 */
const ANONYMOUS_SAFE_PROPS = new Set([
  // where the visit came from
  'landing_page', 'referrer_domain', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
  'entry', 'ad_source_type', 'ad_source_id', 'ad_source_url', 'ad_headline',
  // pages and steps
  'path', 'step', 'step_index', 'view', 'trigger', 'placement', 'source', 'rank', 'reason', 'closed_by',
  // searches
  'query', 'mode', 'input_type', 'result_count', 'group', 'corrected_query', 'title', 'product_title', 'choice',
  // deals and prices
  'merchant', 'brand', 'shops', 'cheapest', 'spread', 'has_voucher', 'voucher_platform', 'voucher_aggregator',
  'listed_price', 'original_price', 'final_price', 'final_cost', 'discount', 'saving', 'saving_amount', 'saving_pct',
  'alternatives_count', 'pct', 'slug', 'available', 'src',
  // vouchers Dealo sells itself
  'seller', 'amount', 'discount_pct', 'best_pct', 'in_store', 'cant_count',
  // bank cards (which banks, not which card)
  'cards', 'prime', 'bank',
]);

/**
 * The three facts about the device kept without consent: phone or desktop,
 * the operating system family and the browser family. Coarse on purpose
 * (no versions, no model), so millions of people share each value.
 */
function deviceClass() {
  try {
    return window.matchMedia('(max-width: 768px)').matches ? 'phone' : 'desktop';
  } catch {
    return 'unknown';
  }
}

function osFamily() {
  const ua = navigator.userAgent || '';
  if (/iPhone|iPad|iPod/i.test(ua)) return 'iOS';
  if (/Android/i.test(ua)) return 'Android';
  if (/Windows/i.test(ua)) return 'Windows';
  if (/Mac OS X/i.test(ua)) return 'macOS';
  if (/CrOS/i.test(ua)) return 'ChromeOS';
  if (/Linux/i.test(ua)) return 'Linux';
  return 'other';
}

function browserFamily() {
  const ua = navigator.userAgent || '';
  if (/Edg\//i.test(ua)) return 'Edge';
  if (/SamsungBrowser/i.test(ua)) return 'Samsung Internet';
  if (/OPR\//i.test(ua)) return 'Opera';
  if (/Firefox\//i.test(ua)) return 'Firefox';
  if (/Chrome\//i.test(ua) && !/Chromium/i.test(ua)) return 'Chrome';
  if (/Safari\//i.test(ua)) return 'Safari';
  return 'other';
}

/**
 * A pasted link keeps only its shop and page (amzn.in/d/0ab6OVDJ): the part
 * after "?" is where share and ad links put tracking codes, which can point
 * back at a person.
 */
function withoutLinkTracking(text) {
  return String(text).replace(/https?:\/\/[^\s]+/g, (link) => {
    try {
      const url = new URL(link);
      return `${url.hostname}${url.pathname}`;
    } catch {
      return link.split(/[?#]/)[0];
    }
  });
}

function anonymousProps(props) {
  const kept = {};
  for (const [key, value] of Object.entries(props || {})) {
    if (ANONYMOUS_SAFE_PROPS.has(key) && value !== undefined && value !== null) kept[key] = value;
  }
  if (kept.query) kept.query = withoutLinkTracking(kept.query);
  return kept;
}

function countStage(event, props = {}) {
  const payload = [{
    event,
    properties: {
      ...anonymousProps(props),
      token: MIXPANEL_TOKEN,
      distinct_id: VISIT_ID,
      time: Math.floor(Date.now() / 1000),
      consent: 'not_granted',
      device: deviceClass(),
      os: osFamily(),
      browser: browserFamily(),
      surface: 'web',
      app_version: APP_VERSION,
      environment: environment(),
    },
  }];
  // Form-encoded `data=`, which is the shape Mixpanel's own SDK posts in.
  // A JSON body needs a CORS preflight, and the endpoint answered those with
  // 503 from the browser (verified: identical payloads are accepted over curl,
  // so it's the cross-origin JSON POST it objects to, not the content). A
  // form-encoded body is a "simple request" — no preflight, no rejection.
  const body = new URLSearchParams({ data: JSON.stringify(payload), ip: '0' });
  try {
    // keepalive so a stage fired as the page unloads still leaves.
    fetch('https://api-eu.mixpanel.com/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch {
    // Analytics must never break the page.
  }
}



function prefixed(obj, prefix) {
  return Object.fromEntries(Object.entries(obj).map(([k, v]) => [`${prefix}${k}`, v]));
}

/** Where this visit came from: campaign tags, referring site, landing page. */
function currentTouch() {
  const params = new URLSearchParams(window.location.search);
  const touch = { landing_page: window.location.pathname };
  for (const key of ATTRIBUTION_PARAMS) {
    const value = params.get(key);
    if (value) touch[key] = value;
  }
  try {
    const ref = document.referrer ? new URL(document.referrer).hostname : '';
    touch.referrer_domain = ref && ref !== window.location.hostname ? ref : 'direct';
  } catch {
    touch.referrer_domain = 'direct';
  }
  return touch;
}

/** The very first visit's source, kept forever on this browser. */
function getFirstTouch() {
  try {
    const saved = window.localStorage.getItem(FIRST_TOUCH_KEY);
    if (saved) return JSON.parse(saved);
    const touch = { ...currentTouch(), seen_at: new Date().toISOString() };
    window.localStorage.setItem(FIRST_TOUCH_KEY, JSON.stringify(touch));
    return touch;
  } catch {
    return { ...currentTouch(), seen_at: new Date().toISOString() };
  }
}

/**
 * This visitor's id, or null when they haven't agreed to be recorded — links
 * then carry no id and their clicks are counted anonymously.
 */
export function getDealoId() {
  return isGranted() ? getUserId() : null;
}

/**
 * Query string every outbound link carries to the backend's /go and /out
 * redirects, which log the click and stamp the id onto affiliate links.
 */
export function linkParams(ctx) {
  const params = new URLSearchParams({ surface: 'web', ctx });
  const id = getDealoId();
  if (id) params.set('did', id);
  return params.toString();
}

/** A shop link through /go: logged, commission-wrapped, id-stamped. */
export function shopLink(link, ctx) {
  if (!link) return '#';
  return `${API_BASE_URL}/go?url=${encodeURIComponent(link)}&${linkParams(ctx)}`;
}

/** A voucher-partner or card-application link through /out: logged only. */
export function outboundLink(link, kind, ctx) {
  if (!link) return undefined;
  return `${API_BASE_URL}/out?url=${encodeURIComponent(link)}&kind=${kind}&${linkParams(ctx)}`;
}

let lastViewedPath = null;

/** One Page Viewed per route change. */
export function trackPageView(pathname) {
  if (pathname === lastViewedPath) return;
  lastViewedPath = pathname;
  track('Page Viewed', { path: pathname });
}

function startMixpanel() {
  if (started) return;
  started = true;

  mixpanel.init(MIXPANEL_TOKEN, {
    track_pageview: false,
    persistence: 'localStorage',

    // This Mixpanel project uses EU data residency. Without this, the SDK's
    // default host (api-js.mixpanel.com) silently drops every event for an
    // EU-residency token instead of rejecting it — it still returns a
    // deceptive-looking success response, so nothing about it looks broken
    // except that events never actually show up in the dashboard.
    api_host: 'https://api-eu.mixpanel.com',

    // Session replay: record every session. Dealo's traffic is low enough that
    // sampling would just mean missing the one session that went wrong.
    record_sessions_percent: 100,
    recorder_src: RECORDER_URL,

    // What the replay is allowed to see. Most of the screen stays readable —
    // a replay of grey boxes tells us nothing — but the visitor's own words
    // are blanked: every input, plus the elements marked with
    // PRIVATE_TEXT_ATTR, which are the places their query is printed back.
    //
    // We lose nothing by this. The query already arrives as a property on
    // 'Searched', 'Selected Product' and 'Viewed Deal'; the replay was never
    // where we read it from.
    record_mask_all_inputs: true,
    record_mask_all_text: false,
    record_mask_text_selector: PRIVATE_TEXT_SELECTOR,

    // The SDK blocks img/video/audio by default. Dealo's UI is product cards, so
    // blocking images leaves replays as unreadable grey boxes. Audio/video stay
    // blocked — the app has neither.
    record_block_selector: 'video, audio',
  });

  const userId = getUserId();

  // Our own id is this browser's $device_id — not a $user_id. Mixpanel's
  // Simplified ID Merge only joins a device to a person, never two people
  // together, so an anonymous visitor has to stay a device for the WhatsApp
  // hand-off (the bot sends this id alongside the phone's $user_id) and a
  // later affiliate purchase (stamped with this id by /go) to land on the
  // same person. Set straight into the SDK's persistence because it has no
  // option to supply the device id itself.
  if (mixpanel.get_property('$device_id') !== userId || mixpanel.get_property('$user_id')) {
    mixpanel.unregister('$user_id');
    mixpanel.register({ distinct_id: `$device:${userId}`, $device_id: userId });
  }

  const firstTouch = getFirstTouch();
  mixpanel.register_once(prefixed(firstTouch, 'first_'));

  mixpanel.register({
    surface: 'web',
    app_version: APP_VERSION,
    // Also carried as a plain event property: it keeps the id queryable in
    // Mixpanel even if distinct_id is later remapped (e.g. to a WhatsApp
    // identity), and it survives a move off Mixpanel entirely.
    dealo_user_id: userId,
    // Marks every event as real traffic vs. our own testing (anything not on
    // the live domain — localhost, preview builds, etc.), so dashboards can
    // filter to "production" and never need to guess which visits were us.
    environment: environment(),
    // Marks the team's own devices even when testing on the real live site
    // (see getIsInternalTester above) — the environment flag alone can't catch
    // that, since it looks identical to a real visitor there.
    is_internal_tester: getIsInternalTester(),
    // So a consented session is distinguishable from the anonymous counters.
    consent: 'granted',
  });

  mixpanel.track('Session Started', { is_returning_visitor: isReturningVisitor, ...currentTouch() });
  mixpanel.track('Dashboard Opened', { is_returning_visitor: isReturningVisitor });
}

function stopMixpanel() {
  if (!started) return;
  try {
    mixpanel.stop_session_recording();
    mixpanel.opt_out_tracking({ clear_persistence: true, delete_user: true });
  } catch {
    // Best effort — the important half is that nothing more is sent below.
  }
  started = false;
  memoryUserId = null;
  clearAnalyticsStorage();
}

/**
 * Called once at startup, and again whenever the answer changes.
 *
 * Nothing happens on a page load without consent — no init, no recording, no
 * identifier — so the first arrival of a visitor who never answers leaves
 * nothing behind but the stage counts, which aren't tied to them.
 */
export function syncAnalyticsToConsent() {
  if (isGranted()) startMixpanel();
  else stopMixpanel();
}

onConsentChange(syncAnalyticsToConsent);
syncAnalyticsToConsent();

// The one event that would otherwise be missed: a visitor who lands and leaves
// without agreeing still counts as an arrival. Fired at module scope rather
// than in a component so StrictMode's double-mount can't double-count it.
if (!isGranted()) {
  countStage('Session Started', currentTouch());
  countStage('Dashboard Opened');
}

/**
 * The properties every event about a voucher Dealo sells itself carries
 * (the offer from GET /hubble/offer or the brand from /hubble/brand), so one
 * funnel can be built from "offer shown" to "voucher ready": who sold it,
 * which shop, Dealo's rate, the public best rate it was compared with, the
 * voucher value, where on the page, and which link brought the shopper.
 * placement: 'journey' (cart result) | 'shop_card' (shop-name search or a
 * buy link). src: the buy link's src (wa | ext | chat | link), else null.
 */
export function soldEventProps(offer, { merchant, placement, bestPct, amount, src } = {}) {
  return {
    seller: 'hubble',
    merchant: merchant ?? offer?.brand_name ?? null,
    brand: offer?.brand_name ?? null,
    amount: amount ?? offer?.voucher_total ?? null,
    discount_pct: offer?.discount_pct ?? null,
    best_pct: bestPct ?? null,
    placement: placement ?? null,
    src: src ?? null,
    in_store: Boolean(offer?.in_store),
  };
}

/** Fire-and-forget event tracking. */
export function track(event, props = {}) {
  if (isGranted()) mixpanel.track(event, props);
  else countStage(event, props);
}

// Shop and partner links are built at render time, which can be before the
// visitor answers the consent banner. Re-stamping the id at the moment of the
// click (capture phase, before the browser follows the link) keeps the id on
// the link in step with their answer.
if (typeof document !== 'undefined') {
  document.addEventListener(
    'click',
    (e) => {
      const a = e.target.closest?.(`a[href^="${API_BASE_URL}/go?"], a[href^="${API_BASE_URL}/out?"]`);
      if (!a) return;
      try {
        const url = new URL(a.href);
        const id = getDealoId();
        if (id) url.searchParams.set('did', id);
        else url.searchParams.delete('did');
        a.href = url.toString();
      } catch {
        // Leave the link as rendered.
      }
    },
    true,
  );
}

/**
 * Persists properties (campaign UTM tags, for now) as Mixpanel super
 * properties for the rest of this browser session, so every later funnel
 * event — 'Searched', 'Selected Product', 'Viewed Deal', 'Clicked Buy Link' —
 * carries them too, not just the landing event that read them off the URL.
 *
 * Distinct from the 'first_' properties above: those are permanent, set once
 * per browser and never overwritten, so a returning visitor's original
 * touchpoint from months ago still wins there. A specific campaign — "did
 * people from this email actually complete the funnel on THIS visit?" —
 * needs this visit's own tag instead, which is what this plain (unprefixed)
 * version provides for the rest of the current session.
 *
 * No-op without consent — an unconsented visitor still gets nothing written
 * to storage, same rule as everywhere else in this file.
 */
export function registerCampaignProps(props) {
  if (!isGranted() || Object.keys(props).length === 0) return;
  mixpanel.register(props);
}
