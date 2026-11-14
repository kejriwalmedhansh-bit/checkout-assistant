import { useEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { CONSENT_DENIED, CONSENT_GRANTED, hasAnswered, setConsent } from '@/utils/consent';

// When to ask (owner call, 2026-11-14). Asking the moment someone lands put a
// card over the bottom third of the phone before they had done anything, and
// 121 of 316 visitors (9–14 Nov) left without a single tap. Now the question
// waits until they have searched once (a short pause so the deal shows
// first), or until they have spent 30 seconds on the site, whichever is first.
const AFTER_SEARCH_MS = 2500;
const AFTER_IDLE_MS = 30000;

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
 * "Sure" is the solid button and sits on the right (owner call, 2026-11-14,
 * after ~86% of visitors ignored the equal-weight version). "No" is still a
 * full-size, clearly labelled button next to it, and not answering is
 * treated as no, so nothing is recorded unless someone taps "Sure".
 */
export default function ConsentBanner() {
  // Read once on mount rather than during render: the answer lives in
  // localStorage, and reading storage while rendering makes the first paint
  // depend on something that can throw.
  const [visible, setVisible] = useState(false);
  const query = useSearchStore((st) => st.query);
  // The last search is remembered between visits, so only a search made
  // during this visit (a change from what was there on arrival) counts.
  const queryOnArrival = useRef(query);

  useEffect(() => {
    if (hasAnswered()) return undefined;
    const t = setTimeout(() => setVisible(true), AFTER_IDLE_MS);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!query || query === queryOnArrival.current || hasAnswered()) return undefined;
    const t = setTimeout(() => setVisible(true), AFTER_SEARCH_MS);
    return () => clearTimeout(t);
  }, [query]);

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
      // Laptop: bottom-right, just above the floating WhatsApp button. The
      // old bottom-left spot sat over the sidebar's "Your account" and
      // extension buttons. Phone: full width along the bottom, as before.
      bottom={{ base: '12px', md: '96px' }}
      left={{ base: '12px', md: 'auto' }}
      right={{ base: '12px', md: '28px' }}
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
      {/* Owner call, 2026-11-14 (mockup option B): "Sure" on the right,
          where eyes and thumbs finish, as the solid button. "No" stays a full,
          readable button of the same size, so saying no is never hidden.
          44px tall for thumbs on a phone. */}
      <Flex gap="8px">
        <Button h="44px" flex={1} variant="ghost" onClick={() => answer(CONSENT_DENIED)}>
          No
        </Button>
        <Button h="44px" flex={1} variant="primary" onClick={() => answer(CONSENT_GRANTED)}>
          Sure
        </Button>
      </Flex>
    </Box>
  );
}
