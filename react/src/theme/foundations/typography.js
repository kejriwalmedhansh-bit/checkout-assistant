/**
 * Type system — native system font stack (apple-system first) for body text.
 *
 * `LABEL_FONT` controls the font for prices, small uppercase labels, table
 * headers, and stat numbers (everything that uses `fontFamily="mono"`, e.g.
 * <Eyebrow>, <Chip>, <DataTable> headers, price displays). Set to MONO_FONT
 * so numbers read as precise/tabular — fits Dealo's exact-savings positioning.
 * Requires the JetBrains Mono <link> in index.html.
 */
const SYSTEM_STACK =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

const MONO_FONT = "'JetBrains Mono', ui-monospace, SFMono-Regular, monospace";

const LABEL_FONT = MONO_FONT;

export const fonts = {
  heading: SYSTEM_STACK,
  body: SYSTEM_STACK,
  mono: LABEL_FONT,
};

export const radii = {
  xs: '8px',
  sm: '12px',
  md: '16px',
  lg: '22px',
  pill: '999px',
};
