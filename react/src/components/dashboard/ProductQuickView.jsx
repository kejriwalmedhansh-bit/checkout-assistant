import { useEffect, useRef, useState } from 'react';
import { Box, Flex, Image, Text } from '@chakra-ui/react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

const TITLE_LIMIT = 100;
// Below this a swipe/drag is treated as a tap, not a page change.
const SWIPE_THRESHOLD = 60;

/**
 * Full-screen quick-view opened from a thumbnail on the product picker: a
 * bigger photo plus the same name/price/"Better price" info the picker row
 * already shows, so tapping a photo to check it isn't the right item gives
 * you the full picture, not just a zoomed image. Left/right arrows (and
 * swipe/drag, and arrow keys) move between the *other* candidates without
 * closing the view — the point is to compare look-alike listings side by
 * side without bouncing back to the list each time.
 */
export default function ProductQuickView({ products, index, onIndexChange, onSelect, onClose }) {
  const prefersReduced = useReducedMotion();
  const [dragStartX, setDragStartX] = useState(null);
  const containerRef = useRef(null);

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') step(1);
      if (e.key === 'ArrowLeft') step(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, products.length]);

  const step = (dir) => {
    onIndexChange((index + dir + products.length) % products.length);
  };

  const handlePointerDown = (e) => {
    setDragStartX(e.touches ? e.touches[0].clientX : e.clientX);
  };
  const handlePointerUp = (e) => {
    if (dragStartX == null) return;
    const endX = e.changedTouches ? e.changedTouches[0].clientX : e.clientX;
    const delta = endX - dragStartX;
    if (Math.abs(delta) > SWIPE_THRESHOLD) step(delta < 0 ? 1 : -1);
    setDragStartX(null);
  };

  const p = products[index];
  if (!p) return null;
  const { title, price, thumbnail, source, product_token: token } = p;
  const displayTitle = title && title.length > TITLE_LIMIT ? `${title.slice(0, TITLE_LIMIT).trimEnd()}…` : title;
  const isVerifiedLive = token?.startsWith('live-price:');
  const showArrows = products.length > 1;

  return (
    <Box
      ref={containerRef}
      tabIndex={-1}
      position="fixed"
      inset={0}
      zIndex={100}
      bg="rgba(10,12,10,.68)"
      backdropFilter="blur(3px)"
      display="flex"
      alignItems="center"
      justifyContent="center"
      p="20px"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        key={token}
        initial={prefersReduced ? false : { opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        style={{ width: '100%', maxWidth: '360px' }}
      >
        <Box bg="surface" borderRadius="20px" overflow="hidden" boxShadow="0 40px 80px rgba(0,0,0,.4)" position="relative">
          <Box
            as="button"
            type="button"
            aria-label="Close"
            onClick={onClose}
            position="absolute"
            top="10px"
            right="10px"
            zIndex={5}
            w="28px"
            h="28px"
            borderRadius="50%"
            bg="rgba(0,0,0,.4)"
            color="white"
            display="flex"
            alignItems="center"
            justifyContent="center"
          >
            <I.x size={14} />
          </Box>

          <Box
            position="relative"
            h="220px"
            bg="surface2"
            display="flex"
            alignItems="center"
            justifyContent="center"
            onMouseDown={handlePointerDown}
            onMouseUp={handlePointerUp}
            onTouchStart={handlePointerDown}
            onTouchEnd={handlePointerUp}
            cursor={showArrows ? 'grab' : 'default'}
            userSelect="none"
          >
            <AnimatePresence mode="wait">
              <motion.div
                key={token}
                initial={prefersReduced ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                {thumbnail ? (
                  <Image src={thumbnail} alt="" maxW="80%" maxH="80%" objectFit="contain" draggable={false} />
                ) : (
                  <Flex w="100%" h="100%" align="center" justify="center" color="brand" bg="brandSoft">
                    <I.cart size={40} />
                  </Flex>
                )}
              </motion.div>
            </AnimatePresence>

            {showArrows && (
              <>
                <Box
                  as="button"
                  type="button"
                  aria-label="Previous product"
                  onClick={() => step(-1)}
                  position="absolute"
                  left="8px"
                  top="50%"
                  transform="translateY(-50%) rotate(180deg)"
                  color="rgba(255,255,255,.85)"
                  filter="drop-shadow(0 1px 3px rgba(0,0,0,.4))"
                  _hover={{ color: 'white' }}
                  _active={{ transform: 'translateY(-50%) rotate(180deg) scale(0.9)' }}
                  transition="color .15s ease, transform .12s ease"
                >
                  <I.chevRight size={22} />
                </Box>
                <Box
                  as="button"
                  type="button"
                  aria-label="Next product"
                  onClick={() => step(1)}
                  position="absolute"
                  right="8px"
                  top="50%"
                  transform="translateY(-50%)"
                  color="rgba(255,255,255,.85)"
                  filter="drop-shadow(0 1px 3px rgba(0,0,0,.4))"
                  _hover={{ color: 'white' }}
                  _active={{ transform: 'translateY(-50%) scale(0.9)' }}
                  transition="color .15s ease, transform .12s ease"
                >
                  <I.chevRight size={22} />
                </Box>
              </>
            )}
          </Box>

          {showArrows && (
            <Flex justify="center" gap="5px" pt="10px">
              {products.map((_, i) => (
                <Box
                  key={i}
                  w={i === index ? '16px' : '6px'}
                  h="6px"
                  borderRadius="4px"
                  bg={i === index ? 'brass' : 'border'}
                  transition="all .2s ease"
                />
              ))}
            </Flex>
          )}
          {showArrows && (
            <Text textAlign="center" fontSize="10.5px" color="text3" pt="6px">
              Swipe or use arrows for other options
            </Text>
          )}

          <Box p="16px">
            <Text fontSize="15px" fontWeight={700} color="text" lineHeight={1.35}>
              {displayTitle || 'Product'}
            </Text>
            {isVerifiedLive && (
              <Text fontSize="11px" fontWeight={600} color="green.500" mt="2px">
                Verified from your link
              </Text>
            )}

            <Flex align="center" justify="space-between" mt="12px">
              {price != null && (
                <Text fontFamily="mono" fontSize="12.5px" fontWeight={500} color="text3">
                  <Box as="span" fontSize="10px" textTransform="uppercase" letterSpacing=".05em" mr="4px">
                    Listed
                  </Box>
                  {fmt(price)}
                </Text>
              )}
              <Flex
                as="button"
                type="button"
                onClick={() => onSelect(token, title, price, source, thumbnail)}
                align="center"
                justify="center"
                gap="5px"
                bg="brandSoft"
                color="brand"
                fontSize="12px"
                fontWeight={800}
                whiteSpace="nowrap"
                borderRadius="999px"
                px="10px"
                py="7px"
                transition="background .18s ease, color .18s ease"
                _hover={{ bg: 'brand', color: 'onBrand' }}
              >
                <I.trendUp size={13} />
                Find Better Price
                <I.chevRight size={12} />
              </Flex>
            </Flex>
          </Box>
        </Box>
      </motion.div>
    </Box>
  );
}
