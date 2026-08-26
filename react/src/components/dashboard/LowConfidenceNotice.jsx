import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';

/**
 * Shown above the product picker when the backend's `approximate` flag is
 * true — the listings below only weakly matched the search (see
 * _STRONG_MATCH_FRACTION in search_service.py), so they're shown, not
 * hidden, but flagged rather than presented with the same silent confidence
 * as a solid match. Per CLAUDE.md rule #1 ("a wrong result is worse than no
 * result"): a labeled guess is still useful, an unlabeled wrong one isn't.
 */
export default function LowConfidenceNotice() {
  return (
    <Flex
      align="flex-start"
      gap="10px"
      bg="amberSoft"
      border="1px solid"
      borderColor="amber"
      borderRadius="md"
      px="14px"
      py="12px"
      mb="12px"
    >
      <Box color="amber" mt="1px" flex="0 0 auto">
        <I.alert size={15} />
      </Box>
      <Text fontSize="13px" color="text" fontWeight={500} lineHeight="1.4">
        Results confidence is low — try searching with the product name.
      </Text>
    </Flex>
  );
}
