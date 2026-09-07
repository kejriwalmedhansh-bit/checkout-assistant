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
      borderRadius="18px"
      boxShadow="0 1px 2px rgba(22,32,43,.06), 0 24px 52px -20px rgba(22,32,43,.34)"
      p={{ base: '16px', md: '18px' }}
    >
      <Text m="0 0 6px" fontSize="13.5px" fontWeight={800}>
        Can we record how you use Dealo?
      </Text>
      <Text m="0 0 12px" fontSize="12.5px" color="text2" lineHeight={1.65}>
        It helps us see where people get stuck. What you type is never recorded — the search box is blanked out
        even when you say yes. Say no and we won’t record you at all.{' '}
        <ChakraLink as={RouterLink} to={ROUTES.privacy} color="brand" fontWeight={700} textDecoration="underline">
          What we collect
        </ChakraLink>
      </Text>
      <Flex gap="8px">
        <Button size="sm" flex={1} onClick={() => answer(CONSENT_GRANTED)}>
          Allow
        </Button>
        <Button size="sm" flex={1} variant="outline" onClick={() => answer(CONSENT_DENIED)}>
          No thanks
        </Button>
      </Flex>
    </Box>
  );
}
