import { Box, Flex, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import Card from '@/components/common/Card';
import Chip from '@/components/common/Chip';
import { I } from '@/components/common/icons';
import { ROUTES } from '@/routes/paths';

/**
 * Compact voucher brand card for the Vouchers grid. Tolerant of a loosely-typed
 * backend shape (the voucher routes may still be in progress): it reads a few
 * likely key names and degrades gracefully when fields are missing.
 */
export default function VoucherCard({ voucher }) {
  const name = voucher.brand_name || voucher.brand || voucher.merchant || voucher.name || 'Voucher';
  const slug = voucher.slug || voucher.id || encodeURIComponent(name);
  const pct =
    voucher.best_discount_pct ??
    voucher.upi?.pct ??
    voucher.discount_pct ??
    voucher.best_discount ??
    null;
  const category = voucher.category || voucher.categories?.[0];

  const to = ROUTES.voucherDetail.replace(':slug', slug);

  return (
    <Card
      as={RouterLink}
      to={to}
      p="16px 18px"
      transition="border-color .12s, box-shadow .12s"
      _hover={{ borderColor: 'borderStrong', boxShadow: 'md', textDecoration: 'none' }}
    >
      <Flex align="center" gap="12px" mb="10px">
        <Flex
          w="38px"
          h="38px"
          borderRadius="10px"
          bg="orangeSoft"
          color="orange"
          align="center"
          justify="center"
          flex="0 0 auto"
        >
          <I.ticket size={19} />
        </Flex>
        <Box minW={0}>
          <Text fontSize="14px" fontWeight={700} color="text" noOfLines={1}>
            {name}
          </Text>
          {category && (
            <Text fontSize="12px" color="text3" noOfLines={1}>
              {category}
            </Text>
          )}
        </Box>
      </Flex>
      {pct != null && (
        <Chip tone="green" mono={false}>
          {pct}% off via UPI
        </Chip>
      )}
    </Card>
  );
}
