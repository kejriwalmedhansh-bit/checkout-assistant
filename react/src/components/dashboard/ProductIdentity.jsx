import { Box, Flex, Image, Link, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';

/**
 * Product identity box — what we're pricing. Shows the product name, linked to
 * the source URL when the search was a URL. Shows the real product photo
 * (carried over from the candidate the user picked) when one is available.
 */
function NameBlock({ name, sourceUrl }) {
  return (
    <Box minW={0}>
      <Text fontSize="11px" color="text3" fontWeight={500} letterSpacing=".06em" textTransform="uppercase">
        Searching for
      </Text>
      <Text fontSize="15px" fontWeight={700} color="text" noOfLines={2}>
        {sourceUrl ? (
          <Link href={sourceUrl} isExternal color="brandText">
            {name}
          </Link>
        ) : (
          name
        )}
      </Text>
    </Box>
  );
}

/**
 * Product identity box — what we're pricing. Shows the product name, linked to
 * the source URL when the search was a URL. When a real product photo is
 * available (carried over from the candidate the user picked), it gets a
 * full-width banner treatment — the point is to make this look like a
 * specific, real item, not a generic placeholder. Falls back to a compact
 * icon row when there's no photo.
 */
export default function ProductIdentity({ name, sourceUrl, thumbnail }) {
  if (thumbnail) {
    return (
      <Card p="0" overflow="hidden">
        <Flex
          bg="bgGrid"
          borderBottom="1px solid"
          borderColor="border"
          justify="center"
          align="center"
          h="150px"
          p="14px"
        >
          <Image
            src={thumbnail}
            alt=""
            maxW="55%"
            maxH="100%"
            objectFit="contain"
            filter="drop-shadow(var(--chakra-shadows-photoDrop))"
          />
        </Flex>
        <Box p="14px 18px">
          <NameBlock name={name} sourceUrl={sourceUrl} />
        </Box>
      </Card>
    );
  }

  return (
    <Card p="16px 18px">
      <Flex align="center" gap="14px">
        <Flex
          w="52px"
          h="52px"
          borderRadius="12px"
          bg="brandSoft"
          color="brand"
          align="center"
          justify="center"
          flex="0 0 auto"
        >
          <I.cart size={24} />
        </Flex>
        <NameBlock name={name} sourceUrl={sourceUrl} />
      </Flex>
    </Card>
  );
}
