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
 * Product identity box — what we're pricing. Shows the product name, linked to
 * the source URL when the search was a URL. When a real product photo is
 * available (carried over from the candidate the user picked), it gets a
 * full-width banner treatment — the point is to make this look like a
 * specific, real item, not a generic placeholder. Falls back to a compact
 * icon row when there's no photo.
 */
export default function ProductIdentity({ name, sourceUrl, thumbnail }) {
  const prefersReduced = useReducedMotion();
  const groundShadow = 'rgba(0,0,0,.55)';

  if (thumbnail) {
    return (
      <Card p="0" overflow="hidden">
        <Flex
          position="relative"
          bg="surface2"
          borderBottom="1px solid"
          borderColor="border"
          justify="center"
          align="center"
          h={{ base: '190px', md: '230px' }}
          p="20px"
        >
          {/* studio-style contact shadow, grounds the product instead of letting
              it float unanchored against the flat backdrop */}
          <Box
            position="absolute"
            bottom={{ base: '22px', md: '28px' }}
            w="46%"
            h="20px"
            borderRadius="50%"
            bg={`radial-gradient(closest-side, ${groundShadow}, transparent 75%)`}
            filter="blur(4px)"
          />
          <motion.div
            style={{ maxWidth: '82%', maxHeight: '100%', display: 'flex', position: 'relative' }}
            initial={prefersReduced ? false : { opacity: 0, y: 14, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <Image
              src={thumbnail}
              alt=""
              maxW="100%"
              maxH="100%"
              objectFit="contain"
              filter="drop-shadow(var(--chakra-shadows-photoDrop)) drop-shadow(var(--chakra-shadows-photoDropSoft))"
            />
          </motion.div>
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
