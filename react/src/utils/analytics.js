import mixpanel from 'mixpanel-browser';

import { MIXPANEL_TOKEN } from '@/config';

const USER_ID_KEY = 'dealo_user_id';

/** Fallback id holder for browsers where localStorage throws (Safari private mode). */
let memoryUserId = null;

/** True when the id was read back from storage rather than minted this visit. */
let isReturningVisitor = false;

function newId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  // Older Safari/WebView: good enough for an anonymous analytics handle.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * A stable, anonymous per-browser id, minted on first visit and reused after
 * that. Not tied to a person — it's a handle for stitching one visitor's events
 * together across sessions, and it resets if they clear site data.
 */
export function getUserId() {
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

  // The search box is the app's only text input, and it holds a product query
  // or a merchant URL — never a password, email, or card number (checkout
  // happens on the merchant's site, not here). Masking it would hide the single
  // most useful thing in a replay: what the user actually typed.
  record_mask_inputs: false,

  // The SDK blocks img/video/audio by default. Dealo's UI is product cards, so
  // blocking images leaves replays as unreadable grey boxes. Audio/video stay
  // blocked — the app has neither.
  record_block_selector: 'video, audio',
});

const userId = getUserId();

// Use our own id as the distinct_id, so every event and replay is attributed to
// the same visitor across sessions instead of the SDK's own '$device:<uuid>'.
mixpanel.identify(userId);

// Also carried as a plain event property: it keeps the id queryable in Mixpanel
// even if distinct_id is later remapped (e.g. to a WhatsApp identity), and it
// survives a move off Mixpanel entirely.
mixpanel.register({ dealo_user_id: userId });

// Fired once per page load, at module scope rather than in a component so
// StrictMode's double-mount can't double-count it. Without this, a visitor who
// lands and leaves without searching would produce no events at all.
mixpanel.track('Dashboard Opened', { is_returning_visitor: isReturningVisitor });

/** Fire-and-forget event tracking. */
export function track(event, props = {}) {
  mixpanel.track(event, props);
}
