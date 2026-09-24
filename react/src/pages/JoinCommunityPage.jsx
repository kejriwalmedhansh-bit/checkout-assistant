import { useEffect, useMemo } from 'react';
import { Box, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink, useLocation } from 'react-router-dom';

import BackButton from '@/components/common/BackButton';
import { I } from '@/components/common/icons';
import { usePageHeader } from '@/hooks/usePageHeader';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { registerCampaignProps, track } from '@/utils/analytics';
import { WHATSAPP_COMMUNITY_LINK } from '@/config';

const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];

function IconBubble({ icon, accent }) {
  return (
    <Flex
      w="60px"
      h="60px"
      align="center"
      justify="center"
      borderRadius="18px"
      bg={accent ? 'brandSoft' : 'surface2'}
      color={accent ? 'brand' : 'text2'}
      border="1px solid"
      borderColor={accent ? 'brandSoft' : 'border'}
    >
      {icon}
    </Flex>
  );
}

/**
 * Landing spot for the "join the WhatsApp community" campaign link. Almost no
 * copy on purpose: someone who opened this off a cold email has zero patience
 * for a paragraph, the icon row alone (cart → cheapest way to pay) has to
 * carry the pitch. Deliberately not an auto-redirect — see the button's
 * onClick comment for why a real click is required before navigating out.
 */
export default function JoinCommunityPage() {
  usePageTitle('Join the community', "Send Dealo's founder whatever you're about to buy — free, no catch.");

  const backControl = <BackButton fallback={ROUTES.home} iconOnly />;
  usePageHeader({ left: backControl });

  const location = useLocation();
  const utm = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const out = {};
    for (const key of UTM_KEYS) {
      const val = params.get(key);
      if (val) out[key] = val;
    }
    return out;
  }, [location.search]);

  useEffect(() => {
    track('Join Page Viewed', utm);
    // So the campaign tag survives onto whatever they do next (search, view
    // a deal, click buy) — not just this landing event.
    registerCampaignProps(utm);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(utm)]);

  return (
    <Box textAlign="center" maxW="380px" mx="auto" pt={{ base: '8vh', md: '12vh' }}>
      <Flex display={{ base: 'none', lg: 'flex' }} mb="24px">
        {backControl}
      </Flex>

      <Flex align="center" justify="center" gap="10px" mb="20px">
        <IconBubble icon={<I.cart size={26} />} />
        <I.arrowRight size={18} color="var(--chakra-colors-text3)" />
        <IconBubble icon={<I.pay size={26} />} accent />
      </Flex>

      <Text as="h1" m="0 0 28px" fontSize="20px" fontWeight={800} letterSpacing="-.02em">
        Send it. We find the price.
      </Text>

      <ChakraLink
        href={WHATSAPP_COMMUNITY_LINK}
        isExternal
        // A click is required, not an auto-redirect — an email client's own
        // link scanner (Gmail, Outlook Safe Links) fetches this page before a
        // person ever sees it; a JS redirect on load would send that scanner,
        // not the recipient, into the WhatsApp invite.
        onClick={() => track('Joined WhatsApp Clicked', utm)}
        display="flex"
        alignItems="center"
        justifyContent="center"
        gap="10px"
        w="100%"
        h="52px"
        px="16px"
        borderRadius="16px"
        bg="brand"
        color="white"
        fontSize="14px"
        fontWeight={700}
        whiteSpace="nowrap"
        _hover={{ textDecoration: 'none', opacity: 0.92 }}
      >
        <I.external size={17} />
        Join our WhatsApp community
      </ChakraLink>

      <Text m="18px 0 0" fontSize="15px" fontWeight={600} color="text2">
        or{' '}
        <ChakraLink
          as={RouterLink}
          to={ROUTES.home}
          onClick={() => track('Try It Yourself Clicked', utm)}
          color="text2"
          _hover={{ color: 'brand', textDecoration: 'underline' }}
        >
          try it yourself →
        </ChakraLink>
      </Text>

      <Box mt="36px">
        <Text m="0 0 10px" fontSize="12.5px" fontWeight={600} color="text3">
          or scan this QR code
        </Text>
        <Box
          as="img"
          src="/whatsapp-community-qr.png"
          alt="QR code to join Dealo's WhatsApp community"
          w="150px"
          h="150px"
          mx="auto"
          borderRadius="14px"
          border="1px solid"
          borderColor="border"
        />
      </Box>
    </Box>
  );
}
