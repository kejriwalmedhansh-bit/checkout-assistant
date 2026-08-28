import { Box, Link, Tooltip } from '@chakra-ui/react';

import { track } from '@/utils/analytics';

// Dealo's live WhatsApp number (+91 98744 00045), in the digits-only
// international format wa.me requires — no spaces, no leading "+".
const WHATSAPP_NUMBER = '919874400045';
const DEFAULT_MESSAGE = "Hi! I'd like to try Dealo on WhatsApp.";

/**
 * Fixed circular WhatsApp launcher, pinned to the bottom-right corner on
 * every page (rendered once in AppLayout). Unlike the sidebar's "Chat on
 * WhatsApp" row — which is hidden behind the hamburger drawer on mobile —
 * this is always on screen without any navigation. Keeps WhatsApp's own
 * green so it reads instantly as "this opens WhatsApp", not a site action.
 */
export default function FloatingWhatsAppButton() {
  const href = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(DEFAULT_MESSAGE)}`;

  return (
    <Box position="fixed" bottom={{ base: '20px', md: '28px' }} right={{ base: '16px', md: '28px' }} zIndex={15}>
      {/* Mobile-only label: there's no hover on a phone, so the Tooltip
          below never gets a chance to show there. Absolutely positioned
          off the button's own left edge, so it floats over the page
          instead of taking up any layout space or pushing the button
          around. Desktop keeps the hover Tooltip only — this stays
          hidden there since it'd be redundant with it. */}
      <Box
        display={{ base: 'block', md: 'none' }}
        position="absolute"
        top="50%"
        right="100%"
        mr="10px"
        transform="translateY(-50%)"
        whiteSpace="nowrap"
        bg="surface"
        color="text"
        fontSize="12px"
        fontWeight={600}
        px="10px"
        py="6px"
        borderRadius="full"
        boxShadow="0 4px 12px rgba(10,12,10,.18)"
        pointerEvents="none"
      >
        Dealo works on WhatsApp too
      </Box>

      <Tooltip label="Dealo works on WhatsApp too" placement="left" hasArrow openDelay={250}>
        <Link
          href={href}
          isExternal
          onClick={() => track('Clicked Floating WhatsApp Button')}
          aria-label="Dealo works on WhatsApp too"
          display="flex"
          alignItems="center"
          justifyContent="center"
          w="52px"
          h="52px"
          borderRadius="full"
          bg="#25D366"
          boxShadow="0 6px 18px rgba(10,12,10,.28)"
          transition="transform .15s ease, box-shadow .15s ease"
          _hover={{ textDecoration: 'none', transform: 'scale(1.06)', boxShadow: '0 8px 22px rgba(10,12,10,.34)' }}
        >
          <Box as="svg" viewBox="0 0 32 32" w="28px" h="28px" fill="#fff" aria-hidden="true">
            <path d="M16 3C9.1 3 3.5 8.6 3.5 15.5c0 2.4.7 4.7 1.9 6.7L3 29l7-1.9c1.9 1.1 4 1.6 6 1.6 6.9 0 12.5-5.6 12.5-12.5S22.9 3 16 3zm0 2c5.8 0 10.5 4.7 10.5 10.5S21.8 26 16 26c-1.9 0-3.7-.5-5.3-1.5l-.4-.2-4.2 1.1 1.1-4.1-.2-.4c-1.1-1.7-1.6-3.6-1.6-5.6C5.5 9.7 10.2 5 16 5z" />
            <path d="M12.2 10.4c-.3-.6-.5-.6-.8-.6h-.6c-.2 0-.6.1-.9.4-.3.3-1.2 1.1-1.2 2.8s1.2 3.2 1.4 3.5c.2.3 2.4 3.9 5.9 5.3 2.9 1.2 3.5 1 4.1.9.6-.1 2-.8 2.2-1.6.3-.8.3-1.5.2-1.6-.1-.2-.3-.3-.6-.4-.3-.2-2-1-2.3-1.1-.3-.1-.5-.2-.7.2-.2.3-.8 1-1 1.3-.2.2-.4.2-.7.1-.3-.2-1.3-.5-2.5-1.6-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.6.1-.2.3-.4.5-.6.1-.2.2-.3.3-.5.1-.2 0-.4 0-.6-.1-.2-.7-1.9-1-2.6z" />
          </Box>
        </Link>
      </Tooltip>
    </Box>
  );
}
