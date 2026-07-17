/**
 * Elevation + focus-ring tokens, light/dark aware. Neutral shadows unchanged;
 * the `brand` glow and `ring` focus tokens are colored to Dealo green.
 */
export const semanticShadows = {
  sm: {
    default: '0 1px 2px rgba(18,21,26,.05), 0 1px 1px rgba(18,21,26,.04)',
    _dark: '0 1px 2px rgba(0,0,0,.4)',
  },
  md: {
    default: '0 4px 14px rgba(18,21,26,.06), 0 1px 3px rgba(18,21,26,.05)',
    _dark: '0 4px 14px rgba(0,0,0,.4)',
  },
  lg: {
    default: '0 18px 50px -12px rgba(18,21,26,.18), 0 6px 18px rgba(18,21,26,.06)',
    _dark: '0 24px 60px -14px rgba(0,0,0,.66)',
  },
  brand: {
    default: '0 10px 28px -8px rgba(10,107,65,.45)',
    _dark: '0 10px 28px -8px rgba(57,181,124,.40)',
  },
  ring: {
    default: '0 0 0 4px rgba(10,107,65,.16)',
    _dark: '0 0 0 4px rgba(57,181,124,.22)',
  },
  savingsHairline: {
    default: '0 1px 0 rgba(10,107,65,.08)',
    _dark: '0 1px 0 rgba(57,181,124,.10)',
  },
};
