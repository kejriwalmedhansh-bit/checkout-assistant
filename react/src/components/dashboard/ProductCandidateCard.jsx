import { Box, Flex, Image, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * One candidate product in the selection grid (step 1 of the two-step flow).
 * Clicking it commits the product_token and kicks off the route build.
 */
export default function ProductCandidateCard({ product, onSelect, isSelecting }) {
  const { title, price, thumbnail, source, product_token: token } = product;

  return (
    <Card
      as="button"
      type="button"
      onClick={() => onSelect(token, title, price, source, thumbnail)}
      disabled={isSelecting}
      textAlign="left"
      w="100%"
      p="14px 16px"
      cursor={isSelecting ? 'wait' : 'pointer'}
      opacity={isSelecting ? 0.6 : 1}
      transition="border-color .12s, box-shadow .12s"
      _hover={{ borderColor: 'brand', boxShadow: 'md' }}
    >
      <Flex align="center" gap="14px">
        <Flex
          w="76px"
          h="76px"
          flex="0 0 auto"
          borderRadius="12px"
          bg="surface3"
          border="1px solid"
          borderColor="border"
          align="center"
          justify="center"
          overflow="hidden"
        >
          {thumbnail ? (
            <Image src={thumbnail} alt="" maxW="88%" maxH="88%" objectFit="contain" />
          ) : (
            <Box color="text3">
              <I.cart size={26} />
            </Box>
          )}
        </Flex>

        <Box minW={0} flex="1">
          <Text fontSize="13.5px" fontWeight={600} color="text" noOfLines={2} lineHeight={1.35}>
            {title || 'Product'}
          </Text>
        </Box>

        <Box flex="0 0 auto" textAlign="right">
          {price != null && (
            <Text fontFamily="mono" fontSize="14px" fontWeight={600} color="text">
              from {fmt(price)}
            </Text>
          )}
          <Box color="text3" display="inline-flex" mt="4px">
            <I.chevRight size={16} />
          </Box>
        </Box>
      </Flex>
    </Card>
  );
}
