import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import Card from './Card';

/**
 * Centered card with pulsing dots + a rotating reassurance message. Shared by
 * any page that waits on a real network call long enough to need one
 * (ResultsPage building routes, ProductSelectPage fetching candidates).
 */
export default function LoadingCard({ messages }) {
  const [idx, setIdx] = useState(0);
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
          <Text fontSize="14px" color="text2" fontWeight={500}>
            {messages[idx]}
          </Text>
        </Flex>
      </Card>
    </Flex>
  );
}
