/**
 * Elevation + focus-ring tokens, light/dark aware. Neutral shadows unchanged;
 * the `brand` glow and `ring` focus tokens are colored to Dealo green.
 */
export const semanticShadows = {
  sm: {
    default: '0 1px 2px rgba(28,25,22,.05), 0 1px 1px rgba(28,25,22,.04)',
    _dark: '0 1px 2px rgba(0,0,0,.4)',
  },
  md: {
    default: '0 4px 14px rgba(28,25,22,.06), 0 1px 3px rgba(28,25,22,.05)',
    _dark: '0 4px 14px rgba(0,0,0,.4)',
  },
  lg: {
    default: '0 18px 50px -12px rgba(28,25,22,.18), 0 6px 18px rgba(28,25,22,.06)',
    _dark: '0 24px 60px -14px rgba(0,0,0,.66)',
  },
  brand: {
    default: '0 10px 28px -8px rgba(26,158,99,.45)',
    _dark: '0 10px 28px -8px rgba(52,197,126,.40)',
  },
  ring: {
    default: '0 0 0 4px rgba(26,158,99,.16)',
    _dark: '0 0 0 4px rgba(52,197,126,.22)',
  },
  savingsHairline: {
    default: '0 1px 0 rgba(26,158,99,.08)',
    _dark: '0 1px 0 rgba(52,197,126,.10)',
  },
};
