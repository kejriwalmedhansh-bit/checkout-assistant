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

export default function PrivacyPage() {
  usePageTitle('Privacy Policy', 'How getdealo collects, uses, and protects your information when you use Dealo.');

  return (
    <InfoPageShell title="Privacy Policy" subtitle={`Last updated ${LAST_UPDATED}`}>
      <Section title="What we collect">
        When you use Dealo, we may collect the product links or search terms you enter, and basic usage data (like
        which pages you visit and which buttons you tap) to understand how the product is used and improve it. If
        you message us on WhatsApp or by email, we collect what you send us so we can reply.
      </Section>

      <Section title="What we don't collect">
        Dealo never asks for, and never stores, your card number, CVV, OTP, UPI PIN, or bank login details. You
        always complete payment directly on the store's own website or app — Dealo never handles your money.
      </Section>

      <Section title="How we use it">
        We use the information above to run the search, show you accurate results, respond to support requests, and
        improve Dealo over time. We don't sell your personal information to third parties.
      </Section>

      <Section title="Third parties">
        A search may link out to voucher partners and stores (e.g. our Gift Voucher partner, and the store you're
        buying from). Those sites have their own privacy policies, which we'd encourage you to check before you buy.
      </Section>

      <Section title="Contact">
        Questions about this policy? Email us at{' '}
        <Text as="a" href="mailto:medhansh@getdealo.in" color="brand" fontWeight={700} textDecoration="underline">
          medhansh@getdealo.in
        </Text>
        .
      </Section>
    </InfoPageShell>
  );
}
