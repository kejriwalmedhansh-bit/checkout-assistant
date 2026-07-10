import { Box, Flex, Link, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';

/**
 * Product identity box — what we're pricing. Shows the product name, linked to
 * the source URL when the search was a URL.
 */
export default function ProductIdentity({ name, sourceUrl }) {
  return (
    <Card p="16px 18px">
      <Flex align="center" gap="14px">
        <Flex
          w="40px"
          h="40px"
          borderRadius="10px"
          bg="orangeSoft"
          color="orange"
          align="center"
          justify="center"
          flex="0 0 auto"
        >
          <I.cart size={20} />
        </Flex>
        <Box minW={0}>
          <Text fontSize="11px" color="text3" fontWeight={500} letterSpacing=".06em" textTransform="uppercase">
            Searching for
          </Text>
          <Text fontSize="15px" fontWeight={700} color="text" noOfLines={2}>
            {sourceUrl ? (
              <Link href={sourceUrl} isExternal color="orangeText">
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
