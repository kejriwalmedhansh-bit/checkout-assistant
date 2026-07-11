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
    <Flex
      align="center"
      gap="14px"
      bg="greenSoft"
      border="1.5px solid"
      borderColor="green"
      borderRadius="md"
      px="20px"
      py="16px"
      boxShadow="0 1px 0 rgba(26,158,99,.08)"
    >
      <Flex
        w="44px"
        h="44px"
        flex="0 0 auto"
        borderRadius="12px"
        bg="green"
        color="white"
        align="center"
        justify="center"
      >
        <I.trendUp size={22} />
      </Flex>

      <Box flex="1" minW={0}>
        <Flex align="baseline" gap="10px" flexWrap="wrap">
          <Text fontSize="24px" fontWeight={800} color="green" lineHeight={1.1} letterSpacing="-.01em">
            You save {fmt(saving)}
          </Text>
          {pct != null && pct > 0 && (
            <Box
              as="span"
              bg="green"
              color="white"
              fontSize="12px"
              fontWeight={700}
              borderRadius="999px"
              px="8px"
              py="2px"
              lineHeight={1.6}
            >
              -{pct}%
            </Box>
          )}
        </Flex>
        <Flex align="center" gap="6px" mt="2px" fontSize="13px" color="text2">
          <Text as="span" textDecoration="line-through" color="text3">
            {fmt(originalPrice)}
          </Text>
          <Text as="span">→</Text>
          <Text as="span" fontWeight={600} color="text">
            {fmt(finalPrice)}
          </Text>
        </Flex>
      </Box>
    </Flex>
  );
}
