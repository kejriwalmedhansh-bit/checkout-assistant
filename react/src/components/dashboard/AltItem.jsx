import { Box, Flex, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * One alternative route row. Clicking it promotes the alternative to the
 * primary route card at the top of the page (same full detail the
 * recommended route gets) — handled by the parent via onSelect, so the user
 * never has to scroll down to see it.
 */
export default function AltItem({ alt, onSelect, isSelected }) {
  const v = alt.voucher || null;

  return (
    <Card
      as="button"
      type="button"
      onClick={() => onSelect(alt)}
      w="100%"
      p="14px 18px"
      textAlign="left"
      cursor="pointer"
      bg={isSelected ? 'brandSoft2' : undefined}
      borderColor={isSelected ? 'brand' : undefined}
    >
      <Flex align="center" justify="space-between" gap="12px">
        <Flex align="center" gap="8px" minW={0}>
          {isSelected && (
            <Box color="brand" flex="0 0 auto">
              <I.checkCircle size={16} />
            </Box>
          )}
          <Box minW={0}>
            <Text fontSize="14px" fontWeight={600} color="text">
              {alt.merchant}
            </Text>
            <Text fontSize="12px" color="text2" mt="2px">
              {v ? `With Gyftr voucher · ${v.upi?.pct}% off` : 'Direct purchase · no voucher available'}
            </Text>
          </Box>
        </Flex>
        <Text fontSize="16px" fontWeight={600} color="text" flex="0 0 auto">
          {fmt(alt.final_cost ? Math.round(alt.final_cost) : null)}
        </Text>
      </Flex>
    </Card>
  );
}
