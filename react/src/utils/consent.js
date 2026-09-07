/**
 * The visitor's answer to "may we record how you use Dealo?".
 *
 * Three states, and the difference between two of them matters:
 *
 *   'granted'  — they said yes. Full analytics and a session recording.
 *   'denied'   — they said no. No recording, no identifier, nothing stored.
 *   null       — they haven't answered yet. Treated exactly like 'denied'.
 *
 * Treating "hasn't answered" as "no" is the whole point of asking. If we
 * recorded until someone got around to refusing, the banner would be
 * decoration — the recording it asks permission for would already have
 * happened by the time anyone read it.
 *
 * The answer is the one thing kept for a visitor who says no, and it's kept
 * because saying no is worthless if we ask again on the next page. It's a
 * single word in this browser, readable by nobody but this site.
 */
const KEY = 'dealo_consent';

export const CONSENT_GRANTED = 'granted';
export const CONSENT_DENIED = 'denied';

/** Fires whenever the answer changes, so the banner and analytics both react. */
const listeners = new Set();

/**
 * Storage can throw outright (Safari private mode, browsers set to block site
 * data), and a visitor whose browser blocks storage must not end up recorded
 * by accident — so every failure path here reads as "no answer", which is
 * treated as no.
 */
export function getConsent() {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === CONSENT_GRANTED || v === CONSENT_DENIED ? v : null;
  } catch {
    return null;
  }
}

export function hasAnswered() {
  return getConsent() !== null;
}

export function isGranted() {
  return getConsent() === CONSENT_GRANTED;
}

export function setConsent(value) {
  try {
    window.localStorage.setItem(KEY, value);
  } catch {
    // Nothing to do — an unstorable answer just means asking again next visit,
    // which is the safe direction to fail in.
  }
  listeners.forEach((fn) => fn(value));
}

export function onConsentChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/**
 * Erases everything analytics put in this browser. Called when someone
 * withdraws consent, because "you can change your mind" has to mean the
 * identifier goes too — otherwise the same person is recognisable again the
 * moment they say yes a second time.
 */
export function clearAnalyticsStorage() {
  try {
    Object.keys(window.localStorage)
      .filter((k) => k.startsWith('mp_') || k === 'dealo_user_id')
      .forEach((k) => window.localStorage.removeItem(k));
  } catch {
    // Same as above — if storage is unreadable there is nothing stored to clear.
  }
}
