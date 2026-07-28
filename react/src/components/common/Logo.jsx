import { Box, Flex, Text } from '@chakra-ui/react';

import LogoIcon from './LogoIcon';

/**
 * Dealo wordmark + icon, the approved "final lockup": the mark (see
 * LogoIcon) next to lowercase "dealo" — "deal" in brand navy, the final "o"
 * in copper, echoing the icon's own ink-route/copper-dot split. Replaces the
 * earlier text-only wordmark (2026-07-28 homepage redesign) now that a real
 * icon glyph exists.
 */
export default function Logo({ size = 24, iconSize }) {
  // `size` is normally a plain number (px), but accepts a Chakra responsive
  // object (e.g. `{ base: '48px', md: '68px' }`) for hero-scale usage where
  // the wordmark itself needs to scale with the viewport like the headline
  // next to it does.
  const fontSize = typeof size === 'number' ? `${size}px` : size;
  const resolvedIconSize = iconSize ?? (typeof size === 'number' ? Math.round(size * 0.9) : size);
  const gap = typeof size === 'number' ? `${Math.max(6, Math.round(size * 0.26))}px` : '10px';

  return (
    <Flex as="span" align="center" gap={gap}>
      <LogoIcon size={resolvedIconSize} />
      <Text as="span" fontSize={fontSize} fontWeight={800} letterSpacing="-.02em" lineHeight={1} whiteSpace="nowrap">
        <Box as="span" color="brand">
          deal
        </Box>
        <Box as="span" color="brass">
          o
        </Box>
      </Text>
    </Flex>
  );
}
