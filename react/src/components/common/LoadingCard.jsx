import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import { EASE_OUT, EASE_IN_OUT_CSS } from '@/theme/motion';
import Card from './Card';
import { I } from './icons';

/**
 * Waiting state for any page blocked on a real network call (ResultsPage
 * building routes, ProductSelectPage fetching candidates).
 *
 * Instead of bouncing dots, it shows the outline of what's about to arrive —
 * a faint preview of the product list or of the savings + steps — with one
 * slow light sweep across it. That tells the user "your answer is being put
 * together, and it will look like this", and the real content lands in the
 * same place without a jump.
 *
 * Above it, a rotating tip (first, so it's on screen even on short phones). Dealo's core trust gap is that gift vouchers
 * are an unfamiliar concept (see PRODUCT.md), so this dead time is spent on
 * that. Tips loop since there's no "final" tip to land on.
 *
 * @param {string[]} tips
 * @param {'routes'|'products'} variant  which page's outline to preview
 */
export default function LoadingCard({ tips, variant = 'routes' }) {
  const [idx, setIdx] = useState(0);
  const prefersReduced = useReducedMotion();
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % tips.length), 5000);
    return () => clearInterval(t);
  }, [tips]);

  const tip = tips[idx];

  return (
    <Flex justify="center" pt={{ base: '8px', md: '40px' }} w="100%">
      <Box w="100%" maxW="440px" role="status" aria-live="polite" aria-label="Finding the best price">
        <Flex mb="14px" gap="10px" align="flex-start" bg="brandSoft" borderRadius="sm" px="14px" py="12px" minH="64px">
          <Flex color="brand" flex="0 0 auto" mt="2px">
            <I.bulb size={16} />
          </Flex>
          <Box position="relative" flex="1" minW={0}>
            {prefersReduced ? (
              <Text fontSize="13.5px" color="text" lineHeight={1.5}>
                {tip}
              </Text>
            ) : (
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, transform: 'translateY(4px)', filter: 'blur(2px)' }}
                  animate={{ opacity: 1, transform: 'translateY(0px)', filter: 'blur(0px)' }}
                  exit={{ opacity: 0, transform: 'translateY(-4px)', filter: 'blur(2px)' }}
                  transition={{ duration: 0.3, ease: EASE_OUT }}
                >
                  <Text fontSize="13.5px" color="text" lineHeight={1.5}>
                    {tip}
                  </Text>
                </motion.div>
              </AnimatePresence>
            )}
          </Box>
        </Flex>
        <Shimmer animated={!prefersReduced}>{variant === 'products' ? <ProductsOutline /> : <RoutesOutline />}</Shimmer>
      </Box>
    </Flex>
  );
}

/** One slow band of light passing over the outline. Moves with transform only. */
function Shimmer({ animated, children }) {
  return (
    <Box
      position="relative"
      overflow="hidden"
      borderRadius="md"
      sx={
        animated
          ? {
              '&::after': {
                content: '""',
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none',
                background: 'linear-gradient(100deg, transparent 20%, rgba(255,255,255,.65) 50%, transparent 80%)',
                transform: 'translateX(-100%)',
                animation: `dealoShimmer 1.8s ${EASE_IN_OUT_CSS} infinite`,
              },
              '@keyframes dealoShimmer': {
                '0%': { transform: 'translateX(-100%)' },
                '70%, 100%': { transform: 'translateX(100%)' },
              },
            }
          : undefined
      }
    >
      {children}
    </Box>
  );
}

function Bar({ w, h = '10px', bg = 'surface3', ...rest }) {
  return <Box w={w} h={h} bg={bg} borderRadius="99px" {...rest} />;
}

/** The results page, in outline: product, savings band, first step. */
function RoutesOutline() {
  return (
    <Flex direction="column" gap="10px">
      <Card p="14px" display="flex" alignItems="center" gap="12px" boxShadow="none">
        <Box w="44px" h="44px" flex="0 0 44px" borderRadius="10px" bg="surface3" />
        <Flex direction="column" gap="8px" flex="1">
          <Bar w="70%" h="12px" />
          <Bar w="40%" />
        </Flex>
      </Card>
      <Box bg="greenSoft" border="1px solid" borderColor="border" borderRadius="md" p="16px">
        <Flex align="center" gap="14px">
          <Box w="40px" h="40px" flex="0 0 40px" borderRadius="50%" bg="rgba(31,122,82,.14)" />
          <Flex direction="column" gap="8px" flex="1">
            <Bar w="30%" bg="rgba(31,122,82,.14)" />
            <Bar w="55%" h="18px" bg="rgba(31,122,82,.14)" />
          </Flex>
        </Flex>
      </Box>
      <Card p="18px" boxShadow="none">
        <Flex direction="column" align="center" gap="10px">
          <Box w="30px" h="30px" borderRadius="50%" bg="surface3" />
          <Bar w="50%" h="14px" />
          <Bar w="35%" />
          <Box w="100%" h="44px" mt="8px" borderRadius="sm" bg="surface3" />
        </Flex>
      </Card>
    </Flex>
  );
}

/** The product list, in outline: three rows. */
function ProductsOutline() {
  return (
    <Flex direction="column" gap="10px">
      {[0, 1, 2].map((i) => (
        <Card key={i} p="14px" display="flex" alignItems="center" gap="12px" boxShadow="none">
          <Box w="56px" h="56px" flex="0 0 56px" borderRadius="10px" bg="surface3" />
          <Flex direction="column" gap="8px" flex="1" minW={0}>
            <Bar w={['80%', '65%', '72%'][i]} h="12px" />
            <Bar w="45%" />
          </Flex>
          <Bar w="56px" h="28px" flex="0 0 56px" borderRadius="8px" />
        </Card>
      ))}
    </Flex>
  );
}
