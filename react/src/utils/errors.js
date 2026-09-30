const FALLBACK = 'Something went wrong on our side. Please try again in a moment.';

/**
 * Server-side failure text that was written for a log, not for a person:
 * "SearchApi returned HTTP 429", "KeyError: 'price'", axios's own "Request
 * failed with status code 500". The backend also sends real, hand-written
 * messages through the same field ("Couldn't find a product on that page…"),
 * so those pass through and only this kind is swapped for plain wording.
 */
const TECHNICAL = /SearchApi|HTTP \d{3}|status code|Request failed|Bad response|_KEY\b|not configured|timeout of|Network Error|Traceback|^[A-Z]\w*(Error|Exception)\b|^Empty query\.?$/;

/** A message safe to put in front of a visitor. */
export function friendlyMessage(message, fallback = FALLBACK) {
  if (typeof message !== 'string' || !message.trim() || TECHNICAL.test(message)) return fallback;
  return message;
}

/**
 * Turn an axios/network error into a user-presentable message.
 * The backend surfaces problems as FastAPI `{ detail: "..." }`; validation
 * arrays and raw exception text are never shown as-is.
 */
export function extractErrorMessage(error, fallback = FALLBACK) {
  if (!error) return fallback;

  // Network / no response
  if (error.request && !error.response) {
    return 'Could not reach Dealo. Check your connection and try again.';
  }

  if (error.response?.status >= 500) return fallback;

  const detail = error.response?.data?.detail;
  return friendlyMessage(typeof detail === 'string' ? detail : null, fallback);
}
