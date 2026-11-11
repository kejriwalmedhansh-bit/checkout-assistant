import { Box, Flex, IconButton, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';

// One line of the voucher card: label, the value in mono, and a quiet copy
// icon on the right (2026-11-02, owner's ask: copy the code and the PIN with
// one tap, the way bank apps do; icon only, no pill or word, and a tick for
// about half a second once copied).
export default function CodeRow({ label, value, copied, onCopy }) {
  return (
    <Flex align="center" justify="space-between" gap="12px">
      <Box minW={0}>
        <Text fontSize="11px" letterSpacing=".12em" opacity={0.6}>
          {label}
        </Text>
        <Text fontFamily="mono" fontWeight={600} fontSize="17px" wordBreak="break-all">
          {value}
        </Text>
      </Box>
      <IconButton
        onClick={onCopy}
        aria-label={copied ? `${label} copied` : `Copy ${label.toLowerCase()}`}
        icon={copied ? <I.check size={18} /> : <I.copy size={18} />}
        variant="iconSubtle"
        minW="40px"
        h="40px"
        flexShrink={0}
        borderRadius="12px"
        bg="transparent"
        color={copied ? 'brass' : 'onBrand'}
        opacity={copied ? 1 : 0.7}
        _hover={{ opacity: 1, bg: 'whiteAlpha.100', color: copied ? 'brass' : 'onBrand' }}
        _active={{ bg: 'whiteAlpha.200' }}
      />
    </Flex>
  );
}
