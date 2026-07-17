import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * The savings hero — this is Dealo's core value proposition, so it gets the
 * strongest visual treatment on the page: a large "You save ₹X" headline
 * with a percentage badge, was/now price as supporting detail underneath.
 * Renders nothing when there is no positive saving to show.
 */
export default function SavingsBar({ originalPrice, finalPrice, saving }) {
  if (!saving || saving <= 0) return null;

  const pct = originalPrice ? Math.round((saving / originalPrice) * 100) : null;

  return (
    <Box
      bg="greenSoft"
      border="1.5px solid"
      borderColor="green"
      borderRadius="md"
      px="20px"
      py="22px"
      boxShadow="savingsHairline"
      textAlign="center"
    >
      <Flex align="center" justify="center" gap="8px" mb="2px">
        <Flex
          w="30px"
          h="30px"
          flex="0 0 auto"
          borderRadius="9px"
          bg="green"
          color="white"
          align="center"
          justify="center"
        >
          <I.trendUp size={17} />
        </Flex>
        <Text fontSize="13px" fontWeight={700} color="green" letterSpacing=".01em">
          You save
        </Text>
      </Flex>

      <Text
        fontFamily="mono"
        fontSize={{ base: '38px', md: '46px' }}
        fontWeight={800}
        color="green"
        lineHeight={1.05}
        letterSpacing="-.02em"
      >
        {fmt(saving)}
      </Text>

      {pct != null && pct > 0 && (
        <Box
          as="span"
          display="inline-block"
          mt="8px"
          fontFamily="mono"
          bg="green"
          color="white"
          fontSize="12.5px"
          fontWeight={700}
          borderRadius="999px"
          px="10px"
          py="3px"
        >
          {pct}% less than usual
        </Box>
      )}

      <Flex align="center" justify="center" gap="8px" mt="12px" fontSize="14px" color="text2">
        <Text as="span" fontFamily="mono" textDecoration="line-through" color="text3">
          {fmt(originalPrice)}
        </Text>
        <Text as="span" color="text3">
          →
        </Text>
        <Text as="span" fontFamily="mono" fontWeight={700} color="text">
          {fmt(finalPrice)}
        </Text>
      </Flex>
    </Box>
  );
}
