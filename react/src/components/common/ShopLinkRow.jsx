import { useState } from 'react';
import { Box, Flex, Grid, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import BrandAvatar from '@/components/common/BrandAvatar';
import { I } from '@/components/common/icons';
import { costLine } from '@/seo/categories';
import { pct, shownPct } from '@/seo/pageMeta';
import { ROUTES } from '@/routes/paths';
import { shopLogos } from '@/utils/priceList';

/** The shop's logo from the same sources the price list uses (Brandfetch,
 * then the site's favicon), on a white disc; initials if both are missing. */
export function ShopLogo({ shop, size = 56 }) {
  const sources = shopLogos(shop.website);
  const [tries, setTries] = useState(0);
  const src = sources[tries];
  const filled = tries === 0;
  const radius = size >= 48 ? '14px' : '10px';
  return (
    <Flex w={`${size}px`} h={`${size}px`} borderRadius={radius} bg="white" border="1px solid" borderColor="border" align="center" justify="center" overflow="hidden" flexShrink={0}>
      {src ? (
        <Box
          as="img"
          src={src}
          alt={`${shop.name} logo`}
          loading="lazy"
          decoding="async"
          w={filled ? '100%' : `${Math.round(size / 2)}px`}
          h={filled ? '100%' : `${Math.round(size / 2)}px`}
          objectFit={filled ? 'cover' : 'contain'}
          onError={() => setTries((t) => t + 1)}
        />
      ) : (
        <BrandAvatar name={shop.name} size={size} radius={radius} fontSize={`${Math.round(size * 0.4)}px`} />
      )}
    </Flex>
  );
}

/** One shop as a link to its page: logo, name, what ₹1,000 of shopping costs, today's %. */
export function ShopLinkRow({ shop }) {
  const rate = shownPct(shop);
  return (
    <Flex
      className="dealo-press" as={RouterLink}
      to={`${ROUTES.brandFor(shop.slug)}/`}
      align="center"
      gap="10px"
      p="10px 12px"
      borderRadius="12px"
      border="1px solid"
      borderColor="border"
      bg="surface2"
      _hover={{ textDecoration: 'none', borderColor: 'borderStrong', bg: 'surface3' }}
    >
      <ShopLogo shop={shop} size={34} />
      <Box minW={0} flex={1}>
        <Text m={0} fontSize="13px" fontWeight={700} noOfLines={1}>
          {shop.name}
        </Text>
        <Text m={0} fontSize="11px" color="text3" noOfLines={1}>
          {costLine(shop, rate)}
        </Text>
      </Box>
      <Flex align="center" gap="3px" flex="0 0 auto" px="8px" py="3px" borderRadius="999px" bg="brandSoft" color="brandText" fontSize="11px" fontWeight={700}>
        <I.zap size={10} />
        {pct(rate)}
      </Flex>
    </Flex>
  );
}

/** A grid of shop rows, two across from tablet width up. */
export function ShopGrid({ shops }) {
  return (
    <Grid templateColumns={{ base: '1fr', sm: 'repeat(2, 1fr)' }} gap="8px">
      {shops.map((s) => (
        <ShopLinkRow key={s.slug} shop={s} />
      ))}
    </Grid>
  );
}
