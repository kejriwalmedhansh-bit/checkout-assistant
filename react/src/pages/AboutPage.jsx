import { Box, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import { usePageTitle } from '@/hooks/usePageTitle';
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
  usePageTitle(
    'About Dealo',
    'Dealo is a pre-checkout tool that finds the cheapest legitimate way to buy something online in India, by stacking discounted Gift Vouchers with cashback cards.'
  );

  return (
    <InfoPageShell title="About Dealo" subtitle="The smartest way to buy — same product, less money out.">
      <Section title="What Dealo does">
        Paste a product link or describe what you want to buy, and Dealo checks the cheapest legitimate way to
        actually pay for it — usually a discounted <b>Gift Voucher</b> from the store's official voucher partner,
        sometimes combined with a cashback card. You still buy from the real store, on the real store's website. We
        just find the cheapest legitimate way to pay for it.
      </Section>

      <Section title="Why it works">
        Big stores sell Gift Vouchers through official partners at a small discount to encourage upfront spending.
        Buy the voucher, add it to your account as store credit, then check out normally — same store, same product,
        lower total. It's real store credit, not a workaround, and Dealo never touches your card details or your
        money at any point.
      </Section>

      <Section title="What Dealo isn't">
        Dealo is not a cashback platform, a coupon site, or a credit card company. We don't sell anything ourselves —
        we point you to the cheapest legitimate way to pay, and you complete the purchase directly with the store.
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
