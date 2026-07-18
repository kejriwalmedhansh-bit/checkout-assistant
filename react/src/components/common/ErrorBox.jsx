import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from './icons';

/** Inline error banner — shared by every page that can fail a request. */
export default function ErrorBox({ message }) {
  return (
    <Flex
      align="flex-start"
      gap="10px"
      bg="brandSoft2"
      border="1px solid"
      borderColor="danger"
      borderRadius="sm"
      px="18px"
      py="16px"
    >
      <Box color="danger" flex="0 0 auto" mt="1px">
        <I.alert size={18} />
      </Box>
      <Text fontSize="14px" color="text">
        {message}
      </Text>
    </Flex>
  );
}
