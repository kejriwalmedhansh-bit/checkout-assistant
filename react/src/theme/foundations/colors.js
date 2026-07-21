/**
 * Semantic color tokens — the single source of truth for the palette.
 *
 * Dark is the only mode Dealo ships, so each token is a single flat value
 * (no `default`/`_dark` pair) — components still reference these names
 * (e.g. `bg="surface"`, `color="text2"`) exactly as before.
 */
export const semanticColors = {
  // "Ledger" palette — cool paper canvas (precision/audit-trail feel, not a
  // cozy cream), white cards, near-black ink text.
  bg: '#121311',
  bgGrid: '#262920',
  sidebar: '#171812',
  surface: '#1A1C18',
  surface2: '#1F211B',
  surface3: '#232019',
  border: '#2C2E27',
  borderStrong: '#3A3D33',
  text: '#EFEEE8',
  text2: '#A5A99F',
  text3: '#787D72',

  // brand — deep ledger-green (darker/more serious than the old brand green)
  brand: '#39B57C',
  brandHover: '#4FD693',
  brandSoft: '#193226',
  brandSoft2: '#0F241A',
  brandText: '#5FD99C',

  // Foreground for anything sitting ON a brand/green fill — primary buttons,
  // the numbered step circles, the savings pill. Near-black rather than
  // white: white only clears contrast against the deeper light-mode green
  // Dealo no longer uses — against this brighter dark-mode green, near-black
  // is what actually passes (7.2:1 vs white's 2.6:1). Never hardcode
  // `color="white"` over a brand fill.
  onBrand: '#0B1410',

  // brass — the one deliberate rich accent, used sparingly (verification/
  // confirmation moments only, not general UI)
  brass: '#D9A748',
  brassSoft: '#2E2617',

  // secondary accents
  cyan: '#2BC6D6',
  cyanSoft: '#16323A',
  green: '#39B57C',
  greenSoft: '#193226',
  amber: '#E0A93B',
  amberSoft: '#322611',
  violet: '#A48BEC',
  violetSoft: '#251C3A',

  // danger
  danger: '#E0685A',
};

/**
 * Multi-stop gradients that don't fit the token model. Kept here so every visual
 * constant still lives in the theme layer. All recolored to Dealo green.
 */
export const gradients = {
  brandAvatar: 'linear-gradient(135deg, #39B57C, var(--chakra-colors-brand))',
  usageBar: 'linear-gradient(90deg, #39B57C, var(--chakra-colors-brand))',

  // "search hero" glow — a soft, minimal green glow that fades in from the
  // top of the screen. Built on transparent stops so it washes over the
  // page background without introducing a hard surface.
  promptHero:
    'radial-gradient(72% 60% at 50% -12%, rgba(57,181,124,.20) 0%, rgba(57,181,124,0) 68%)',
};
