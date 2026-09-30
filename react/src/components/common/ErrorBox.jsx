import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from './icons';

/**
 * Inline error banner — shared by every page that can fail a request.
 * `action` ({ label, onClick }) gives the person a way forward from it, so
 * an error is never a dead end with nothing to press.
 */
export default function ErrorBox({ message, action }) {
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
      role="alert"
    >
      <Box color="danger" flex="0 0 auto" mt="1px">
        <I.alert size={18} />
      </Box>
      <Box>
        <Text fontSize="14px" color="text">
          {message}
        </Text>
        {action && (
          <Box
            as="button"
            type="button"
            onClick={action.onClick}
            mt="8px"
            fontSize="13px"
            fontWeight={700}
            color="brand"
            _hover={{ textDecoration: 'underline' }}
          >
            {action.label}
          </Box>
        )}
      </Box>
    </Flex>
  );
}
