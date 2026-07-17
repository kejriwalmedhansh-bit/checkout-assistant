import { Box, Flex, Image, Link, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';

/**
 * Product identity box — what we're pricing. Shows the product name, linked to
 * the source URL when the search was a URL. Shows the real product photo
 * (carried over from the candidate the user picked) when one is available.
 */
export default function ProductIdentity({ name, sourceUrl, thumbnail }) {
  return (
    <Card p="16px 18px">
      <Flex align="center" gap="14px">
        <Flex
          w="64px"
          h="64px"
          borderRadius="12px"
          bg={thumbnail ? 'surface3' : 'brandSoft'}
          border={thumbnail ? '1px solid' : 'none'}
          borderColor="border"
          color="brand"
          align="center"
          justify="center"
          flex="0 0 auto"
          overflow="hidden"
        >
          {thumbnail ? (
            <Image src={thumbnail} alt="" maxW="88%" maxH="88%" objectFit="contain" />
          ) : (
            <I.cart size={26} />
          )}
        </Flex>
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
      </Flex>
    </Card>
  );
}
