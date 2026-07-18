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
  // Tight brand-green glows for small elements (logo tile, card-visual chip).
  // `brand` above is a looser glow sized for larger surfaces.
  brandGlowLogo: {
    default: '0 4px 12px -3px rgba(10,107,65,.55)',
    _dark: '0 4px 12px -3px rgba(57,181,124,.48)',
  },
  brandGlowCard: {
    default: '0 3px 8px -2px rgba(10,107,65,.45)',
    _dark: '0 3px 8px -2px rgba(57,181,124,.38)',
  },
  // Ink-colored photo drop-shadow (ProductIdentity's hero image). Dark mode uses
  // flat black, matching the sm/md/lg pattern, not the (near-white) dark `text` hex.
  // Two layers stacked (tight + soft) read as a real studio product shot rather
  // than a flat cutout: `photoDrop` hugs the product, `photoDropSoft` is the
  // larger, fainter ambient falloff beneath it.
  photoDrop: {
    default: '0 8px 14px rgba(18,21,26,.14)',
    _dark: '0 8px 14px rgba(0,0,0,.45)',
  },
  photoDropSoft: {
    default: '0 22px 30px rgba(18,21,26,.08)',
    _dark: '0 22px 30px rgba(0,0,0,.35)',
  },
};
