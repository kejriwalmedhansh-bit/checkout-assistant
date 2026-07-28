/**
 * Semantic color tokens — the single source of truth for the palette.
 *
 * Flat values, no `default`/`_dark` pair — components reference these names
 * (e.g. `bg="surface"`, `color="text2"`) exactly as before regardless of
 * which palette lives here.
 */
export const semanticColors = {
  // "Ink & Copper" palette — white/off-white paper canvas, white cards, deep
  // navy-ink text. Replaces the earlier dark-only "Ledger" green palette
  // (2026-07-28 homepage redesign) — chosen over the docs' other two
  // directions (plain teal-from-logo, and the Brand Kit's green+gold) after
  // side-by-side mockup review.
  bg: '#FAFAF7',
  bgGrid: '#EDEBE3',
  sidebar: '#F3F1EA',
  surface: '#FFFFFF',
  surface2: '#FBFAF7',
  surface3: '#EFEDE5',
  border: '#E4E1D6',
  borderStrong: '#CFCBBB',
  text: '#16202B',
  text2: '#5B655F',
  text3: '#8A9089',

  // brand — deep navy (trust/finance-coded, not the old green)
  brand: '#1F3A5F',
  brandHover: '#16304E',
  brandSoft: '#E7EDF3',
  brandSoft2: '#EFF3F7',
  brandText: '#1F3A5F',

  // Foreground for anything sitting ON a brand/navy fill — primary buttons,
  // the numbered step circles, the savings pill. Near-white rather than
  // near-black: the brand fill itself is now dark, so light text is what
  // actually passes contrast (unlike the old bright-green fill, which needed
  // near-black text). Never hardcode `color="white"` over a brand fill —
  // use this token so it keeps tracking whatever `brand` is.
  onBrand: '#F7F5EF',

  // brass/copper — the one deliberate rich accent, used sparingly
  // (verification/confirmation moments only, not general UI)
  brass: '#C1712F',
  brassSoft: '#F5E4D3',

  // secondary accents
  cyan: '#1E8FA0',
  cyanSoft: '#E3F1F3',
  green: '#1F7A52',
  greenSoft: '#E6F1EA',
  amber: '#B8842A',
  amberSoft: '#F7ECD6',
  violet: '#6B4FB8',
  violetSoft: '#F0EBFB',

  // danger
  danger: '#B23A2E',
};

/**
 * Multi-stop gradients that don't fit the token model. Kept here so every visual
 * constant still lives in the theme layer. Recolored to navy/copper.
 */
export const gradients = {
  brandAvatar: 'linear-gradient(135deg, var(--chakra-colors-brandHover), var(--chakra-colors-brand))',
  usageBar: 'linear-gradient(90deg, var(--chakra-colors-brandHover), var(--chakra-colors-brand))',

  // "search hero" wash — a soft, minimal copper warmth fading in from the
  // top of the screen. Much lower alpha than the old dark-mode glow: a
  // saturated color reads far heavier at the same opacity against white
  // than it did against near-black.
  promptHero:
    'radial-gradient(72% 60% at 50% -12%, rgba(193,113,47,.10) 0%, rgba(193,113,47,0) 68%)',
};
