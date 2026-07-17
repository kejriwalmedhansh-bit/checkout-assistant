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
  // warm whites / blacks — content canvas is white; the sidebar reads as a
  // subtle warm-grey rail against it.
  bg: { default: '#FFFFFF', _dark: '#141210' },
  bgGrid: { default: '#F1EDE7', _dark: '#1C1916' },
  sidebar: { default: '#FDFCFB', _dark: '#1A1613' },
  surface: { default: '#FFFFFF', _dark: '#1E1B18' },
  surface2: { default: '#FBFAF8', _dark: '#232019' },
  surface3: { default: '#F1EEE9', _dark: '#2A2620' },
  border: { default: '#EBE6DF', _dark: '#302B25' },
  borderStrong: { default: '#DCD5CB', _dark: '#3E382F' },
  text: { default: '#1C1916', _dark: '#F4F1EC' },
  text2: { default: '#6C665E', _dark: '#A49C90' },
  text3: { default: '#9E978D', _dark: '#756E63' },

  // brand — Dealo green
  brand: { default: '#1A9E63', _dark: '#34C57E' },
  brandHover: { default: '#158652', _dark: '#4FD693' },
  brandSoft: { default: '#E2F4EB', _dark: '#14301F' },
  brandSoft2: { default: '#F1FAF5', _dark: '#0F241A' },
  brandText: { default: '#147A4C', _dark: '#5FD99C' },

  // secondary accents
  cyan: { default: '#14ACBC', _dark: '#2BC6D6' },
  cyanSoft: { default: '#DDF4F6', _dark: '#16323A' },
  green: { default: '#1A9E63', _dark: '#34C57E' },
  greenSoft: { default: '#E2F4EB', _dark: '#14301F' },
  amber: { default: '#C98A12', _dark: '#E0A93B' },
  amberSoft: { default: '#FBEFD6', _dark: '#322611' },
  violet: { default: '#7C5CD1', _dark: '#A48BEC' },
  violetSoft: { default: '#EEE9FB', _dark: '#251C3A' },

  // danger
  danger: { default: '#E5533A', _dark: '#FF6B4F' },
};

/**
 * Multi-stop gradients that don't fit the token model. Kept here so every visual
 * constant still lives in the theme layer. All recolored to Dealo green.
 */
export const gradients = {
  logoMark: 'linear-gradient(150deg, #34C57E, var(--chakra-colors-brand))',
  brandAvatar: 'linear-gradient(135deg, #34C57E, var(--chakra-colors-brand))',
  usageBar: 'linear-gradient(90deg, #34C57E, var(--chakra-colors-brand))',

  // "search hero" glow — a soft, minimal green glow that fades in from the top of
  // the screen. Built on transparent stops so it washes over the page background
  // (light or dark) without introducing a hard surface.
  promptHeroLight:
    'radial-gradient(72% 60% at 50% -12%, rgba(26,158,99,.16) 0%, rgba(26,158,99,0) 68%)',
  promptHeroDark:
    'radial-gradient(72% 60% at 50% -12%, rgba(52,197,126,.20) 0%, rgba(52,197,126,0) 68%)',
};
