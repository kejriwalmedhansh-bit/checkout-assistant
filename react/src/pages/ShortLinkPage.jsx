import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { ROUTES } from '@/routes/paths';
import { readShortLink } from '@/seo/shortLinks';

/**
 * A short link (getdealo.in/ig, /ig/dominos, see seo/shortLinks.js) lands
 * here and is sent straight on: to the shop page when the second part names
 * one, otherwise to the homepage. The source was already read from the
 * address when the site loaded (currentTouch), so nothing is recorded here;
 * `replace` keeps the short address out of the Back button.
 */
export default function ShortLinkPage() {
  const { pathname } = useLocation();
  const link = readShortLink(pathname);
  // No second part: the homepage, with nothing to look up.
  const [target, setTarget] = useState(link?.name ? null : ROUTES.home);

  useEffect(() => {
    if (!link?.name) return undefined;
    let live = true;
    // The shop list is large and the shop page needs it anyway, so it is
    // fetched only for a link that might name a shop.
    import('@/data/shopPages.json')
      .then((mod) => {
        const isShop = (mod.default || []).some((s) => s.slug === link.name);
        if (live) setTarget(isShop ? ROUTES.brandFor(link.name) : ROUTES.home);
      })
      .catch(() => live && setTarget(ROUTES.home));
    return () => {
      live = false;
    };
  }, [link?.name]);

  return target ? <Navigate to={target} replace /> : null;
}
