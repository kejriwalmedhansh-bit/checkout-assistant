import { useEffect } from 'react';
import Lenis from 'lenis';

// Smooth-scrolls the whole document for as long as the calling page is
// mounted; unmounting restores native scroll for every other route. Only
// worth wiring into pages with real scroll length (the brands index, ~900
// rows) — most of Dealo's pages are short by design and gain nothing from it.
export function useLenis(enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined;

    const lenis = new Lenis();
    let frameId;
    function raf(time) {
      lenis.raf(time);
      frameId = requestAnimationFrame(raf);
    }
    frameId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(frameId);
      lenis.destroy();
    };
  }, [enabled]);
}
