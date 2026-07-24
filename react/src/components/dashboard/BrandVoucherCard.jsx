import { Box, Flex, Link, Text, Wrap, WrapItem } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * Shown instead of the picker when the query directly names a Gyftr brand
 * (see `mode: "brand_voucher"` from POST /search) — L1 price discovery is
 * skipped entirely, so there's no "you pay" final price here, only the
 * brand-level voucher terms. Same amber "voucher" tone JourneyRow already
 * uses elsewhere for this concept.
 */
export default function BrandVoucherCard({ voucher }) {
  const denominations = voucher.denominations || [];
  const method = voucher.best_payment_method || 'UPI';

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
            via Gyftr
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

      <Link
        href={`https://www.gyftr.com/${voucher.slug}`}
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
        Buy voucher on Gyftr
        <I.arrowRight size={15} />
      </Link>
    </Card>
  );
}
