import { Box, Text } from '@chakra-ui/react';

/**
 * Dealo wordmark — no separate icon glyph. Two brand-green anchors (the "D"
 * and the "o") frame the ink-colored "eal", closed with a small brass full
 * stop: the numbers are settled. `brass` is otherwise reserved for
 * confirmation moments (see design-system/dealo/MASTER.md) — this is the one
 * deliberate exception, since the wordmark itself is the ultimate "trust
 * this" signal.
 */
export default function Logo({ size = 24 }) {
  return (
    <Text as="span" fontSize={`${size}px`} fontWeight={800} letterSpacing="-.02em" lineHeight={1} whiteSpace="nowrap">
      <Box as="span" color="brand">
        D
      </Box>
      <Box as="span" color="text">
        eal
      </Box>
      <Box as="span" color="brand">
        o
      </Box>
      <Box as="span" color="brass">
        .
      </Box>
    </Text>
  );
}
