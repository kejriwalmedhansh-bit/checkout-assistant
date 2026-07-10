/**
 * Lucide-style line icons + brand glyphs.
 *
 * Each icon is a chakra <svg> so it accepts Chakra style props — notably `color`
 * (which flows into `stroke="currentColor"`) and `boxSize`. Pass `size` for px,
 * or any color token via `color="orange"`.
 */
import { chakra } from '@chakra-ui/react';

const Svg = chakra('svg');

function BaseIcon({ size = 20, sw = 1.8, fill = 'none', children, ...rest }) {
  return (
    <Svg
      width={`${size}px`}
      height={`${size}px`}
      viewBox="0 0 24 24"
      fill={fill}
      stroke="currentColor"
      strokeWidth={sw}
      strokeLinecap="round"
      strokeLinejoin="round"
      display="inline-block"
      flex="0 0 auto"
      {...rest}
    >
      {children}
    </Svg>
  );
}

export const I = {
  copy: (p) => (
    <BaseIcon {...p}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </BaseIcon>
  ),
  info: (p) => (
    <BaseIcon {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5" />
      <path d="M12 8h.01" />
    </BaseIcon>
  ),
  home: (p) => (
    <BaseIcon {...p}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5" />
      <path d="M9.5 21v-6h5v6" />
    </BaseIcon>
  ),
  gauge: (p) => (
    <BaseIcon {...p}>
      <path d="M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />
      <path d="m13.4 10.6 3.6-3.6" />
      <path d="M3.5 18a9 9 0 1 1 17 0" />
    </BaseIcon>
  ),
  search: (p) => (
    <BaseIcon {...p}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.2-3.2" />
    </BaseIcon>
  ),
  ticket: (p) => (
    <BaseIcon {...p}>
      <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" />
      <path d="M13 5v14" />
    </BaseIcon>
  ),
  cart: (p) => (
    <BaseIcon {...p}>
      <circle cx="8" cy="21" r="1" />
      <circle cx="19" cy="21" r="1" />
      <path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" />
    </BaseIcon>
  ),
  store: (p) => (
    <BaseIcon {...p}>
      <path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z" />
      <path d="M16 3H8l-2 4h12l-2-4z" />
    </BaseIcon>
  ),
  chevDown: (p) => (
    <BaseIcon {...p}>
      <path d="m6 9 6 6 6-6" />
    </BaseIcon>
  ),
  chevRight: (p) => (
    <BaseIcon {...p}>
      <path d="m9 6 6 6-6 6" />
    </BaseIcon>
  ),
  arrowRight: (p) => (
    <BaseIcon {...p}>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </BaseIcon>
  ),
  arrowLeft: (p) => (
    <BaseIcon {...p}>
      <path d="M19 12H5" />
      <path d="m11 6-6 6 6 6" />
    </BaseIcon>
  ),
  arrowUp: (p) => (
    <BaseIcon {...p}>
      <path d="m6 14 6-6 6 6" />
    </BaseIcon>
  ),
  trendUp: (p) => (
    <BaseIcon {...p}>
      <path d="m3 17 6-6 4 4 8-8" />
      <path d="M17 7h4v4" />
    </BaseIcon>
  ),
  sun: (p) => (
    <BaseIcon {...p}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </BaseIcon>
  ),
  moon: (p) => (
    <BaseIcon {...p}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4 7 7 0 1 0 20 14.5Z" />
    </BaseIcon>
  ),
  check: (p) => (
    <BaseIcon {...p}>
      <path d="m5 12.5 4.5 4.5L19 7" />
    </BaseIcon>
  ),
  checkCircle: (p) => (
    <BaseIcon {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </BaseIcon>
  ),
  alert: (p) => (
    <BaseIcon {...p}>
      <path d="M12 3 2.5 19.5h19L12 3Z" />
      <path d="M12 10v4" />
      <path d="M12 17.2v.1" />
    </BaseIcon>
  ),
  zap: (p) => (
    <BaseIcon {...p}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </BaseIcon>
  ),
  link: (p) => (
    <BaseIcon {...p}>
      <path d="M9 15a4 4 0 0 0 5.6 0l2.4-2.4a4 4 0 0 0-5.6-5.6l-1 1" />
      <path d="M15 9a4 4 0 0 0-5.6 0L7 11.4a4 4 0 0 0 5.6 5.6l1-1" />
    </BaseIcon>
  ),
  globe: (p) => (
    <BaseIcon {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3c2.5 2.6 2.5 15.4 0 18M12 3c-2.5 2.6-2.5 15.4 0 18" />
    </BaseIcon>
  ),
  doc: (p) => (
    <BaseIcon {...p}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 16.5h6" />
    </BaseIcon>
  ),
  external: (p) => (
    <BaseIcon {...p}>
      <path d="M14 4h6v6" />
      <path d="M20 4 11 13" />
      <path d="M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4" />
    </BaseIcon>
  ),
  menu: (p) => (
    <BaseIcon {...p}>
      <path d="M3 6h18M3 12h18M3 18h18" />
    </BaseIcon>
  ),
  star: (p) => (
    <BaseIcon {...p}>
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </BaseIcon>
  ),
  x: (p) => (
    <BaseIcon {...p}>
      <path d="M18 6 6 18M6 6l12 12" />
    </BaseIcon>
  ),
};

/** Brand glyph: an open ring with an arrow launching out to the top-right. */
export const SoloMark = ({ size = 16, color = '#fff' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="2.6"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    {/* open ring (gap at the top-right where the arrow exits) */}
    <path d="M12 5 A7 7 0 1 0 16.9 7" />
    {/* arrow shaft + head pointing up-right */}
    <path d="M10 14 L15.4 8.6" />
    <path d="M11.7 8.6 L15.4 8.6 L15.4 12.3" />
  </svg>
);
