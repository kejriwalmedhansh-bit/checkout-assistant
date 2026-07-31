import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import Card from './Card';
import { I } from './icons';

/**
 * Centered card with pulsing dots + a rotating tip. Shared by any page that
 * waits on a real network call long enough to need one (ResultsPage building
 * routes, ProductSelectPage fetching candidates). No separate "Finding the
 * best price... / Almost there..." status line — the dots alone carry
 * "something is happening," freeing the text for something worth reading:
 * Dealo's core trust gap is that gift vouchers are an unfamiliar concept
 * (see PRODUCT.md), so this dead time is spent on that instead of restating
 * the obvious. Tips loop (unlike the old status line, which froze on its
 * last message) since there's no "final" tip to land on.
 */
export default function LoadingCard({ tips }) {
  const [idx, setIdx] = useState(0);
  const prefersReduced = useReducedMotion();
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % tips.length), 5000);
    return () => clearInterval(t);
  }, [tips]);

  const tip = tips[idx];

  return (
    <Flex justify="center" pt={{ base: '32px', md: '64px' }}>
      <Card p={{ base: '28px 20px', md: '36px 40px' }} maxW="360px" w="100%">
        <Flex direction="column" align="center" gap="18px">
          <Flex gap="8px">
            {[0, 1, 2].map((i) => (
              <Box
                key={i}
                w="10px"
                h="10px"
                borderRadius="50%"
                bg="brand"
                sx={{
                  animation: 'dealoPulse 1.2s ease-in-out infinite',
                  animationDelay: `${i * 0.2}s`,
                  '@keyframes dealoPulse': {
                    '0%, 100%': { opacity: 0.35, transform: 'scale(1)' },
                    '50%': { opacity: 1, transform: 'scale(1.3)' },
                  },
                }}
              />
            ))}
          </Flex>
          <Flex
            gap="8px"
            align="flex-start"
            bg="brandSoft"
            borderRadius="xs"
            px="12px"
            py="10px"
            w="100%"
          >
            <Flex color="brand" flex="0 0 auto" mt="1px">
              <I.bulb size={15} />
            </Flex>
            <Box position="relative" flex="1">
              {prefersReduced ? (
                <Text fontSize="12.5px" color="text" lineHeight={1.5}>
                  {tip}
                </Text>
              ) : (
                <AnimatePresence mode="wait">
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <Text fontSize="12.5px" color="text" lineHeight={1.5}>
                      {tip}
                    </Text>
                  </motion.div>
                </AnimatePresence>
              )}
            </Box>
          </Flex>
        </Flex>
      </Card>
    </Flex>
  );
}
