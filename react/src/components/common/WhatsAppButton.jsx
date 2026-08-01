import { Box, Flex, Link, Tooltip } from '@chakra-ui/react';

import { track } from '@/utils/analytics';

// Dealo's live WhatsApp number (+91 98744 00045), in the digits-only
// international format wa.me requires — no spaces, no leading "+".
const WHATSAPP_NUMBER = '919874400045';
const DEFAULT_MESSAGE = "Hi! I'd like to try Dealo on WhatsApp.";

/** Fixed icon-slot width, matching Sidebar's NavItem so icons share one center line. */
const ICON_SLOT = 34;

/**
 * "Chat on WhatsApp" sidebar row — lives in the rail's footer group (see
 * Sidebar.jsx) instead of floating over the page on every route. Styled like
 * a NavItem (fixed icon slot, label fades on collapse) but keeps WhatsApp's
 * own green rather than the site's navy/copper: a link meant to be instantly
 * recognizable as "this opens WhatsApp" should look like WhatsApp, not blend
 * into the site's own brand color.
 */
export default function WhatsAppButton({ collapsed = false }) {
  const href = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(DEFAULT_MESSAGE)}`;

  return (
    <Tooltip label="Chat with Dealo on WhatsApp" placement="right" hasArrow openDelay={250} isDisabled={!collapsed}>
      <Link
        href={href}
        isExternal
        onClick={() => track('Clicked WhatsApp Button')}
        aria-label="Chat with Dealo on WhatsApp"
        display="flex"
        alignItems="center"
        w="100%"
        p="9px 0"
        pr="11px"
        borderRadius="11px"
        fontSize="13px"
        fontWeight={600}
        color="text2"
        _hover={{ textDecoration: 'none', bg: 'surface3', color: 'text' }}
      >
        <Flex w={`${ICON_SLOT}px`} flex="0 0 auto" justify="center" align="center">
          <Box as="svg" viewBox="0 0 32 32" w="18px" h="18px" fill="#25D366" aria-hidden="true">
            <path d="M16 3C9.1 3 3.5 8.6 3.5 15.5c0 2.4.7 4.7 1.9 6.7L3 29l7-1.9c1.9 1.1 4 1.6 6 1.6 6.9 0 12.5-5.6 12.5-12.5S22.9 3 16 3zm0 2c5.8 0 10.5 4.7 10.5 10.5S21.8 26 16 26c-1.9 0-3.7-.5-5.3-1.5l-.4-.2-4.2 1.1 1.1-4.1-.2-.4c-1.1-1.7-1.6-3.6-1.6-5.6C5.5 9.7 10.2 5 16 5z" />
            <path d="M12.2 10.4c-.3-.6-.5-.6-.8-.6h-.6c-.2 0-.6.1-.9.4-.3.3-1.2 1.1-1.2 2.8s1.2 3.2 1.4 3.5c.2.3 2.4 3.9 5.9 5.3 2.9 1.2 3.5 1 4.1.9.6-.1 2-.8 2.2-1.6.3-.8.3-1.5.2-1.6-.1-.2-.3-.3-.6-.4-.3-.2-2-1-2.3-1.1-.3-.1-.5-.2-.7.2-.2.3-.8 1-1 1.3-.2.2-.4.2-.7.1-.3-.2-1.3-.5-2.5-1.6-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.2.3-.4.5-.6.1-.2.2-.3.3-.5.1-.2 0-.4 0-.6-.1-.2-.7-1.9-1-2.6z" />
          </Box>
        </Flex>
        <Box
          as="span"
          flex={1}
          textAlign="left"
          opacity={collapsed ? 0 : 1}
          pointerEvents={collapsed ? 'none' : 'auto'}
          transition="opacity .14s ease"
          whiteSpace="nowrap"
        >
          Chat on WhatsApp
        </Box>
      </Link>
    </Tooltip>
  );
}
