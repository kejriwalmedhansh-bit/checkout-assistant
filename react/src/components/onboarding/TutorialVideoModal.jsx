import { useEffect, useRef } from 'react';
import { Box, Text } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';

import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';

/**
 * First-visit popup: a short video walking through paste-a-link → pick the
 * exact listing → buy the Gift Voucher → check out with the store, in place
 * of the old live spotlight tour. Same full-screen backdrop + centered card
 * convention as ProductQuickView, so it reads as a familiar Dealo overlay
 * rather than a foreign modal.
 */
export default function TutorialVideoModal({ onClose }) {
  const prefersReduced = useReducedMotion();
  const containerRef = useRef(null);

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <Box
      ref={containerRef}
      tabIndex={-1}
      position="fixed"
      inset={0}
      zIndex={200}
      bg="rgba(10,12,10,.68)"
      backdropFilter="blur(3px)"
      display="flex"
      alignItems="center"
      justifyContent="center"
      p="20px"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={prefersReduced ? false : { opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        style={{ width: '100%', maxWidth: '520px' }}
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
            as="video"
            src="/tutorial/tutorial.mp4"
            poster="/tutorial/tutorial-poster.jpg"
            controls
            autoPlay
            playsInline
            preload="metadata"
            w="100%"
            display="block"
            bg="black"
            onPlay={() => track('Played Tutorial Video')}
          />

          <Box p="16px">
            <Text fontSize="15px" fontWeight={700} color="text" lineHeight={1.35}>
              How Dealo works
            </Text>
            <Text fontSize="12.5px" color="text2" mt="4px" lineHeight={1.5}>
              Paste a link, pick the exact listing, buy the Gift Voucher, check out with the store — Dealo never sees your card.
            </Text>
          </Box>
        </Box>
      </motion.div>
    </Box>
  );
}
