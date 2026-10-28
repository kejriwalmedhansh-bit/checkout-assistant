import { useEffect, useState } from 'react';
import { Box, Button, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import { ROUTES } from '@/routes/paths';
import { CONSENT_DENIED, CONSENT_GRANTED, hasAnswered, setConsent } from '@/utils/consent';

/**
 * Asks before recording, and takes no for an answer.
 *
 * Deliberately not a modal and not a full-width bar across the top: it sits in
 * the corner, out of the way of the search box, and the site works normally
 * whether or not it is answered. Nothing is being withheld until someone
 * clicks, so there is no reason to block the page — and a wall that has to be
 * dismissed is exactly what trains people to click the first button without
 * reading it.
 *
 * Both buttons carry the same visual weight. Making "Allow" the loud one and
 * "No thanks" a grey whisper is the standard trick, and it is the reason
 * nobody trusts these banners. The whole value of asking is lost if the answer
 * is engineered.
 */
export default function ConsentBanner() {
  // Read once on mount rather than during render: the answer lives in
  // localStorage, and reading storage while rendering makes the first paint
  // depend on something that can throw.
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!hasAnswered()) setVisible(true);
  }, []);

  if (!visible) return null;

  const answer = (value) => {
    setConsent(value);
    setVisible(false);
  };

  return (
    <Box
      role="dialog"
      aria-label="Recording permission"
      position="fixed"
      zIndex={1400}
      bottom={{ base: '12px', md: '20px' }}
      left={{ base: '12px', md: '20px' }}
      // Clear of the floating WhatsApp button, which sits bottom-right.
      right={{ base: '12px', md: 'auto' }}
      maxW={{ base: 'none', md: '380px' }}
      bg="surface"
      border="1px solid"
      borderColor="border"
      borderRadius="16px"
      boxShadow="0 1px 2px rgba(22,32,43,.06), 0 24px 52px -20px rgba(22,32,43,.34)"
      p={{ base: '16px', md: '18px' }}
    >
      {/* Short on purpose (owner pick 2026-10-26): the four-line version was
          ignored by ~86% of visitors. The full detail lives behind "Details".
          Don't promise "never what you type" here — search words are recorded
          for everyone (see ANONYMOUS_SEARCH_PROPS in analytics.js). */}
      <Flex gap="12px" align="center" mb="12px">
        <Flex
          w="40px"
          h="40px"
          flex="0 0 auto"
          borderRadius="full"
          bg="brassSoft"
          align="center"
          justify="center"
          aria-hidden="true"
        >
          <Box
            as="svg"
            viewBox="0 0 24 24"
            w="22px"
            h="22px"
            fill="none"
            stroke="#8A4A17"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14.7 6.3a4 4 0 00-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 005.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z" />
          </Box>
        </Flex>
        <Box>
          <Text m="0" fontSize="15px" fontWeight={800}>
            Help us fix what’s confusing?
          </Text>
          <Text m="2px 0 0" fontSize="13px" color="text2" lineHeight={1.45}>
            We’re a small team. We never see your name.{' '}
            <ChakraLink as={RouterLink} to={ROUTES.privacy} color="brand" fontWeight={700} textDecoration="underline">
              Details
            </ChakraLink>
          </Text>
        </Box>
      </Flex>
      {/* Equal weight, kept from before: the answer only means something if
          it isn't engineered. 44px tall for thumbs on a phone. */}
      <Flex gap="8px">
        <Button h="44px" flex={1} onClick={() => answer(CONSENT_GRANTED)}>
          Sure
        </Button>
        <Button h="44px" flex={1} variant="outline" onClick={() => answer(CONSENT_DENIED)}>
          No
        </Button>
      </Flex>
    </Box>
  );
}
