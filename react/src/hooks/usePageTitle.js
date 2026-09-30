import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

import {
  DEFAULT_DESCRIPTION,
  HOME_TITLE,
  SITE_NAME as SUFFIX,
  SITE_URL,
} from '@/seo/pageMeta';

function setMeta(selector, content) {
  const el = document.querySelector(selector);
  if (el) el.setAttribute('content', content);
}

/**
 * The host redirects /privacy to /privacy/, so the slashed form is the only
 * address that actually answers — and it's the one scripts/prerender.mjs
 * writes a file for. Clicking a footer link inside the app produces the
 * unslashed pathname, though, so normalise here: otherwise the same page
 * claims two different canonical URLs depending on how you arrived, and a
 * search engine has to guess which one is real.
 */
function withTrailingSlash(pathname) {
  return pathname.endsWith('/') ? pathname : `${pathname}/`;
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
    const fullTitle = title ? `${title} — ${SUFFIX}` : HOME_TITLE;
    const desc = description || DEFAULT_DESCRIPTION;
    const canonicalUrl = `${SITE_URL}${withTrailingSlash(path ?? location.pathname)}`;

    document.title = fullTitle;
    setMeta('meta[name="description"]', desc);
    setMeta('meta[property="og:title"]', fullTitle);
    setMeta('meta[property="og:description"]', desc);
    setMeta('meta[property="og:url"]', canonicalUrl);
    setMeta('meta[name="twitter:title"]', fullTitle);
    setMeta('meta[name="twitter:description"]', desc);

    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) canonical.setAttribute('href', canonicalUrl);

    return () => {
      document.title = HOME_TITLE;
      setMeta('meta[name="description"]', DEFAULT_DESCRIPTION);
      setMeta('meta[property="og:title"]', HOME_TITLE);
      setMeta('meta[property="og:description"]', DEFAULT_DESCRIPTION);
      setMeta('meta[property="og:url"]', `${SITE_URL}/`);
      setMeta('meta[name="twitter:title"]', HOME_TITLE);
      setMeta('meta[name="twitter:description"]', DEFAULT_DESCRIPTION);
      if (canonical) canonical.setAttribute('href', `${SITE_URL}/`);
    };
  }, [title, description, path, location.pathname]);
}
