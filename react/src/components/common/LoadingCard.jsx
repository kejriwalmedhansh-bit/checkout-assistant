import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import { EASE_OUT } from '@/theme/motion';
import Card from './Card';
import { I } from './icons';

const TIP_MS = 5000;

/**
 * Waiting state for any page blocked on a real network call (ResultsPage
 * building routes, ProductSelectPage fetching candidates).
 *
 * Instead of bouncing dots, it shows the outline of what's about to arrive —
 * a faint preview of the product list or of the savings + steps — with a
 * soft light passing left to right across every grey block. That tells the
 * user "your answer is being put together, and it will look like this", and
 * the real content lands in the same place without a jump.
 *
 * Above it, a rotating tip (first, so it's on screen even on short phones).
 * Dealo's core trust gap is that gift vouchers are an unfamiliar concept (see
 * PRODUCT.md), so this dead time is spent on that. A thin bar per tip fills
 * while each one is showing, like story progress — it says how long until
 * the next tip, and doubles as a sign that work is under way.
 *
 * @param {string[]} tips
 * @param {'routes'|'products'} variant  which page's outline to preview
 */
export default function LoadingCard({ tips, variant = 'routes' }) {
  const [idx, setIdx] = useState(0);
  const prefersReduced = useReducedMotion();
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % tips.length), TIP_MS);
    return () => clearInterval(t);
  }, [tips]);

  const tip = tips[idx];

  return (
    <Flex justify="center" pt={{ base: '4px', md: '40px' }} w="100%">
      <Box w="100%" maxW="440px" role="status" aria-live="polite" aria-label="Finding the best price">
        <Card p="14px 16px 12px" mb="12px" boxShadow="none">
          <Flex gap="12px" align="center" minH="44px">
            <Flex
              flex="0 0 36px"
              w="36px"
              h="36px"
              borderRadius="50%"
              bg="brandSoft"
              color="brand"
              align="center"
              justify="center"
            >
              <I.bulb size={17} />
            </Flex>
            <Box position="relative" flex="1" minW={0}>
              <Text
                fontSize="10.5px"
                fontWeight={700}
                letterSpacing=".08em"
                textTransform="uppercase"
                color="text3"
                mb="2px"
              >
                Good to know
              </Text>
              {prefersReduced ? (
                <TipText>{tip}</TipText>
              ) : (
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={idx}
                    initial={{ opacity: 0, transform: 'translateY(4px)', filter: 'blur(2px)' }}
                    animate={{ opacity: 1, transform: 'translateY(0px)', filter: 'blur(0px)' }}
                    exit={{ opacity: 0, transform: 'translateY(-4px)', filter: 'blur(2px)' }}
                    transition={{ duration: 0.3, ease: EASE_OUT }}
                  >
                    <TipText>{tip}</TipText>
                  </motion.div>
                </AnimatePresence>
              )}
            </Box>
          </Flex>

          <Flex gap="4px" mt="12px" aria-hidden="true">
            {tips.map((_, i) => (
              <Box key={i} flex="1" h="3px" borderRadius="99px" bg="surface3" overflow="hidden">
                <Box
                  // Remount the current bar on every tip so its fill restarts.
                  key={i === idx ? `on-${idx}` : 'off'}
                  h="100%"
                  bg="brand"
                  opacity={0.55}
                  transformOrigin="left"
                  transform={i < idx || (i === idx && prefersReduced) ? 'scaleX(1)' : 'scaleX(0)'}
                  sx={
                    i === idx && !prefersReduced
                      ? {
                          animation: `dealoTipFill ${TIP_MS}ms linear forwards`,
                          '@keyframes dealoTipFill': { to: { transform: 'scaleX(1)' } },
                        }
                      : undefined
                  }
                />
              </Box>
            ))}
          </Flex>
        </Card>

        {variant === 'products' ? <ProductsOutline /> : <RoutesOutline />}
      </Box>
    </Flex>
  );
}

function TipText({ children }) {
  return (
    <Text fontSize="14px" fontWeight={600} color="text" lineHeight={1.4}>
      {children}
    </Text>
  );
}

// Base colour and the lighter band that sweeps across it, per tone.
const TONES = {
  neutral: ['#EFEDE5', '#FAF9F5'],
  green: ['#D3E6D9', '#E9F3EC'],
};

/**
 * One grey placeholder block. A lighter band slides across it left to right,
 * on a loop. The band is sized to the screen, not the block, so every block
 * on the page moves at the same speed and the light reads as one wave
 * passing over the whole preview.
 */
function Bone({ w, h = '10px', tone = 'neutral', borderRadius = '99px', ...rest }) {
  const [base, light] = TONES[tone];
  return (
    <Box
      w={w}
      h={h}
      borderRadius={borderRadius}
      bg={base}
      sx={{
        backgroundImage: `linear-gradient(90deg, ${base} 0%, ${base} 35%, ${light} 50%, ${base} 65%, ${base} 100%)`,
        backgroundSize: '200vw 100%',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: '-150vw 0',
        animation: 'dealoBoneSweep 1.6s ease-in-out infinite',
        '@keyframes dealoBoneSweep': {
          from: { backgroundPosition: '-150vw 0' },
          to: { backgroundPosition: '0vw 0' },
        },
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }}
      {...rest}
    />
  );
}

/** The results page, in outline: product, savings band, first step. */
function RoutesOutline() {
  return (
    <Flex direction="column" gap="10px">
      <Card p="14px" display="flex" alignItems="center" gap="12px" boxShadow="none">
        <Bone w="44px" h="44px" flex="0 0 44px" borderRadius="10px" />
        <Flex direction="column" gap="8px" flex="1">
          <Bone w="70%" h="12px" />
          <Bone w="40%" />
        </Flex>
      </Card>
      <Box bg="greenSoft" border="1px solid" borderColor="border" borderRadius="md" p="16px">
        <Flex align="center" gap="14px">
          <Bone w="40px" h="40px" flex="0 0 40px" borderRadius="50%" tone="green" />
          <Flex direction="column" gap="8px" flex="1">
            <Bone w="30%" tone="green" />
            <Bone w="55%" h="18px" tone="green" />
          </Flex>
        </Flex>
      </Box>
      <Card p="18px" boxShadow="none">
        <Flex direction="column" align="center" gap="10px">
          <Bone w="30px" h="30px" borderRadius="50%" />
          <Bone w="50%" h="14px" />
          <Bone w="35%" />
          <Bone w="100%" h="44px" mt="8px" borderRadius="12px" />
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
          <Bone w="56px" h="56px" flex="0 0 56px" borderRadius="10px" />
          <Flex direction="column" gap="8px" flex="1" minW={0}>
            <Bone w={['80%', '65%', '72%'][i]} h="12px" />
            <Bone w="45%" />
          </Flex>
          <Bone w="56px" h="28px" flex="0 0 56px" borderRadius="8px" />
        </Card>
      ))}
    </Flex>
  );
}
