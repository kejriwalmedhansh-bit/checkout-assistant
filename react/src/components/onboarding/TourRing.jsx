import { Box } from '@chakra-ui/react';
import { useReducedMotion } from 'framer-motion';

const PAD = '8px';

/**
 * The tour's pulsing highlight ring. Rendered locally, inside a
 * `position: relative` wrapper around the real target (see
 * useTourHighlight.js for why) — pure CSS `position: absolute; inset` is
 * laid out by the browser relative to that wrapper, so it's always
 * correctly positioned regardless of viewport quirks, and is naturally
 * covered by anything with a higher stacking context (e.g. a modal opened
 * on top) with no special-casing needed.
 */
export default function TourRing() {
  const prefersReduced = useReducedMotion();
  return (
    <Box
      position="absolute"
      inset={`-${PAD}`}
      pointerEvents="none"
      borderRadius="inherit"
      border="2px solid"
      borderColor="brass"
      sx={{
        '@keyframes dealoSpotlightPulse': {
          '0%, 100%': { boxShadow: '0 0 0 0px var(--chakra-colors-brass)' },
          '50%': { boxShadow: '0 0 0 5px transparent' },
        },
        animation: prefersReduced ? 'none' : 'dealoSpotlightPulse 1.8s ease-in-out infinite',
      }}
    />
  );
}
