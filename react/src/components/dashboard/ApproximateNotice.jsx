import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '../common/icons';

const COPY = {
  picker: {
    title: 'Closest match, not an exact one.',
    body: "We couldn't confirm this exact product elsewhere, so these are the nearest verified listings instead. Check the title carefully before choosing.",
  },
  results: {
    title: 'This price may be for a similar product.',
    body: "We couldn't verify this exact item elsewhere — the price below is for the closest match we found, not a confirmed price for your product.",
  },
};

/** Caution banner shown whenever the backend could only find an approximate
 * (not exact) match — see `approximate` in searchStore.js. */
export default function ApproximateNotice({ variant = 'picker' }) {
  const { title, body } = COPY[variant];
  return (
    <Flex
      align="flex-start"
      gap="10px"
      bg="amberSoft"
      border="1px solid"
      borderColor="amber"
      borderRadius="sm"
      px="18px"
      py="16px"
      mb="14px"
    >
      <Box color="amber" flex="0 0 auto" mt="1px">
        <I.info size={18} />
      </Box>
      <Box>
        <Text fontSize="14px" fontWeight={600} color="text">
          {title}
        </Text>
        <Text fontSize="13px" color="text3" mt="2px">
          {body}
        </Text>
      </Box>
    </Flex>
  );
}
