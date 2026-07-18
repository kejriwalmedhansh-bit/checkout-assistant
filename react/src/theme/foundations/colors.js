/**
 * Semantic color tokens — the single source of truth for the palette.
 *
 * Each token carries a `default` (light) and `_dark` value. Components reference
 * these names (e.g. `bg="surface"`, `color="text2"`) and Chakra resolves the
 * correct value for the active color mode automatically — so flipping the theme
 * toggle re-themes the whole app with no per-component conditionals.
 *
 */
export const semanticColors = {
  // "Ledger" palette — cool paper canvas (precision/audit-trail feel, not a
  // cozy cream), white cards, near-black ink text.
  bg: { default: '#F1F2EE', _dark: '#121311' },
  bgGrid: { default: '#D7DAD1', _dark: '#262920' },
  sidebar: { default: '#F7F7F4', _dark: '#171812' },
  surface: { default: '#FFFFFF', _dark: '#1A1C18' },
  surface2: { default: '#FBFBF9', _dark: '#1F211B' },
  surface3: { default: '#EDEEE8', _dark: '#232019' },
  border: { default: '#DBDCD3', _dark: '#2C2E27' },
  borderStrong: { default: '#C7C9BC', _dark: '#3A3D33' },
  text: { default: '#12151A', _dark: '#EFEEE8' },
  text2: { default: '#585F5B', _dark: '#A5A99F' },
  text3: { default: '#8B918C', _dark: '#787D72' },

  // brand — deep ledger-green (darker/more serious than the old brand green)
  brand: { default: '#0A6B41', _dark: '#39B57C' },
  brandHover: { default: '#084F31', _dark: '#4FD693' },
  brandSoft: { default: '#E4EEE6', _dark: '#193226' },
  brandSoft2: { default: '#F1F7F3', _dark: '#0F241A' },
  brandText: { default: '#084F31', _dark: '#5FD99C' },

  // brass — the one deliberate rich accent, used sparingly (verification/
  // confirmation moments only, not general UI)
  brass: { default: '#B9852E', _dark: '#D9A748' },
  brassSoft: { default: '#F4E7CC', _dark: '#2E2617' },

  // secondary accents
  cyan: { default: '#14ACBC', _dark: '#2BC6D6' },
  cyanSoft: { default: '#DDF4F6', _dark: '#16323A' },
  green: { default: '#0A6B41', _dark: '#39B57C' },
  greenSoft: { default: '#E4EEE6', _dark: '#193226' },
  amber: { default: '#C98A12', _dark: '#E0A93B' },
  amberSoft: { default: '#FBEFD6', _dark: '#322611' },
  violet: { default: '#7C5CD1', _dark: '#A48BEC' },
  violetSoft: { default: '#EEE9FB', _dark: '#251C3A' },

  // danger
  danger: { default: '#B23A2E', _dark: '#E0685A' },
};

/**
 * Multi-stop gradients that don't fit the token model. Kept here so every visual
 * constant still lives in the theme layer. All recolored to Dealo green.
 */
export const gradients = {
  logoMark: 'linear-gradient(150deg, #39B57C, var(--chakra-colors-brand))',
  brandAvatar: 'linear-gradient(135deg, #39B57C, var(--chakra-colors-brand))',
  usageBar: 'linear-gradient(90deg, #39B57C, var(--chakra-colors-brand))',

  // "search hero" glow — a soft, minimal green glow that fades in from the top of
  // the screen. Built on transparent stops so it washes over the page background
  // (light or dark) without introducing a hard surface.
  promptHeroLight:
    'radial-gradient(72% 60% at 50% -12%, rgba(10,107,65,.16) 0%, rgba(10,107,65,0) 68%)',
  promptHeroDark:
    'radial-gradient(72% 60% at 50% -12%, rgba(57,181,124,.20) 0%, rgba(57,181,124,0) 68%)',
};
