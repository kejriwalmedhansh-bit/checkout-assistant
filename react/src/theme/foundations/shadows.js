/**
 * Elevation + focus-ring tokens. Flat values (no light/dark pair); the
 * `brand` glow and `ring` focus tokens are colored to Dealo navy. Neutral
 * (black-based) shadows are intentionally much lower-alpha than the old
 * dark-mode values — a black shadow reads far more visible against white
 * than the same alpha did against a near-black page background.
 */
export const semanticShadows = {
  sm: '0 1px 2px rgba(16,20,15,.06)',
  md: '0 4px 14px rgba(16,20,15,.08)',
  lg: '0 24px 60px -14px rgba(16,20,15,.16)',
  brand: '0 10px 28px -8px rgba(31,58,95,.35)',
  ring: '0 0 0 4px rgba(31,58,95,.22)',
  savingsHairline: '0 1px 0 rgba(31,58,95,.12)',
  // Tight brand-navy glow for small elements (the card-visual chip).
  // `brand` above is a looser glow sized for larger surfaces.
  brandGlowCard: '0 3px 8px -2px rgba(31,58,95,.30)',
  // Ink-colored photo drop-shadow (ProductIdentity's hero image). Flat black,
  // matching the sm/md/lg pattern. Two layers stacked (tight + soft) read as
  // a real studio product shot rather than a flat cutout: `photoDrop` hugs
  // the product, `photoDropSoft` is the larger, fainter ambient falloff
  // beneath it.
  photoDrop: '0 8px 14px rgba(16,20,15,.14)',
  photoDropSoft: '0 22px 30px rgba(16,20,15,.10)',
};
