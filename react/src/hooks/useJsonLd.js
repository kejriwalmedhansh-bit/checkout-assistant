import { useEffect } from 'react';

/**
 * Injects a page-specific JSON-LD <script> into <head> for the lifetime of
 * the component, removed on unmount — for structured data that varies per
 * page (a brand's Product/Offer, this page's FAQ) rather than the
 * site-wide Organization/WebSite blocks that live statically in index.html.
 */
export function useJsonLd(data) {
  useEffect(() => {
    if (!data) return undefined;
    const script = document.createElement('script');
    script.type = 'application/ld+json';
    script.text = JSON.stringify(data);
    document.head.appendChild(script);
    return () => {
      document.head.removeChild(script);
    };
  }, [data]);
}
