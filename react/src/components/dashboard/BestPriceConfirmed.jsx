import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';

/**
 * Shown in place of SavingsBar when there's no positive saving to headline
 * (e.g. Amazon/Flipkart already has the best price, no voucher/card beats
 * it) — SavingsBar renders nothing in that case, which reads as "this app
 * didn't help" even though the recommendation is correct. This turns the
 * same fact into the trust signal itself: naming how many stores were
 * actually checked, not a vague reassurance.
 */
export default function BestPriceConfirmed({ comparedCount }) {
  const hasCount = comparedCount != null && comparedCount > 1;

  return (
    <Box
      bg="brandSoft"
      border="1.5px solid"
      borderColor="brand"
      borderRadius="md"
      px="20px"
      py="22px"
      textAlign="center"
    >
      <Flex align="center" justify="center" gap="8px" mb="4px">
        <Flex
          w="30px"
          h="30px"
          flex="0 0 auto"
          borderRadius="9px"
          bg="brand"
          color="onBrand"
          align="center"
          justify="center"
        >
          <I.checkCircle size={17} />
        </Flex>
        <Text fontSize="15px" fontWeight={700} color="brandText" letterSpacing="-.01em">
          Already the best price
        </Text>
      </Flex>

      <Text fontSize="13px" color="text2" mt="4px">
        {hasCount
          ? `Checked ${comparedCount} stores — nothing beats this price right now.`
          : "We checked and couldn't find it cheaper anywhere else."}
      </Text>
    </Box>
  );
}
