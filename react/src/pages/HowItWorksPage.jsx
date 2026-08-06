import { useState } from 'react';
import { Box, Button, Collapse, Flex, Text } from '@chakra-ui/react';

import BackButton from '@/components/common/BackButton';
import { I } from '@/components/common/icons';
import { usePageHeader } from '@/hooks/usePageHeader';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { track } from '@/utils/analytics';

const STEPS = [
  {
    icon: I.search,
    title: 'Tell us what you want',
    body: 'Paste a product link from any store, or just describe the item.',
  },
  {
    icon: I.gauge,
    title: 'We check every real price',
    body: 'Live prices across stores, plus any Gift Voucher discount available for that store — checked at that moment, never estimated.',
  },
  {
    icon: I.checkCircle,
    title: 'You get one clear recommendation',
    body: 'The lowest honest total — always possible without a credit card. A couple of backups, only if you want them.',
  },
  {
    icon: I.cart,
    title: 'You check out with the store, directly',
    body: "We send you straight to the store's own checkout. Dealo never sees your card or handles your money.",
  },
];

const FAQS = [
  {
    q: 'Why do I sometimes buy a Gift Voucher before checkout?',
    a: "It's usually the cheapest legitimate route: the store's own official voucher partner sells store credit at a discount. You buy the Gift Voucher, then spend it at checkout exactly like a gift card — same store, same product, lower total. It's real store credit, not a workaround.",
  },
  {
    q: 'Is this safe?',
    a: 'Yes. Gift Vouchers come from the store’s official partner, and Dealo never handles your money or your card details — you always pay the store directly, on the store’s own site.',
  },
  {
    q: 'Do I need a credit card?',
    a: "No. Our top recommendation never requires one. If you do have a card, we'll show you when it saves you a little more — never as a requirement.",
  },
];

function FaqItem({ q, a, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Box border="1px solid" borderColor="border" borderRadius="12px" bg="surface" overflow="hidden">
      <Button
        variant="ghost"
        w="100%"
        h="auto"
        py="12px"
        px="13px"
        justifyContent="space-between"
        borderRadius="0"
        fontSize="12.5px"
        fontWeight={700}
        textAlign="left"
        whiteSpace="normal"
        onClick={() => {
          if (!open) track('Clicked FAQ Item', { question: q });
          setOpen((v) => !v);
        }}
        rightIcon={
          <Box as="span" flex="0 0 auto" color="text3" transform={open ? 'rotate(180deg)' : 'none'} transition="transform .18s ease">
            <I.chevDown size={15} />
          </Box>
        }
      >
        {q}
      </Button>
      <Collapse in={open} animateOpacity>
        <Text m={0} px="13px" pb="13px" fontSize="12px" color="text2" lineHeight={1.6}>
          {a}
        </Text>
      </Collapse>
    </Box>
  );
}

export default function HowItWorksPage() {
  usePageTitle('How it works');

  const backControl = <BackButton fallback={ROUTES.home} iconOnly />;
  // Below `lg` this renders in AppLayout's mobile top bar instead of an
  // in-page row, matching the pattern ResultsPage uses for its own back
  // control (see usePageHeader.js).
  usePageHeader({ left: backControl });

  return (
    <Box maxW="560px" mx="auto">
      <Flex display={{ base: 'none', lg: 'flex' }} align="center" gap="6px" mb="14px">
        {backControl}
      </Flex>

      <Flex direction="column" gap="22px">
        <Box>
          <Text as="h1" m={0} fontSize={{ base: '22px', md: '26px' }} fontWeight={800} letterSpacing="-.01em">
            How Dealo works
          </Text>
          <Text m="8px 0 0" fontSize="13.5px" color="text2" lineHeight={1.6}>
            <Text as="b" color="text" fontWeight={700}>
              Dealo checks the real price of what you want to buy
            </Text>{' '}
            — across stores and against every discount actually available — and hands you the
            single cheapest, legitimate way to get it.
          </Text>
        </Box>

        <Box position="relative">
          <Box
            position="absolute"
            left="19px"
            top="20px"
            bottom="20px"
            w="1.5px"
            bg="border"
          />
          <Flex direction="column">
            {STEPS.map((s, i) => (
              <Flex key={s.title} position="relative" gap="14px" py="11px">
                <Flex
                  position="relative"
                  zIndex={1}
                  flex="0 0 auto"
                  w="40px"
                  h="40px"
                  borderRadius="999px"
                  bg="surface"
                  border="1.5px solid"
                  borderColor="brandSoft"
                  color="brand"
                  align="center"
                  justify="center"
                >
                  <s.icon size={18} />
                </Flex>
                <Box flex={1} minW={0} pt="2px">
                  <Text m="0 0 2px" fontSize="10.5px" fontWeight={600} color="brass" letterSpacing=".02em" fontFamily="mono">
                    STEP {i + 1}
                  </Text>
                  <Text m="0 0 3px" fontSize="14.5px" fontWeight={800} letterSpacing="-.005em" lineHeight={1.3}>
                    {s.title}
                  </Text>
                  <Text m={0} fontSize="12.5px" color="text2" lineHeight={1.5}>
                    {s.body}
                  </Text>
                </Box>
              </Flex>
            ))}
          </Flex>
        </Box>

        <Flex align="flex-start" gap="10px" p="12px 13px" borderRadius="12px" bg="greenSoft" border="1px solid #CFE4D8">
          <Box color="green" mt="1px" flex="0 0 auto">
            <I.check size={16} />
          </Box>
          <Text m={0} fontSize="12px" color="#1E5B41" lineHeight={1.5}>
            <Text as="b" fontWeight={700}>
              Every price shown is checked live
            </Text>{' '}
            at the moment you search — not looked up from a stale list.
          </Text>
        </Flex>

        <Box>
          <Text as="h2" m="0 0 8px" fontSize="14px" fontWeight={800} letterSpacing="-.005em">
            Questions people actually ask
          </Text>
          <Flex direction="column" gap="8px">
            {FAQS.map((f, i) => (
              <FaqItem key={f.q} q={f.q} a={f.a} defaultOpen={i === 0} />
            ))}
          </Flex>
        </Box>

        <Flex align="center" justify="center" gap="6px" fontSize="11px" color="text3">
          <I.pay size={13} />
          <Text as="span">Dealo never asks for your card number or OTP.</Text>
        </Flex>
      </Flex>
    </Box>
  );
}
