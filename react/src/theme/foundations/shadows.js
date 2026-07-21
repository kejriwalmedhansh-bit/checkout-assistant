/**
 * Elevation + focus-ring tokens. Dark is the only mode Dealo ships, so each
 * token is a single flat value; the `brand` glow and `ring` focus tokens are
 * colored to Dealo green.
 */
export const semanticShadows = {
  sm: '0 1px 2px rgba(0,0,0,.4)',
  md: '0 4px 14px rgba(0,0,0,.4)',
  lg: '0 24px 60px -14px rgba(0,0,0,.66)',
  brand: '0 10px 28px -8px rgba(57,181,124,.40)',
  ring: '0 0 0 4px rgba(57,181,124,.22)',
  savingsHairline: '0 1px 0 rgba(57,181,124,.10)',
  // Tight brand-green glow for small elements (the card-visual chip).
  // `brand` above is a looser glow sized for larger surfaces.
  brandGlowCard: '0 3px 8px -2px rgba(57,181,124,.38)',
  // Ink-colored photo drop-shadow (ProductIdentity's hero image). Flat black,
  // matching the sm/md/lg pattern. Two layers stacked (tight + soft) read as
  // a real studio product shot rather than a flat cutout: `photoDrop` hugs
  // the product, `photoDropSoft` is the larger, fainter ambient falloff
  // beneath it.
  photoDrop: '0 8px 14px rgba(0,0,0,.45)',
  photoDropSoft: '0 22px 30px rgba(0,0,0,.35)',
};
