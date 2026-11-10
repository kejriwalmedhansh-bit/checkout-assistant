import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';
import { fmt } from '@/utils/format';

// Tagged so Mixpanel can count visits that came from a friend's share.
const SHARE_URL = 'https://getdealo.in/?utm_source=whatsapp&utm_medium=share';

/** The text a friend receives. Leads with the rupee number, never a %. */
function shareText({ shop, original, pay, product, giftCard }) {
  if (giftCard) {
    return `${shop} gift cards are cheaper on Dealo: a ${fmt(original)} card costs ${fmt(pay)}. Pay with it at checkout 👇\n${SHARE_URL}`;
  }
  const where = shop ? ` at ${shop}` : '';
  const what = product ? ` for ${product}` : '';
  if (original && pay && original > pay) {
    return `I'm paying ${fmt(pay)} instead of ${fmt(original)}${where}${what} 🤯\nCheck the cheapest way to pay at your shop 👇\n${SHARE_URL}`;
  }
  return `Found the cheapest price${what}: ${fmt(pay)}${where}.\nCheck yours before you buy 👇\n${SHARE_URL}`;
}

/**
 * "Tell a friend": sends this result to any chat, so every saving can bring
 * in the next shopper (unlike "Send this to my WhatsApp", which only goes to
 * the visitor's own chat with the Dealo bot).
 *
 * `giftCard`: the shop-name screen, where there's no cart yet, so the
 * message gives a ₹1,000 example instead of "I'm paying".
 *
 * Phones open their own share sheet (WhatsApp, Instagram, SMS...); desktops
 * fall back to WhatsApp Web with the text filled in.
 */
export default function ShareSaving({ shop, original, pay, product, view, giftCard = false }) {
  if (!pay) return null;
  const text = shareText({ shop, original, pay, product, giftCard });
  const saved = original && original > pay ? original - pay : 0;

  const onClick = async (e) => {
    track('Clicked Share Saving', { view, saving: saved });
    if (typeof navigator !== 'undefined' && navigator.share) {
      e.preventDefault();
      try {
        await navigator.share({ text });
      } catch {
        /* closed the share sheet: nothing to do */
      }
    }
  };

  return (
    <Box
      as="a"
      href={`https://wa.me/?text=${encodeURIComponent(text)}`}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      display="flex"
      alignItems="center"
      gap="12px"
      minH="56px"
      px="12px"
      py="10px"
      bg="surface"
      border="1px solid"
      borderColor="border"
      borderRadius="14px"
      color="text"
      transition="transform .16s cubic-bezier(0.23, 1, 0.32, 1)"
      _hover={{ textDecoration: 'none', borderColor: 'borderStrong' }}
      _active={{ transform: 'scale(0.98)' }}
      _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
    >
      <Flex w="36px" h="36px" flex="0 0 auto" borderRadius="full" bg="brandSoft" color="brand" align="center" justify="center">
        <Box as="svg" viewBox="0 0 24 24" w="18px" h="18px" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" />
          <path d="M12 3v12" />
          <path d="M7 8l5-5 5 5" />
        </Box>
      </Flex>
      <Box flex="1" minW={0}>
        <Text fontSize="15px" fontWeight={700} lineHeight={1.3}>
          Tell a friend
        </Text>
        <Text fontSize="12.5px" color="text2" lineHeight={1.35}>
          {giftCard ? 'Send this deal to any chat' : saved > 0 ? `Send this ${fmt(saved)} saving to any chat` : 'Send this price to any chat'}
        </Text>
      </Box>
      <Box color="text3" flex="0 0 auto" aria-hidden>
        <I.chevRight size={18} />
      </Box>
    </Box>
  );
}
