import mixpanel from 'mixpanel-browser';

import { MIXPANEL_TOKEN } from '@/config';
import { clearAnalyticsStorage, isGranted, onConsentChange } from '@/utils/consent';

const USER_ID_KEY = 'dealo_user_id';
const INTERNAL_TESTER_KEY = 'dealo_internal_tester';

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

function environment() {
  return window.location.hostname === 'getdealo.in' ? 'production' : 'development';
}

/**
 * The stage counters kept for visitors who haven't agreed to be recorded.
 *
 * Only these event names are sent, only their names, and every one of them is
 * a step in the funnel — enough to answer "where do people stop?", which is
 * the question the recording was for. Anything carrying detail about a
 * particular person or what they searched for is not on this list.
 */
const ANONYMOUS_STAGES = new Set([
  'Dashboard Opened',
  'Searched',
  'Selected Product',
  'Viewed Deal',
  'Clicked Buy Link',
]);

/**
 * One shared id for every un-consented visitor, so Mixpanel counts the step
 * and cannot tell two people apart — which is the point. Sent with ip=0 so no
 * address is recorded and no location derived from one, and by fetch rather
 * than through the SDK, because the SDK would write its own identifier into
 * storage on the way past — which is exactly what a visitor who said no is
 * entitled not to have happen.
 */
const ANONYMOUS_ID = 'anonymous';

function countStage(event) {
  if (!ANONYMOUS_STAGES.has(event)) return;
  const payload = [{
    event,
    properties: {
      token: MIXPANEL_TOKEN,
      distinct_id: ANONYMOUS_ID,
      time: Math.floor(Date.now() / 1000),
      consent: 'not_granted',
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

  // Use our own id as the distinct_id, so every event and replay is attributed to
  // the same visitor across sessions instead of the SDK's own '$device:<uuid>'.
  mixpanel.identify(userId);

  mixpanel.register({
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
if (!isGranted()) countStage('Dashboard Opened');

/** Fire-and-forget event tracking. */
export function track(event, props = {}) {
  if (isGranted()) mixpanel.track(event, props);
  else countStage(event);
}
