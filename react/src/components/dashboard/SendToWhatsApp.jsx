import { Box, Flex, Link, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';
import { botWhatsAppHref } from '@/utils/whatsappLink';

/**
 * "Send this to my WhatsApp" row, right under the result.
 *
 * Why it exists: people who use Dealo on WhatsApp come back (about 1 in 5,
 * Aug–Oct 2026); website visitors almost never do — nothing reminds them
 * Dealo exists the next time they shop. This opens WhatsApp with the
 * product already typed, so the bot's first reply is this same price list
 * and Dealo then sits in their chat list.
 *
 * `message` is what gets pre-filled: the link they pasted, or the product
 * name. The bot treats it like any other search, so a first-time phone
 * gets the welcome message and then the prices.
 */
export default function SendToWhatsApp({ message, view }) {
  return (
    <Link
      href={botWhatsAppHref(message)}
      data-wa-message={message}
      isExternal
      onClick={() => track('Clicked Send To WhatsApp', { view })}
      display="flex"
      alignItems="center"
      gap="12px"
      minH="56px"
      px="12px"
      py="10px"
      bg="greenSoft"
      border="1px solid"
      borderColor="#A8D9BC"
      borderRadius="14px"
      color="text"
      transition="transform .16s cubic-bezier(0.23, 1, 0.32, 1)"
      _hover={{ textDecoration: 'none' }}
      _active={{ transform: 'scale(0.98)' }}
      _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
    >
      {/* WhatsApp's own green, like the other WhatsApp buttons on the site:
          it should read as "this opens WhatsApp" at a glance. */}
      <Flex w="36px" h="36px" flex="0 0 auto" borderRadius="full" bg="#25D366" align="center" justify="center">
        <Box as="svg" viewBox="0 0 32 32" w="20px" h="20px" fill="#fff" aria-hidden="true">
          <path d="M16 3C9.1 3 3.5 8.6 3.5 15.5c0 2.4.7 4.7 1.9 6.7L3 29l7-1.9c1.9 1.1 4 1.6 6 1.6 6.9 0 12.5-5.6 12.5-12.5S22.9 3 16 3zm0 2c5.8 0 10.5 4.7 10.5 10.5S21.8 26 16 26c-1.9 0-3.7-.5-5.3-1.5l-.4-.2-4.2 1.1 1.1-4.1-.2-.4c-1.1-1.7-1.6-3.6-1.6-5.6C5.5 9.7 10.2 5 16 5z" />
          <path d="M12.2 10.4c-.3-.6-.5-.6-.8-.6h-.6c-.2 0-.6.1-.9.4-.3.3-1.2 1.1-1.2 2.8s1.2 3.2 1.4 3.5c.2.3 2.4 3.9 5.9 5.3 2.9 1.2 3.5 1 4.1.9.6-.1 2-.8 2.2-1.6.3-.8.3-1.5.2-1.6-.1-.2-.3-.3-.6-.4-.3-.2-2-1-2.3-1.1-.3-.1-.5-.2-.7.2-.2.3-.8 1-1 1.3-.2.2-.4.2-.7.1-.3-.2-1.3-.5-2.5-1.6-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.2.3-.4.5-.6.1-.2.2-.3.3-.5.1-.2 0-.4 0-.6-.1-.2-.7-1.9-1-2.6z" />
        </Box>
      </Flex>
      <Box flex="1" minW={0}>
        <Text fontSize="15px" fontWeight={700} lineHeight={1.3}>
          Send this to my WhatsApp
        </Text>
        <Text fontSize="12.5px" color="text2" lineHeight={1.35}>
          Check the price again anytime
        </Text>
      </Box>
      <Box color="green" flex="0 0 auto" aria-hidden>
        <I.chevRight size={18} />
      </Box>
    </Link>
  );
}
