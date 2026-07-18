/**
 * Type system — "Ledger" pairing: Hanken Grotesk for UI/headings (warm,
 * humanist, not corporate), IBM Plex Mono for every rupee/percent value
 * (real tabular figures, reads as audited rather than terminal-flavored).
 * Self-hosted (not a Google Fonts CDN link — ad-blockers silently break
 * those) via @font-face declarations in src/styles/fonts.css.
 */
const SYSTEM_FALLBACK =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";
const MONO_FALLBACK = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';

const UI_FONT = `'Hanken Grotesk', ${SYSTEM_FALLBACK}`;
const MONO_FONT = `'IBM Plex Mono', ${MONO_FALLBACK}`;

export const fonts = {
  heading: UI_FONT,
  body: UI_FONT,
  mono: MONO_FONT,
};

export const radii = {
  xs: '8px',
  sm: '12px',
  md: '14px',
  lg: '20px',
  pill: '999px',
};
