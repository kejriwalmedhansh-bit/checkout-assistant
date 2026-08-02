import { Box, Flex, Image, Link, Text } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';

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
 * Product identity box — what we're pricing. Shows the product name, linked
 * to the source URL when the search was a URL. A compact single row —
 * thumbnail beside the name, not a full-width banner above it — so the
 * primary action lower on the page doesn't need a scroll to reach on a phone
 * (a real photo used to get a ~190px banner treatment; that pushed the CTA
 * below the fold on an iPhone 16 Pro in testing). The photo still links to
 * the exact vendor product page — someone should be able to tap the picture
 * and land on the real listing to confirm it's the right item before buying
 * a voucher for it. Falls back to a generic icon when there's no photo.
 */
export default function ProductIdentity({ name, sourceUrl, thumbnail }) {
  const prefersReduced = useReducedMotion();

  const thumb = thumbnail ? (
    <motion.div
      style={{ width: '100%', height: '100%', display: 'flex' }}
      initial={prefersReduced ? false : { opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <Image src={thumbnail} alt="" w="100%" h="100%" objectFit="cover" borderRadius="10px" />
    </motion.div>
  ) : (
    <Flex w="100%" h="100%" align="center" justify="center" color="brand">
      <I.cart size={22} />
    </Flex>
  );

  return (
    <Card p="12px 16px">
      <Flex align="center" gap="12px">
        <Box w="52px" h="52px" flex="0 0 auto" borderRadius="10px" bg="surface2" border="1px solid" borderColor="border" overflow="hidden">
          {sourceUrl ? (
            <Link href={sourceUrl} isExternal display="flex" w="100%" h="100%" _hover={{ opacity: 0.85 }}>
              {thumb}
            </Link>
          ) : (
            thumb
          )}
        </Box>
        <NameBlock name={name} sourceUrl={sourceUrl} />
      </Flex>
    </Card>
  );
}
