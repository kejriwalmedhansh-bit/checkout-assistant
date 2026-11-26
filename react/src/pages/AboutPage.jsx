import { Box, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import { usePageTitle } from '@/hooks/usePageTitle';
import { PAGE_META } from '@/seo/pageMeta';
import { ROUTES } from '@/routes/paths';

function Section({ title, children }) {
  return (
    <Box mb="26px">
      <Text as="h2" m="0 0 8px" fontSize="16px" fontWeight={800} letterSpacing="-.01em">
        {title}
      </Text>
      <Text as="div" fontSize="14px" color="text2" lineHeight={1.65}>
        {children}
      </Text>
    </Box>
  );
}

export default function AboutPage() {
  usePageTitle(PAGE_META.about.title, PAGE_META.about.description);

  return (
    <InfoPageShell title="About Dealo" subtitle="The cheapest way to pay at the shop you already use.">
      <Section title="What Dealo does">
        Type a shop or a product, or paste a product link, and Dealo shows the cheapest way to pay for it. Most
        often that is the shop’s own <b>gift card</b>, bought for less than its value. You pay the shop with the
        gift card code, like store credit, and keep the difference. You still buy from the real shop, on its own
        website or app.
      </Section>

      <Section title="Why a gift card costs less">
        Shops sell their gift cards through official issuers at a discount, because it brings them money up front.
        A ₹1,000 card can cost ₹900 to ₹980 depending on the shop. Dealo reads these prices for 800+ Indian shops
        and shows today’s figure with the date it was checked. Cashback is never counted as a saving, because it
        may or may not arrive later.
      </Section>

      <Section title="Where the gift cards come from">
        Dealo sells many gift cards itself. They are issued through Hubble, an official gift voucher issuer: you
        pay from your bank app and the code arrives in seconds. For other shops Dealo points you to Gyftr, Maximize
        or BuyHatke, which are official gift voucher sellers, and shows their prices side by side.
      </Section>

      <Section title="How Dealo stays free">
        Dealo is free to use and needs no login to search. When you click through to a shop, that link may be an
        affiliate link, so the shop may pay Dealo a small commission if you buy. It never changes the price you
        pay, and it never changes which option Dealo shows first: the lowest price always comes first.
      </Section>

      <Section title="What Dealo never asks for">
        Dealo never asks for your card number, UPI PIN or bank OTP. Payments for gift cards sold by Dealo happen
        in your own bank app.
      </Section>

      <Section title="Who runs it">
        Dealo is built in India by Medhansh Kejriwal. Questions, a wrong price or a code that is not working:{' '}
        <ChakraLink as={RouterLink} to={ROUTES.contact} fontWeight={700} textDecoration="underline" textUnderlineOffset="2px">
          contact us
        </ChakraLink>
        .
      </Section>

      <Flex align="center" gap="10px" p="14px 16px" borderRadius="14px" bg="brandSoft" mt="8px">
        <Box color="brand" flex="0 0 auto">
          <I.check size={16} />
        </Box>
        <Text m={0} fontSize="12.5px" color="brandText" lineHeight={1.55}>
          Curious how a search actually works, step by step?{' '}
          <ChakraLink as={RouterLink} to={ROUTES.howItWorks} fontWeight={700} textDecoration="underline" textUnderlineOffset="2px">
            See how it works
          </ChakraLink>
          .
        </Text>
      </Flex>
    </InfoPageShell>
  );
}
