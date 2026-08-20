import { Box, Flex, Link, Text, Wrap, WrapItem } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * Shown instead of the picker when the query directly names a voucher brand
 * (see `mode: "brand_voucher"` from POST /search) — L1 price discovery is
 * skipped entirely, so there's no "you pay" final price here, only the
 * brand-level voucher terms. Same amber "voucher" tone JourneyRow already
 * uses elsewhere for this concept. Can come from Gyftr, Maximize, or
 * BuyHatke — whichever has the best headline rate (see `_pick_better_voucher`
 * in search_service.py).
 */
const SOURCE_LABELS = { maximize: 'Maximize', buyhatke: 'BuyHatke', gyftr: 'Gyftr' };

export default function BrandVoucherCard({ voucher }) {
  const denominations = voucher.denominations || [];
  const method = voucher.best_payment_method || 'UPI';
  const sourceLabel = SOURCE_LABELS[voucher.voucher_source] || 'Gyftr';
  // Never fabricate a store link — a guessed gyftr.com/{slug} URL is wrong
  // whenever this voucher actually came from Maximize (or the backend just
  // didn't have a real URL for this brand). Trust > a confident wrong link.
  const link = voucher.voucher_url || null;

  return (
    <Card p="22px 20px">
      <Flex align="center" gap="14px" mb="18px">
        <Flex
          w="44px" h="44px" flex="0 0 auto" borderRadius="12px"
          bg="amberSoft" color="amber" align="center" justify="center"
        >
          <I.ticket size={22} />
        </Flex>
        <Box minW={0}>
          <Text fontSize="16px" fontWeight={800} color="text" noOfLines={1}>
            {voucher.brand_name} Gift Voucher
          </Text>
          <Text fontSize="12px" color="text3" mt="1px">
            via {sourceLabel}
          </Text>
        </Box>
      </Flex>

      {voucher.best_discount_pct != null && (
        <Box mb="16px">
          <Text fontFamily="mono" fontSize="30px" fontWeight={700} color="amber" lineHeight={1}>
            {voucher.best_discount_pct}% off
          </Text>
          <Text fontSize="12.5px" color="text2" mt="4px">
            Best rate, paying by {method}
          </Text>
        </Box>
      )}

      {denominations.length > 0 && (
        <Box mb="18px">
          <Text fontSize="11px" color="text3" fontWeight={600} letterSpacing=".04em" textTransform="uppercase" mb="8px">
            Available denominations
          </Text>
          <Wrap spacing="6px">
            {denominations.map((d) => (
              <WrapItem key={d}>
                <Box
                  bg="surface2" border="1px solid" borderColor="border" borderRadius="8px"
                  px="10px" py="4px" fontFamily="mono" fontSize="12.5px" fontWeight={600} color="text2"
                >
                  {fmt(d)}
                </Box>
              </WrapItem>
            ))}
          </Wrap>
        </Box>
      )}

      {denominations.length === 0 && voucher.is_custom_denom && voucher.custom_min != null && voucher.custom_max != null && (
        <Box mb="18px">
          <Text fontSize="11px" color="text3" fontWeight={600} letterSpacing=".04em" textTransform="uppercase" mb="8px">
            Voucher amount
          </Text>
          <Box
            display="inline-block" bg="surface2" border="1px solid" borderColor="border" borderRadius="8px"
            px="10px" py="4px" fontFamily="mono" fontSize="12.5px" fontWeight={600} color="text2"
          >
            Any amount, {fmt(voucher.custom_min)}–{fmt(voucher.custom_max)}
          </Box>
        </Box>
      )}

      {link ? (
        <Link
          href={link}
          isExternal
          display="inline-flex"
          alignItems="center"
          justifyContent="center"
          gap="6px"
          w="100%"
          bg="amber"
          color="onBrand"
          fontSize="13.5px"
          fontWeight={700}
          borderRadius="10px"
          py="12px"
          _hover={{ textDecoration: 'none', opacity: 0.92 }}
        >
          Buy voucher on {sourceLabel}
          <I.arrowRight size={15} />
        </Link>
      ) : (
        <Text fontSize="12px" color="text3" textAlign="center">
          Store link unavailable right now — search for {voucher.brand_name} on {sourceLabel} directly.
        </Text>
      )}
    </Card>
  );
}
