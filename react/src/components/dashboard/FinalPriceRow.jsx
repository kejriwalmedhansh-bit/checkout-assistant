import { Box, Flex, Text } from '@chakra-ui/react';

import { fmt } from '@/utils/format';

/** "You pay {final}" row, with the original price struck through when saving > 0. */
export default function FinalPriceRow({ finalPrice, originalPrice, saving }) {
  if (!finalPrice) return null;

  return (
    <Flex
      align="center"
      justify="space-between"
      bg="greenSoft"
      border="1px solid"
      borderColor="green"
      borderRadius="sm"
      px="18px"
      py="14px"
    >
      <Box>
        <Text fontSize="12px" fontWeight={600} color="green">
          You pay
        </Text>
        {originalPrice && saving ? (
          <Text fontSize="11px" color="text3" textDecoration="line-through">
            {fmt(originalPrice)} elsewhere
          </Text>
        ) : null}
      </Box>
      <Text fontSize="28px" fontWeight={700} color="green" lineHeight={1}>
        {fmt(finalPrice)}
      </Text>
    </Flex>
  );
}
