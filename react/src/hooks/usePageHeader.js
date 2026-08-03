import { createContext, useContext, useEffect } from 'react';

/**
 * Lets a page put content into AppLayout's mobile top bar (left/right of the
 * logo) instead of spending its own vertical space on a duplicate row —
 * added when the results page's in-page Back + Search-again row was
 * measured to cost ~40px that a phone screen couldn't spare. AppLayout owns
 * the setter; a page calls the hook with the JSX it wants shown there.
 */
export const PageHeaderContext = createContext(() => {});

export function usePageHeader(content) {
  const setPageHeader = useContext(PageHeaderContext);
  useEffect(() => {
    setPageHeader(content);
    return () => setPageHeader(null);
  });
}
