/**
 * Type system — native system font stack (apple-system first) for everything.
 *
 * CONFIG: `LABEL_FONT` controls the font for the small uppercase labels, table
 * headers, and stat numbers (everything that uses `fontFamily="mono"`, e.g.
 * <Eyebrow>, <Chip>, <DataTable> headers). It currently uses the normal system
 * font. To restore the original monospaced look, set it to MONO_FONT below.
 */
const SYSTEM_STACK =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

const MONO_FONT = "'JetBrains Mono', ui-monospace, SFMono-Regular, monospace";

const LABEL_FONT = SYSTEM_STACK; // ← switch to MONO_FONT to bring monospace back

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
