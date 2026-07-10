import { Flex, Text } from '@chakra-ui/react';

import { fmt } from '@/utils/format';

/**
 * Savings summary line: was {original} → now {final} → saved {saving}.
 * Renders nothing when there is no positive saving to show.
 */
export default function SavingsBar({ originalPrice, finalPrice, saving }) {
  if (!saving || saving <= 0) return null;

  return (
    <Flex
      align="center"
      gap="8px"
      flexWrap="wrap"
      bg="greenSoft"
      border="1px solid"
      borderColor="green"
      borderRadius="sm"
      px="16px"
      py="12px"
      fontSize="14px"
      color="text2"
    >
      <Text as="span">You were paying</Text>
      <Text as="span" textDecoration="line-through" color="text3">
        {fmt(originalPrice)}
      </Text>
      <Text as="span">→ Now paying</Text>
      <Text as="span" fontWeight={600} color="text">
        {fmt(finalPrice)}
      </Text>
      <Text as="span">→ Saved</Text>
      <Text as="span" fontWeight={700} color="green">
        {fmt(saving)}
      </Text>
    </Flex>
  );
}
