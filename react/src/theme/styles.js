/** Global base styles — body type/canvas, selection color, custom scrollbars. */
export const styles = {
  global: {
    'html, body, #root': { height: '100%' },
    // Stop iPhones enlarging text on their own when the phone is turned sideways.
    html: { WebkitTextSizeAdjust: '100%', textSizeAdjust: '100%' },
    body: {
      bg: 'bg',
      // Nothing on the page may push it wider than the screen. Each page is
      // built to fit already; this is the safety net, so one stray element
      // can never again make a phone zoom out or show an edge strip.
      overflowX: 'clip',
      color: 'text',
      fontFamily: 'body',
      WebkitFontSmoothing: 'antialiased',
      textRendering: 'optimizeLegibility',
    },
    // iPhones zoom the whole page in when you tap a text box whose text is
    // smaller than 16px, and never zoom back out after you leave it — the
    // header slides off-screen and every later page stays zoomed. 16px on
    // touch screens stops that at the source; laptops keep the smaller size.
    '@media (pointer: coarse)': {
      'input, select, textarea': { fontSize: '16px !important' },
    },
    // No grey flash on tap, and no 300ms wait while the phone checks for a
    // double-tap zoom.
    'a, button, [role="button"], label, summary': {
      WebkitTapHighlightColor: 'transparent',
      touchAction: 'manipulation',
    },
    '::selection': { bg: 'brand', color: 'onBrand' },
    '*::-webkit-scrollbar': { width: '10px', height: '10px' },
    '*::-webkit-scrollbar-thumb': {
      background: 'var(--chakra-colors-borderStrong)',
      borderRadius: '99px',
      border: '3px solid transparent',
      backgroundClip: 'content-box',
    },
    '*::-webkit-scrollbar-track': { background: 'transparent' },
    a: { color: 'inherit', textDecoration: 'none' },
  },
};
