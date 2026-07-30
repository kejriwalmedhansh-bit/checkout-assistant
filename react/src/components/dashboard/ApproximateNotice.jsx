import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '../common/icons';
import InfoNote from '../common/InfoNote';

const COPY = {
  picker: {
    title: 'Closest match, not an exact one.',
    body: "We couldn't confirm this exact product elsewhere, so these are the nearest verified listings instead. Check the title carefully before choosing.",
  },
  results: {
    // Shortened on the results page (the picker variant above is untouched)
    // — the full two-sentence version moves behind the row's own InfoNote
    // so it's still there for anyone who wants it.
    short: "Closest match — price isn't confirmed for this exact product.",
    full: "We couldn't verify this exact item elsewhere. The price shown is for the closest match we found, not a confirmed price for your exact product.",
  },
};

/** Caution banner shown whenever the backend could only find an approximate
 * (not exact) match — see `approximate` in searchStore.js. */
export default function ApproximateNotice({ variant = 'picker' }) {
  if (variant === 'results') {
    const { short, full } = COPY.results;
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
        <InfoNote short={short} full={full} fontSize="14px" color="text" mt="0" />
      </Flex>
    );
  }

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
