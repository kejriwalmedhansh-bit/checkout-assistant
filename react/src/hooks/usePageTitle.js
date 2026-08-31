import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const SUFFIX = 'Dealo';
const SITE_URL = 'https://getdealo.in';
const DEFAULT_DESCRIPTION =
  'Dealo finds the cheapest legitimate way to buy anything online in India — stacking discounted gift vouchers with cashback cards to cut your final checkout price.';
const DEFAULT_OG_TITLE = 'Dealo — Never pay full price, just search the product';

function setMeta(selector, content) {
  const el = document.querySelector(selector);
  if (el) el.setAttribute('content', content);
}

/**
 * Sets everything a search engine or a link preview (WhatsApp, Twitter,
 * Slack) actually reads for the current page — tab title, meta description,
 * canonical URL, and the Open Graph / Twitter mirrors of title+description —
 * all restored to the site-wide default on unmount so navigating away (or
 * back to a page that doesn't call this) never leaves stale values behind.
 * `path` overrides the canonical URL for a page whose route param isn't the
 * canonical form (not currently needed, but kept as an escape hatch).
 */
export function usePageTitle(title, description, path) {
  const location = useLocation();

  useEffect(() => {
    const fullTitle = title ? `${title} — ${SUFFIX}` : SUFFIX;
    const desc = description || DEFAULT_DESCRIPTION;
    const canonicalUrl = `${SITE_URL}${path ?? location.pathname}`;

    document.title = fullTitle;
    setMeta('meta[name="description"]', desc);
    setMeta('meta[property="og:title"]', title ? fullTitle : DEFAULT_OG_TITLE);
    setMeta('meta[property="og:description"]', desc);
    setMeta('meta[property="og:url"]', canonicalUrl);
    setMeta('meta[name="twitter:title"]', title ? fullTitle : DEFAULT_OG_TITLE);
    setMeta('meta[name="twitter:description"]', desc);

    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.setAttribute('href', canonicalUrl);

    return () => {
      document.title = SUFFIX;
      setMeta('meta[name="description"]', DEFAULT_DESCRIPTION);
      setMeta('meta[property="og:title"]', DEFAULT_OG_TITLE);
      setMeta('meta[property="og:description"]', DEFAULT_DESCRIPTION);
      setMeta('meta[property="og:url"]', `${SITE_URL}/`);
      setMeta('meta[name="twitter:title"]', DEFAULT_OG_TITLE);
      setMeta('meta[name="twitter:description"]', DEFAULT_DESCRIPTION);
      if (canonical) canonical.setAttribute('href', `${SITE_URL}/`);
    };
  }, [title, description, path, location.pathname]);
}
