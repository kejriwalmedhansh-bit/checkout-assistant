import { useState } from 'react';
import { Box } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';

import { EASE_OUT } from '@/theme/motion';

/**
 * A plain credit card peeking up from behind the tile directly below it —
 * the "there's something here for card users" cue. Used twice on purpose,
 * the same way both times: on the homepage as a teaser, and on the results
 * page over "Have a credit card?", so people recognise the thing the
 * homepage told them to look out for.
 *
 * No bank or network logo, so it stands for any card. It rises once when it
 * scrolls into view, a soft shine crosses it three times, then it rests.
 * Render it immediately above the tile it tucks behind; the tile needs
 * `position="relative"` so it sits on top of the card's lower half.
 */
export default function PeekCard({ height = 58 }) {
  const prefersReduced = useReducedMotion();
  // The shine waits for the card to be seen — on the results page it sits
  // below the fold, and would otherwise finish before anyone scrolled there.
  const [seen, setSeen] = useState(false);

  return (
    // The strip, not the card, watches for being on screen: the card starts
    // almost fully tucked away, so it would never count as "seen" itself.
    <Box
      as={motion.div}
      initial={prefersReduced ? false : 'tucked'}
      whileInView="up"
      viewport={{ once: true, amount: 0.5 }}
      onViewportEnter={() => setSeen(true)}
      position="relative"
      h={`${height}px`}
      overflow="hidden"
      aria-hidden="true"
      pointerEvents="none"
    >
      <Box
        as={motion.div}
        // Timing lives inside the variant: on a Chakra Box, a `transition`
        // prop is read as CSS and never reaches the animation.
        variants={{ tucked: { y: 44 }, up: { y: 0, transition: { duration: 0.9, ease: EASE_OUT } } }}
        position="absolute"
        left="50%"
        top="10px"
        ml="-82px"
        w="164px"
        h="102px"
        borderRadius="11px"
        overflow="hidden"
        bgImage="linear-gradient(140deg, #27466f 0%, var(--chakra-colors-brand) 45%, #12243b 100%)"
        boxShadow="0 -8px 22px -12px rgba(18,36,59,.7), inset 0 0 0 1px rgba(255,255,255,.08)"
      >
        {/* "CREDIT" label */}
        <Box position="absolute" left="15px" top="10px" fontSize="8px" letterSpacing=".18em" fontWeight={700} color="rgba(255,255,255,.7)">
          CREDIT
        </Box>
        {/* chip */}
        <Box
          position="absolute"
          left="15px"
          top="28px"
          w="24px"
          h="18px"
          borderRadius="4px"
          bgImage="linear-gradient(135deg, #f3dc9c, #c7a14d)"
          sx={{
            '&::before': {
              content: '""',
              position: 'absolute',
              left: '8px',
              top: 0,
              bottom: 0,
              width: '1px',
              background: 'rgba(0,0,0,.18)',
              boxShadow: '8px 0 0 rgba(0,0,0,.18)',
            },
          }}
        />
        {/* tap-to-pay waves */}
        <Box as="svg" position="absolute" left="45px" top="30px" width="12px" height="14px" viewBox="0 0 12 14" fill="none">
          <path d="M2 4.5c1.2 1.4 1.2 3.6 0 5M5 2.5c2.3 2.6 2.3 6.4 0 9M8 1c3.2 3.4 3.2 8.6 0 12" stroke="rgba(255,255,255,.6)" strokeWidth="1.4" strokeLinecap="round" />
        </Box>
        {/* two plain rings, no brand */}
        <Box position="absolute" right="13px" top="11px" w="28px" h="17px">
          <Box position="absolute" left={0} top={0} w="17px" h="17px" borderRadius="50%" border="1.5px solid rgba(255,255,255,.55)" />
          <Box position="absolute" left="10px" top={0} w="17px" h="17px" borderRadius="50%" border="1.5px solid rgba(255,255,255,.55)" />
        </Box>
        {/* shine: crosses three times, then rests */}
        <Box
          position="absolute"
          top="-40%"
          bottom="-40%"
          left="-60%"
          w="40%"
          bgImage="linear-gradient(90deg, transparent, rgba(255,255,255,.22), transparent)"
          transform="skewX(-18deg)"
          sx={{
            '@keyframes dealoCardSheen': { '0%': { left: '-60%' }, '40%, 100%': { left: '130%' } },
            animation: seen ? 'dealoCardSheen 3.2s 1s 3 both' : 'none',
            '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
          }}
        />
      </Box>
    </Box>
  );
}
