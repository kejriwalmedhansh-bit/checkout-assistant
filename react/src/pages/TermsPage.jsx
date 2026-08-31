import { Box, Text } from '@chakra-ui/react';

import InfoPageShell from '@/components/common/InfoPageShell';
import { usePageTitle } from '@/hooks/usePageTitle';

const LAST_UPDATED = 'August 31, 2026';

function Section({ title, children }) {
  return (
    <Box mb="22px">
      <Text as="h2" m="0 0 8px" fontSize="15px" fontWeight={800} letterSpacing="-.01em">
        {title}
      </Text>
      <Text as="div" fontSize="13.5px" color="text2" lineHeight={1.7}>
        {children}
      </Text>
    </Box>
  );
}

export default function TermsPage() {
  usePageTitle('Terms of Use', 'The terms for using getdealo’s Dealo search and Gift Voucher recommendations.');

  return (
    <InfoPageShell title="Terms of Use" subtitle={`Last updated ${LAST_UPDATED}`}>
      <Section title="What Dealo is">
        Dealo (getdealo) is a free tool that suggests the cheapest legitimate way to buy a product — typically a
        discounted Gift Voucher, sometimes combined with a cashback card. Dealo does not sell products, vouchers, or
        cards itself; it points you to official partners and stores where you complete the purchase directly.
      </Section>

      <Section title="No guarantee of price or availability">
        Prices, discount rates, and voucher availability are checked live at the moment you search, but can change
        by the time you check out — stock, offers, and rates are set by the store or voucher partner, not by us. We
        do our best to show accurate, current information, but we can't guarantee a price shown on Dealo will still
        be available when you complete the purchase.
      </Section>

      <Section title="Your responsibility">
        You're responsible for reviewing the product, price, and terms on the store's own page before you pay, and
        for following the voucher partner's own terms when you redeem a Gift Voucher. Dealo is a recommendation
        tool, not a party to your purchase.
      </Section>

      <Section title="Acceptable use">
        Don't use Dealo to attempt fraud, to scrape or resell our results at scale, or to interfere with the
        service for other users. We may restrict access if we reasonably believe the service is being misused.
      </Section>

      <Section title="Changes to these terms">
        We may update these terms as Dealo evolves. Continuing to use Dealo after a change means you accept the
        updated terms.
      </Section>

      <Section title="Contact">
        Questions about these terms? Email us at{' '}
        <Text as="a" href="mailto:medhansh@getdealo.in" color="brand" fontWeight={700} textDecoration="underline">
          medhansh@getdealo.in
        </Text>
        .
      </Section>
    </InfoPageShell>
  );
}
