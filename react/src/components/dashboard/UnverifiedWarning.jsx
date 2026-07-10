import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';

/** Warning shown when the backend flags untrusted sellers on the route. */
export default function UnverifiedWarning() {
  return (
    <Flex
      align="flex-start"
      gap="10px"
      bg="amberSoft"
      border="1px solid"
      borderColor="amber"
      borderRadius="sm"
      px="16px"
      py="14px"
    >
      <Box color="amber" flex="0 0 auto" mt="1px">
        <I.alert size={18} />
      </Box>
      <Box>
        <Text fontSize="13px" fontWeight={700} color="amber">
          Unverified sellers
        </Text>
        <Text fontSize="13px" color="text2" lineHeight={1.55}>
          We couldn&apos;t verify these sellers — please do your own research before buying.
        </Text>
      </Box>
    </Flex>
  );
}
