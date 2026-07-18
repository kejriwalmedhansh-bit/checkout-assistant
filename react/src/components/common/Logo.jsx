import { Box, Flex, Text } from '@chakra-ui/react';

import { gradients } from '@/theme/foundations/colors';
import { SoloMark } from './icons';

/**
 * Dealo wordmark + gradient tile. The wordmark's accent uses the `brand` token,
 * which the theme resolves to Dealo green.
 */
export default function Logo({ size = 30, wordmark = true, shadow = true }) {
  return (
    <Flex align="center" gap="10px">
      <Box
        w={`${size}px`}
        h={`${size}px`}
        borderRadius={`${size * 0.3}px`}
        bg={gradients.logoMark}
        boxShadow={shadow ? 'brandGlowLogo' : 'none'}
        display="grid"
        placeItems="center"
        flex="0 0 auto"
      >
        <SoloMark size={size * 0.56} color="#fff" />
      </Box>

      {wordmark && (
        <Text
          as="span"
          fontSize={`${size * 0.62}px`}
          fontWeight={800}
          letterSpacing="-.02em"
          lineHeight={1}
        >
          <Box as="span" color="text">
            Deal
          </Box>
          <Box as="span" color="brand">
            o
          </Box>
        </Text>
      )}
    </Flex>
  );
}
