import { Box, Flex, Link, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { fmt, affiliateUrl } from '@/utils/format';

/**
 * One alternative route row: merchant + a plain sub-line (voucher discount or
 * "direct purchase"), an optional store link, and the final cost.
 */
export default function AltItem({ alt }) {
  const v = alt.voucher || null;
  const sellerLink = alt.sellers?.[0]?.link;

  return (
    <Card p="14px 18px">
      <Flex align="center" justify="space-between" gap="12px">
        <Box minW={0}>
          <Text fontSize="14px" fontWeight={600} color="text">
            {alt.merchant}
          </Text>
          <Text fontSize="12px" color="text2" mt="2px">
            {v ? `With Gyftr voucher · ${v.upi?.pct}% off` : 'Direct purchase · no voucher available'}
          </Text>
          {sellerLink && (
            <Link
              href={affiliateUrl(sellerLink)}
              isExternal
              display="inline-block"
              mt="5px"
              fontSize="11px"
              fontWeight={500}
              color="orangeText"
              bg="orangeSoft"
              border="1px solid"
              borderColor="orange"
              borderRadius="6px"
              px="8px"
              py="2px"
              _hover={{ textDecoration: 'none', bg: 'orangeSoft2' }}
            >
              Open store →
            </Link>
          )}
        </Box>
        <Text fontSize="16px" fontWeight={600} color="text" flex="0 0 auto">
          {fmt(alt.final_cost ? Math.round(alt.final_cost) : null)}
        </Text>
      </Flex>
    </Card>
  );
}
