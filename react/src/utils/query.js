/**
 * Search-input normalization shared by every entry point into a search.
 *
 * Mirrors `_extract_pasted_url` in src/services/search_service.py — the
 * backend does this too (it has to, WhatsApp doesn't come through here), but
 * the frontend needs its own copy so the header, the search box, and the
 * persisted store all show the link the user is actually searching, not the
 * store app's share blurb wrapped around it.
 */

// A link shared from a store app arrives with the app's own blurb attached:
// "https://dl.flipkart.com/s/!A4VgYNNNN Take a look at this … on Flipkart".
const EMBEDDED_URL_RE = /https?:\/\/\S+/i;

// Sentence punctuation that can end up glued to a link ("…/p/itm123."). '!'
// is deliberately absent — Flipkart's own short links contain it.
const TRAILING_PUNCT_RE = /[.,;:'"“”‘’>)\]}]+$/;

/**
 * If the input contains a link, return just that link; otherwise return the
 * input trimmed. A link names one specific product page, so it always wins
 * over whatever text is sitting next to it.
 */
export function normalizeSearchInput(input) {
  const text = (input || '').trim();
  const match = text.match(EMBEDDED_URL_RE);
  if (!match) return text;
  return match[0].replace(TRAILING_PUNCT_RE, '') || text;
}
