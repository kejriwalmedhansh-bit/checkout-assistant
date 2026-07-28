import { Box } from '@chakra-ui/react';

/**
 * The Dealo mark on its own — a ring "picked up," a dashed route, and a dot
 * "dropped off," reading as a stylized checkmark/route glyph. Matches the
 * approved "final lockup" exactly: flat-ended dashes (not a solid line —
 * an earlier round used solid and was corrected), ink ring/route, copper
 * dot as the one confirmation-colored accent (same job `brass` does
 * elsewhere — see colors.js).
 */
export default function LogoIcon({ size = 24 }) {
  const px = typeof size === 'number' ? `${size}px` : size;
  return (
    <Box as="svg" viewBox="0 0 64 64" w={px} h={px} flex="0 0 auto" display="block" aria-hidden="true">
      <circle cx="15" cy="49" r="5.5" fill="none" stroke="var(--chakra-colors-text)" strokeWidth="5" />
      <path
        d="M15 39.5 C15 26 49 38 49 23"
        fill="none"
        stroke="var(--chakra-colors-text)"
        strokeWidth="7"
        strokeLinecap="butt"
        strokeDasharray="8.5 6.5"
      />
      <circle cx="49" cy="17" r="7.5" fill="var(--chakra-colors-brass)" />
    </Box>
  );
}
