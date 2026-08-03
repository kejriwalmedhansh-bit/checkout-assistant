import { Box, Flex, Image, Link, Text } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';

/**
 * Product identity — a big, real photo (what we're pricing), with the name
 * wrapped directly onto it as a caption instead of stacked in a separate row
 * below. Wrapping the name onto the photo keeps this a genuinely large image
 * (unlike an earlier version that shrank to a 52px thumbnail to save space)
 * while paying for only one block's worth of height, not two — needed after
 * live mobile testing showed the primary action button had to fit on screen
 * without scrolling. The photo still links to the exact vendor product page
 * — someone should be able to tap it and land on the real listing to confirm
 * it's the right item before buying a voucher for it. Falls back to a
 * generic icon tile when there's no photo.
 */
export default function ProductIdentity({ name, sourceUrl, thumbnail }) {
  const prefersReduced = useReducedMotion();

  const content = (
    <Flex position="relative" bg="surface2" justify="center" align="center" h={{ base: '150px', md: '190px' }}>
      {thumbnail ? (
        <motion.div
          style={{ width: '100%', height: '100%', display: 'flex' }}
          initial={prefersReduced ? false : { opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <Image src={thumbnail} alt="" w="100%" h="100%" objectFit="cover" />
        </motion.div>
      ) : (
        <Flex w="100%" h="100%" align="center" justify="center" color="brand" bg="brandSoft">
          <I.cart size={28} />
        </Flex>
      )}

      <Box
        position="absolute"
        left={0}
        right={0}
        bottom={0}
        px="14px"
        py="10px"
        bgImage="linear-gradient(to top, rgba(0,0,0,.72), transparent)"
      >
        <Text
          fontSize="15px"
          fontWeight={700}
          color="white"
          noOfLines={1}
          sx={{ textShadow: '0 1px 4px rgba(0,0,0,.5)' }}
        >
          {name}
        </Text>
      </Box>
    </Flex>
  );

  return (
    <Card p="0" overflow="hidden">
      {sourceUrl ? (
        <Link href={sourceUrl} isExternal display="block" _hover={{ opacity: 0.93 }}>
          {content}
        </Link>
      ) : (
        content
      )}
    </Card>
  );
}
