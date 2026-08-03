import { Box, Flex, Image, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * One candidate product in the selection grid (step 1 of the two-step flow).
 * Clicking it commits the product_token and kicks off the route build.
 */
// Standard-tier hover lift (confirmed over both a barely-there nudge and a
// bouncier spring): a real rise + shadow, no overshoot. Transform/opacity
// only so it stays on the compositor thread, and fully off under
// prefers-reduced-motion.
const REDUCED_MOTION_SX = {
  '@media (prefers-reduced-motion: reduce)': {
    transition: 'none !important',
    '&:hover': { transform: 'none !important' },
  },
};

const TITLE_LIMIT = 100;

export default function ProductCandidateCard({ product, onSelect, onEnlarge, isSelecting }) {
  const { title, price, thumbnail, source, product_token: token } = product;
  const displayTitle =
    title && title.length > TITLE_LIMIT ? `${title.slice(0, TITLE_LIMIT).trimEnd()}…` : title;
  // Backend marks a live-fetched price (read straight off the page the user
  // pasted, not Google's index) with this product_token prefix — see
  // _live_price_candidate in src/services/search_service.py.
  const isVerifiedLive = token?.startsWith('live-price:');

  return (
    <Card
      as="button"
      type="button"
      role="group"
      onClick={() => onSelect(token, title, price, source, thumbnail)}
      disabled={isSelecting}
      textAlign="left"
      w="100%"
      p="14px 16px"
      cursor={isSelecting ? 'wait' : 'pointer'}
      opacity={isSelecting ? 0.6 : 1}
      transition="transform .25s cubic-bezier(.16,.68,.32,1), box-shadow .25s cubic-bezier(.16,.68,.32,1), border-color .25s ease"
      _hover={{ borderColor: 'brand', boxShadow: '0 20px 36px rgba(0,0,0,.35)', transform: 'translateY(-6px) scale(1.02)' }}
      // Press feedback — the hover lift only reaches people with a mouse;
      // on a phone (most of this product's traffic) a tap gave no visible
      // response at all until the isSelecting dim kicked in ~300ms later.
      _active={{ transform: 'translateY(-2px) scale(0.99)', boxShadow: '0 10px 20px rgba(0,0,0,.3)' }}
      sx={REDUCED_MOTION_SX}
    >
      <Flex align="center" gap="14px">
        <Flex
          role={onEnlarge ? 'button' : undefined}
          tabIndex={onEnlarge ? 0 : undefined}
          aria-label={onEnlarge ? 'Enlarge photo' : undefined}
          onClick={
            onEnlarge
              ? (e) => {
                  e.stopPropagation();
                  onEnlarge();
                }
              : undefined
          }
          onKeyDown={
            onEnlarge
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.stopPropagation();
                    onEnlarge();
                  }
                }
              : undefined
          }
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
          cursor={onEnlarge ? 'zoom-in' : undefined}
          transition="transform .18s cubic-bezier(.16,.68,.32,1)"
          _hover={onEnlarge ? { transform: 'scale(1.08)' } : undefined}
          _focusVisible={onEnlarge ? { outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' } : undefined}
          sx={REDUCED_MOTION_SX}
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
          <Text fontSize="13.5px" fontWeight={600} color="text" lineHeight={1.35}>
            {displayTitle || 'Product'}
          </Text>
          {isVerifiedLive && (
            <Text fontSize="11px" fontWeight={600} color="green.500" mt="2px">
              Verified from your link
            </Text>
          )}
        </Box>

        <Box flex="0 0 auto" textAlign="right">
          {price != null && (
            <Text
              fontFamily="mono"
              fontSize="12.5px"
              fontWeight={500}
              color="text3"
              transition="opacity .18s ease"
              _groupHover={{ opacity: 0.5 }}
            >
              <Box as="span" fontSize="10px" textTransform="uppercase" letterSpacing=".05em" mr="4px">
                Listed
              </Box>
              {fmt(price)}
            </Text>
          )}
          <Flex
            align="center"
            justify="center"
            gap="5px"
            mt="6px"
            bg="brandSoft"
            color="brand"
            fontSize="12px"
            fontWeight={800}
            whiteSpace="nowrap"
            borderRadius="999px"
            px="10px"
            py="5px"
            transition="background .18s ease, color .18s ease"
            _groupHover={{ bg: 'brand', color: 'onBrand' }}
          >
            <I.trendUp size={13} />
            Find Better Price
            <Box
              display="inline-flex"
              transition="transform .18s cubic-bezier(.16,.68,.32,1)"
              _groupHover={{ transform: 'translateX(4px)' }}
              sx={REDUCED_MOTION_SX}
            >
              <I.chevRight size={12} />
            </Box>
          </Flex>
        </Box>
      </Flex>
    </Card>
  );
}
