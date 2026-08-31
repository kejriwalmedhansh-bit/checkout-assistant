import { useEffect } from 'react';

const SUFFIX = 'Dealo';
const DEFAULT_DESCRIPTION =
  'Dealo finds the cheapest legitimate way to buy anything online in India — stacking discounted gift vouchers with cashback cards to cut your final checkout price.';

/**
 * Sets the tab title and, optionally, the meta description — both restored
 * to the site-wide default on unmount so navigating away (or back to a page
 * that doesn't call this) never leaves a stale description behind.
 */
export function usePageTitle(title, description) {
  useEffect(() => {
    document.title = title ? `${title} — ${SUFFIX}` : SUFFIX;
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', description || DEFAULT_DESCRIPTION);
    return () => {
      document.title = SUFFIX;
      if (meta) meta.setAttribute('content', DEFAULT_DESCRIPTION);
    };
  }, [title, description]);
}
