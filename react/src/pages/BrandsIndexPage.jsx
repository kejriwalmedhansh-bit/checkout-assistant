import { useMemo, useState } from 'react';
import { Box, Flex, Grid, Input, InputGroup, InputLeftElement, Link as ChakraLink, Select, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import BrandAvatar from '@/components/common/BrandAvatar';
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
      alignItems="center"
      gap="12px"
      p="14px"
      borderRadius="16px"
      border="1px solid"
      borderColor="border"
      bg="surface2"
      _hover={{ textDecoration: 'none', borderColor: 'borderStrong', bg: 'surface3' }}
    >
      <BrandAvatar name={brand.name} size={38} logoSrc={`/brand-logos/${brand.slug}.png`} />
      <Box minW={0} flex={1}>
        <Text m="0 0 2px" fontSize="14px" fontWeight={800} noOfLines={1}>
          {brand.name}
        </Text>
        <Flex align="center" gap="4px" fontSize="11.5px" fontWeight={700} color="brandText">
          <I.zap size={10} />
          {brand.ratePct}% off
        </Flex>
      </Box>
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
      gap="10px"
      p="10px 12px"
      borderRadius="13px"
      border="1px solid"
      borderColor="border"
      bg="surface2"
      _hover={{ textDecoration: 'none', borderColor: 'borderStrong', bg: 'surface3' }}
    >
      <BrandAvatar name={brand.name} size={32} />
      <Box minW={0} flex={1}>
        <Text m={0} fontSize="12.5px" fontWeight={700} noOfLines={1}>
          {brand.name}
        </Text>
        <Text m={0} fontSize="10.5px" color="text3">
          via {SOURCE_LABEL[brand.source] || brand.source}
        </Text>
      </Box>
      <Flex align="center" gap="3px" flex="0 0 auto" px="8px" py="3px" borderRadius="99px" bg="brandSoft" color="brandText" fontSize="11px" fontWeight={700}>
        <I.zap size={10} />
        {brand.pct}%
      </Flex>
      <Box color="text3" flex="0 0 auto">
        <I.external size={13} />
      </Box>
    </ChakraLink>
  );
}

export default function BrandsIndexPage() {
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('rate');

  usePageTitle(
    'Gift Voucher deals by store',
    `Compare Gift Voucher discount rates across ${ALL_BRAND_DEALS.length}+ Indian stores — search any brand and go straight to whichever voucher partner has the best rate.`
  );

  const trimmedQuery = query.trim();

  const filtered = useMemo(() => {
    if (!trimmedQuery) return [];
    const q = trimmedQuery.toLowerCase();
    const list = LONG_TAIL.filter((b) => b.name.toLowerCase().includes(q));
    return [...list].sort((a, b) => (sort === 'az' ? a.name.localeCompare(b.name) : b.pct - a.pct));
  }, [trimmedQuery, sort]);

  return (
    <InfoPageShell
      title="Gift Voucher deals by store"
      subtitle={`Every store below sells Gift Vouchers at a discount through an official partner — buy one, spend it like store credit, save the difference. ${ALL_BRAND_DEALS.length}+ stores tracked across our voucher partners.`}
      maxW="920px"
    >
      <Text as="h2" m="0 0 12px" fontSize="15px" fontWeight={800} letterSpacing="-.01em">
        Search every store we track
      </Text>

      <Flex gap="10px" mb="14px">
        <InputGroup flex={1}>
          <InputLeftElement pointerEvents="none" h="42px">
            <Box color="text3">
              <I.search size={16} />
            </Box>
          </InputLeftElement>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search for the brand you're looking for…"
            h="42px"
            borderRadius="12px"
            fontSize="13.5px"
            bg="surface"
          />
        </InputGroup>
        {trimmedQuery && (
          <Select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            w={{ base: '140px', sm: '180px' }}
            flex="0 0 auto"
            h="42px"
            borderRadius="12px"
            fontSize="13px"
            fontWeight={600}
            bg="surface"
          >
            <option value="rate">Highest rate</option>
            <option value="az">A–Z</option>
          </Select>
        )}
      </Flex>

      {trimmedQuery && (
        <>
          <Text fontSize="11.5px" color="text3" mb="10px">
            {filtered.length} store{filtered.length === 1 ? '' : 's'}
          </Text>

          {filtered.length === 0 ? (
            <Text fontSize="13px" color="text3" py="20px" textAlign="center">
              No store matches "{trimmedQuery}" yet — search it on Dealo instead and we'll check its rate live.
            </Text>
          ) : (
            <Grid templateColumns={{ base: '1fr', sm: 'repeat(2, 1fr)' }} gap="8px">
              {filtered.map((b) => (
                <BrandRow key={`${b.source}-${b.name}`} brand={b} />
              ))}
            </Grid>
          )}
        </>
      )}

      <Text as="h2" m="32px 0 12px" fontSize="13px" fontWeight={700} color="text3" letterSpacing=".02em" textTransform="uppercase">
        Popular stores
      </Text>
      <Grid templateColumns={{ base: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }} gap="10px">
        {BRAND_DEALS.map((b) => (
          <FlagshipCard key={b.slug} brand={b} />
        ))}
      </Grid>

      <Box mt="24px">
        <Text fontSize="12.5px" color="text3" lineHeight={1.6}>
          Each store above links straight to whichever voucher partner currently has its best rate. Buying something
          from a store not listed? Search it on Dealo and we'll check its rate live.
        </Text>
      </Box>
    </InfoPageShell>
  );
}
