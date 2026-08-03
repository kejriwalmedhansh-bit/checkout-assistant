import { Box, Flex, Image, Link, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';

/**
 * Product identity — a small thumbnail + name row (shrunk from an earlier
 * full-width banner photo so the how-to steps below fit on screen without
 * scrolling). Hovering the thumbnail on desktop floats a bigger version of
 * the same photo right there — no click needed — so the "is this the right
 * item" check the old big photo gave doesn't disappear just because the
 * resting size got smaller. The whole row still links to the exact vendor
 * product page, same as the old photo did. Falls back to a generic icon
 * tile when there's no photo.
 */
export default function ProductIdentity({ name, sourceUrl, thumbnail }) {
  const thumb = (
    <Box
      position="relative"
      role="group"
      w="44px"
      h="44px"
      flex="0 0 auto"
      borderRadius="10px"
      bg="surface3"
      border="1px solid"
      borderColor="border"
      overflow="hidden"
    >
      {thumbnail ? (
        <Image src={thumbnail} alt="" w="100%" h="100%" objectFit="contain" />
      ) : (
        <Flex w="100%" h="100%" align="center" justify="center" color="brand" bg="brandSoft">
          <I.cart size={18} />
        </Flex>
      )}

      {/* Floats above the small resting thumbnail on hover — desktop-only in
          practice, since touch devices don't sustain a hover state. */}
      {thumbnail && (
        <Box
          position="absolute"
          left="52px"
          top="-8px"
          w="150px"
          h="150px"
          borderRadius="14px"
          bg="surface2"
          border="1px solid"
          borderColor="borderStrong"
          boxShadow="0 20px 36px rgba(0,0,0,.28)"
          opacity={0}
          transform="scale(.92) translateY(4px)"
          transition="opacity .15s ease, transform .15s ease"
          pointerEvents="none"
          zIndex={5}
          overflow="hidden"
          _groupHover={{ opacity: 1, transform: 'scale(1) translateY(0)' }}
        >
          <Image src={thumbnail} alt="" w="100%" h="100%" objectFit="contain" />
        </Box>
      )}
    </Box>
  );

  const content = (
    <Flex align="center" gap="12px" p="12px 14px">
      {thumb}
      <Text fontSize="14px" fontWeight={700} color="text" noOfLines={2} lineHeight={1.3}>
        {name}
      </Text>
    </Flex>
  );

  return (
    <Card p="0" overflow="visible">
      {sourceUrl ? (
        <Link href={sourceUrl} isExternal display="block" _hover={{ bg: 'surface2' }} borderRadius="md">
          {content}
        </Link>
      ) : (
        content
      )}
    </Card>
  );
}
