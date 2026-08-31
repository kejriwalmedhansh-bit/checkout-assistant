import { Box, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';

import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import { usePageTitle } from '@/hooks/usePageTitle';
import { track } from '@/utils/analytics';

const WHATSAPP_NUMBER = '919874400045';
const SUPPORT_EMAIL = 'medhansh@getdealo.in';

function ContactRow({ icon, label, value, href, isExternal, onClick }) {
  return (
    <ChakraLink
      href={href}
      isExternal={isExternal}
      onClick={onClick}
      display="flex"
      alignItems="center"
      gap="14px"
      p="16px"
      borderRadius="16px"
      border="1px solid"
      borderColor="border"
      bg="surface2"
      _hover={{ textDecoration: 'none', borderColor: 'borderStrong', bg: 'surface3' }}
    >
      <Flex w="40px" h="40px" flex="0 0 auto" align="center" justify="center" borderRadius="12px" bg="brandSoft" color="brand">
        {icon}
      </Flex>
      <Box>
        <Text m={0} fontSize="13px" fontWeight={700}>
          {label}
        </Text>
        <Text m={0} fontSize="13px" color="text2">
          {value}
        </Text>
      </Box>
    </ChakraLink>
  );
}

export default function ContactPage() {
  usePageTitle('Contact', 'Reach the Dealo team by WhatsApp or email — search support, feedback, and questions about how Gift Voucher deals work.');

  const whatsappHref = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent("Hi! I have a question about Dealo.")}`;

  return (
    <InfoPageShell title="Contact" subtitle="Have a question, found a bug, or want to talk to us? Here's how to reach Dealo.">
      <Flex direction="column" gap="10px" mb="20px">
        <ContactRow
          icon={<I.external size={17} />}
          label="Chat on WhatsApp"
          value="Search and get answers right in chat"
          href={whatsappHref}
          isExternal
          onClick={() => track('Clicked WhatsApp Button', { source: 'contact_page' })}
        />
        <ContactRow
          icon={<I.external size={17} />}
          label="Email support"
          value={SUPPORT_EMAIL}
          href={`mailto:${SUPPORT_EMAIL}`}
        />
      </Flex>

      <Text fontSize="12.5px" color="text3" lineHeight={1.6}>
        There's no separate phone support line yet — the fastest way to reach us is WhatsApp or email above.
      </Text>
    </InfoPageShell>
  );
}
