import { useState } from 'react';
import { Box, Flex, Image, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import TourRing from '@/components/onboarding/TourRing';
import { useTourHighlight } from '@/components/onboarding/useTourHighlight';
import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * One candidate product in the selection grid (step 1 of the two-step flow).
 * Tapping the card body opens the quick-view detail modal (browsing-first,
 * safe default) — only the explicit "Find Better Price" pill commits the
 * product_token and kicks off the route build.
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

// Was 100 — measurably too long for a one-line picker row on a phone (the
// title wrapped or got clipped mid-word by the container instead of by this
// limit). Cut to 40; nothing about the full title is actually lost, since
// tapping anywhere on the card (see below) opens the same quick-view detail
// modal — the full, untruncated title is one tap away.
const TITLE_LIMIT = 40;

export default function ProductCandidateCard({ product, onSelect, onEnlarge, isSelecting, tourId }) {
  const { title, price, thumbnail, source, product_token: token } = product;
  const isTruncated = Boolean(title && title.length > TITLE_LIMIT);
  const displayTitle = isTruncated ? title.slice(0, TITLE_LIMIT).trimEnd() : title;
  // Backend marks a live-fetched price (read straight off the page the user
  // pasted, not Google's index) with this product_token prefix — see
  // _live_price_candidate in src/services/search_service.py.
  const isVerifiedLive = token?.startsWith('live-price:');
  const { active: thumbnailHighlighted, dim: thumbnailDim } = useTourHighlight(tourId);
  // Set the moment "Find Better Price" is tapped. The pill fills and sinks
  // and the page changes a beat later, so the tap is actually seen — going
  // straight to the next page made it feel like nothing had been pressed.
  const [pressed, setPressed] = useState(false);
  const choose = () => {
    if (pressed) return;
    setPressed(true);
    navigator.vibrate?.(10); // a tiny tick on Android; iPhones ignore it
    setTimeout(() => onSelect(token, title, price, source, thumbnail), 160);
  };

  return (
    <Card
      as="button"
      type="button"
      role="group"
      onClick={() => onEnlarge?.()}
      disabled={isSelecting}
      textAlign="left"
      w="100%"
      p="14px 16px"
      cursor={isSelecting ? 'wait' : 'pointer'}
      opacity={isSelecting ? 0.6 : 1}
      transition="transform .2s cubic-bezier(0.23, 1, 0.32, 1), box-shadow .2s cubic-bezier(0.23, 1, 0.32, 1), border-color .2s ease"
      // Press feedback — on a phone (most of this product's traffic) a tap
      // otherwise gives no visible response until the isSelecting dim kicks
      // in ~300ms later. A small, quick sink, like a physical key.
      _active={{ transform: 'scale(0.98)', transitionDuration: '.1s' }}
      sx={{
        // Hover lift only for a real mouse. On phones a tap leaves :hover
        // stuck on, which left the card floating after the finger lifted.
        '@media (hover: hover) and (pointer: fine)': {
          '&:hover': { borderColor: 'brand', boxShadow: '0 10px 24px rgba(20,32,54,.12)', transform: 'translateY(-2px)' },
        },
        // Pressing the pill shouldn't also sink the whole card behind it.
        '&:has([data-pill]:active)': { transform: 'none' },
        ...REDUCED_MOTION_SX,
      }}
    >
      <Flex align="center" gap="14px">
        {/* Outer wrapper carries the tour ring — it must sit outside the
            inner box's overflow:hidden (which clips the image to its
            rounded corners), since the ring extends past the edges via a
            negative inset and would otherwise be clipped along with it. */}
        <Box
          position="relative"
          zIndex={thumbnailHighlighted && thumbnailDim ? 201 : undefined}
          flex="0 0 auto"
          borderRadius="12px"
        >
          {thumbnailHighlighted && <TourRing />}
          <Flex
            w="76px"
            h="76px"
            borderRadius="12px"
            bg="surface3"
            border="1px solid"
            borderColor="border"
            align="center"
            justify="center"
            overflow="hidden"
            transition="transform .18s cubic-bezier(.16,.68,.32,1)"
            _groupHover={{ transform: 'scale(1.08)' }}
            sx={REDUCED_MOTION_SX}
          >
            {thumbnail ? (
              <Image src={thumbnail} alt={title || 'Product photo'} maxW="88%" maxH="88%" objectFit="contain" />
            ) : (
              <Box color="text3">
                <I.cart size={26} />
              </Box>
            )}
          </Flex>
        </Box>

        {/* Phones: name on top with the full width, price and button on
            one line beneath it. Side by side, the nowrap button left the
            name a ~40px column that broke words mid-way ("Airdope-s").
            Wider screens keep all three in one row. */}
        <Flex
          flex="1"
          minW={0}
          direction={{ base: 'column', md: 'row' }}
          align={{ base: 'stretch', md: 'center' }}
          gap={{ base: '8px', md: '14px' }}
        >
          <Box minW={0} flex="1">
            <Text fontSize="13.5px" fontWeight={600} color="text" lineHeight={1.35}>
              {displayTitle || 'Product'}
              {isTruncated && (
                <Box as="span" color="brand" fontWeight={800} ml="2px">
                  …
                </Box>
              )}
            </Text>
            {isVerifiedLive && (
              <Text fontSize="11px" fontWeight={600} color="green.500" mt="2px">
                Verified from your link
              </Text>
            )}
          </Box>

          <Flex
            flex="0 0 auto"
            direction={{ base: 'row', md: 'column' }}
            align={{ base: 'center', md: 'flex-end' }}
            justify={{ base: 'space-between', md: 'flex-start' }}
            gap={{ base: '8px', md: 0 }}
            wrap={{ base: 'wrap', md: 'nowrap' }}
            textAlign="right"
          >
            {price != null && (
              <Text
                fontFamily="mono"
                fontSize="12.5px"
                fontWeight={500}
                color="text3"
                transition="opacity .18s ease"
                _groupHover={{ opacity: 0.5 }}
              >
                <Box
                  as="span"
                  // Phones drop the label to keep price and button on one line.
                  display={{ base: 'none', md: 'inline' }}
                  fontSize="10px"
                  textTransform="uppercase"
                  letterSpacing=".05em"
                  mr="4px"
                >
                  Listed
                </Box>
                {fmt(price)}
              </Text>
            )}
            <Flex
              role="button"
              tabIndex={0}
              aria-label="Find better price for this product"
              data-pill=""
              data-pressed={pressed || undefined}
              onClick={(e) => {
                e.stopPropagation();
                choose();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  e.stopPropagation();
                  choose();
                }
              }}
              align="center"
              justify="center"
              gap="5px"
              mt={{ base: 0, md: '6px' }}
              bg="brandSoft"
              color="brand"
              fontSize="12px"
              fontWeight={800}
              whiteSpace="nowrap"
              borderRadius="999px"
              px={{ base: '12px', md: '10px' }}
              py={{ base: '7px', md: '5px' }}
              cursor="pointer"
              transition="background .12s ease, color .12s ease, transform .16s cubic-bezier(0.23, 1, 0.32, 1), box-shadow .16s ease"
              boxShadow="inset 0 0 0 1px rgba(30,50,80,.10)"
              _hover={{ bg: 'brand', color: 'onBrand' }}
              _active={{ bg: 'brand', color: 'onBrand', transform: 'scale(0.94)', transitionDuration: '.08s' }}
              sx={{
                '&[data-pressed]': { bg: 'brand', color: 'onBrand', transform: 'scale(0.96)' },
                '&[data-pressed] .pill-arrow': { transform: 'translateX(4px)' },
              }}
              _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
            >
              <I.trendUp size={13} />
              Find Better Price
              <Box
                className="pill-arrow"
                display="inline-flex"
                transition="transform .18s cubic-bezier(0.23, 1, 0.32, 1)"
                _groupHover={{ transform: 'translateX(4px)' }}
                sx={REDUCED_MOTION_SX}
              >
                <I.chevRight size={12} />
              </Box>
            </Flex>
          </Flex>
        </Flex>
      </Flex>
    </Card>
  );
}
