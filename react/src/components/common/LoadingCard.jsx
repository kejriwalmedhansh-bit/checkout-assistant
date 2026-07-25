import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import Card from './Card';

/**
 * Centered card with pulsing dots + a rotating reassurance message. Shared by
 * any page that waits on a real network call long enough to need one
 * (ResultsPage building routes, ProductSelectPage fetching candidates). The
 * message crossfades between lines instead of jump-cutting — small, but it's
 * the one piece of this card that changes every few seconds without saying so.
 */
export default function LoadingCard({ messages }) {
  const [idx, setIdx] = useState(0);
  const prefersReduced = useReducedMotion();
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => Math.min(i + 1, messages.length - 1)), 3000);
    return () => clearInterval(t);
  }, [messages]);

  return (
    <Flex justify="center" pt={{ base: '32px', md: '64px' }}>
      <Card p="40px 48px" maxW="360px" w="100%">
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
          <Box position="relative" minH="20px" w="100%" textAlign="center">
            {prefersReduced ? (
              <Text fontSize="14px" color="text2" fontWeight={500}>
                {messages[idx]}
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
                  <Text fontSize="14px" color="text2" fontWeight={500}>
                    {messages[idx]}
                  </Text>
                </motion.div>
              </AnimatePresence>
            )}
          </Box>
        </Flex>
      </Card>
    </Flex>
  );
}
