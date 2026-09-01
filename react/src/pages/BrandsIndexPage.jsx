import { useMemo, useState } from 'react';
import { Box, Flex, Grid, Input, InputGroup, InputLeftElement, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import ALL_BRAND_DEALS from '@/data/allBrandDeals.json';
import { BRAND_DEALS } from '@/data/brandDeals';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { track } from '@/utils/analytics';

const SOURCE_LABEL = {
  gyftr: 'Gyftr',
  maximize: 'Maximize',
  buyhatke: 'BuyHatke',
};

// Brands already covered by a full, hand-written /brands/:slug page — kept
// out of the long list below so each brand appears exactly once, always
// pointing at its richer internal page rather than the plain external link
// every other row gets.
const FLAGSHIP_KEYS = new Set(BRAND_DEALS.map((b) => b.name.toLowerCase().replace(/[^a-z0-9]/g, '')));

function normalizeKey(name) {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}

const LONG_TAIL = ALL_BRAND_DEALS.filter((b) => !FLAGSHIP_KEYS.has(normalizeKey(b.name)));

function FlagshipCard({ brand }) {
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

function BrandRow({ brand }) {
  return (
    <ChakraLink
      href={brand.url}
      isExternal
      onClick={() => track('Clicked Brand Voucher Link', { brand: brand.name, source: brand.source, pct: brand.pct })}
      display="flex"
      alignItems="center"
      justifyContent="space-between"
      gap="12px"
      p="12px 14px"
      borderRadius="12px"
      border="1px solid"
      borderColor="border"
      bg="surface2"
      _hover={{ textDecoration: 'none', borderColor: 'borderStrong', bg: 'surface3' }}
    >
      <Box minW={0}>
        <Text m={0} fontSize="13.5px" fontWeight={700} noOfLines={1}>
          {brand.name}
        </Text>
        <Text m={0} fontSize="11px" color="text3">
          via {SOURCE_LABEL[brand.source] || brand.source}
        </Text>
      </Box>
      <Flex align="center" gap="8px" flex="0 0 auto">
        <Flex align="center" gap="4px" px="8px" py="3px" borderRadius="99px" bg="brandSoft" color="brandText" fontSize="11.5px" fontWeight={700}>
          <I.zap size={10} />
          {brand.pct}% off
        </Flex>
        <Box color="text3">
          <I.external size={14} />
        </Box>
      </Flex>
    </ChakraLink>
  );
}

export default function BrandsIndexPage() {
  const [query, setQuery] = useState('');

  usePageTitle(
    'Gift Voucher deals by store',
    `Compare Gift Voucher discount rates across ${ALL_BRAND_DEALS.length}+ Indian stores — search any brand and go straight to whichever voucher partner has the best rate.`
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return LONG_TAIL;
    return LONG_TAIL.filter((b) => b.name.toLowerCase().includes(q));
  }, [query]);

  return (
    <InfoPageShell
      title="Gift Voucher deals by store"
      subtitle={`Every store below sells Gift Vouchers at a discount through an official partner — buy one, spend it like store credit, save the difference. ${ALL_BRAND_DEALS.length}+ stores tracked across our voucher partners.`}
      maxW="920px"
    >
      <Grid templateColumns={{ base: '1fr', sm: 'repeat(2, 1fr)' }} gap="12px" mb="32px">
        {BRAND_DEALS.map((b) => (
          <FlagshipCard key={b.slug} brand={b} />
        ))}
      </Grid>

      <Text as="h2" m="0 0 12px" fontSize="15px" fontWeight={800} letterSpacing="-.01em">
        Search every store we track
      </Text>

      <InputGroup mb="14px">
        <InputLeftElement pointerEvents="none" h="42px">
          <Box color="text3">
            <I.search size={16} />
          </Box>
        </InputLeftElement>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a store name…"
          h="42px"
          borderRadius="12px"
          fontSize="13.5px"
          bg="surface"
        />
      </InputGroup>

      {filtered.length === 0 ? (
        <Text fontSize="13px" color="text3" py="20px" textAlign="center">
          No store matches "{query}" yet — search it on Dealo instead and we'll check its rate live.
        </Text>
      ) : (
        <Flex direction="column" gap="8px" maxH={query ? undefined : '640px'} overflowY={query ? undefined : 'auto'}>
          {filtered.map((b) => (
            <BrandRow key={`${b.source}-${b.name}`} brand={b} />
          ))}
        </Flex>
      )}

      <Box mt="24px">
        <Text fontSize="12.5px" color="text3" lineHeight={1.6}>
          Each store above links straight to whichever voucher partner currently has its best rate. Buying something
          from a store not listed? Search it on Dealo and we'll check its rate live.
        </Text>
      </Box>
    </InfoPageShell>
  );
}
