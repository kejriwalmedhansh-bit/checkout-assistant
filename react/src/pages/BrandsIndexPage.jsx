import { Box, Flex, Grid, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import { BRAND_DEALS } from '@/data/brandDeals';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';

function BrandCard({ brand }) {
  return (
    <ChakraLink
      as={RouterLink}
      to={ROUTES.brandFor(brand.slug)}
      display="flex"
      flexDirection="column"
      gap="8px"
      p="18px"
      borderRadius="18px"
      border="1px solid"
      borderColor="border"
      bg="surface2"
      _hover={{ textDecoration: 'none', borderColor: 'borderStrong', bg: 'surface3' }}
    >
      <Flex align="center" justify="space-between">
        <Text m={0} fontSize="15px" fontWeight={800}>
          {brand.name}
        </Text>
        <Flex align="center" gap="4px" px="9px" py="3px" borderRadius="99px" bg="brandSoft" color="brandText" fontSize="11.5px" fontWeight={700}>
          <I.zap size={11} />
          {brand.ratePct}% off
        </Flex>
      </Flex>
      <Text m={0} fontSize="12.5px" color="text2" lineHeight={1.5}>
        {brand.tagline}
      </Text>
    </ChakraLink>
  );
}

export default function BrandsIndexPage() {
  usePageTitle(
    'Gift Voucher deals by store',
    'Compare Gift Voucher discount rates for Amazon, Flipkart, Myntra, Croma, Reliance Digital, AJIO and more — the cheapest legitimate way to pay at each store.'
  );

  return (
    <InfoPageShell
      title="Gift Voucher deals by store"
      subtitle="Every store below sells Gift Vouchers at a discount through its official partner — buy one, spend it like store credit, save the difference."
      maxW="920px"
    >
      <Grid templateColumns={{ base: '1fr', sm: 'repeat(2, 1fr)' }} gap="12px">
        {BRAND_DEALS.map((b) => (
          <BrandCard key={b.slug} brand={b} />
        ))}
      </Grid>

      <Box mt="24px">
        <Text fontSize="12.5px" color="text3" lineHeight={1.6}>
          Buying something from a different store? Search it on Dealo and we'll check its rate live — these pages
          cover the stores people ask about most.
        </Text>
      </Box>
    </InfoPageShell>
  );
}
