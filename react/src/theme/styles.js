/** Global base styles — body type/canvas, selection color, custom scrollbars. */
export const styles = {
  global: {
    'html, body, #root': { height: '100%' },
    body: {
      bg: 'bg',
      color: 'text',
      fontFamily: 'body',
      WebkitFontSmoothing: 'antialiased',
      textRendering: 'optimizeLegibility',
    },
    '::selection': { bg: 'brand', color: 'white' },
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
