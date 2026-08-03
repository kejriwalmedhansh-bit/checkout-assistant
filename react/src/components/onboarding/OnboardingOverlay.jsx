import { useEffect, useRef, useState } from 'react';
import { Box, Flex, Image, Text } from '@chakra-ui/react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';
import { ONBOARDING_STEPS } from './steps';

// Below this a swipe/drag is treated as a tap, not a step change.
const SWIPE_THRESHOLD = 60;

/**
 * First-visit walkthrough: a full-screen overlay stepping through real
 * screenshots of the app (search → pick product → route → checkout), built
 * on the same overlay/pagination/swipe pattern as ProductQuickView (the
 * product picker's photo quick-view) so it feels native, not bolted on.
 * `onDismiss` fires exactly once, however the overlay closes (skip, x,
 * escape, click-outside, or finishing the last step) — the caller uses it to
 * mark the tutorial "seen" so it never auto-shows again.
 */
export default function OnboardingOverlay({ onDismiss }) {
  const prefersReduced = useReducedMotion();
  const [stepIndex, setStepIndex] = useState(0);
  const [dragStartX, setDragStartX] = useState(null);
  const containerRef = useRef(null);
  const total = ONBOARDING_STEPS.length;

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  useEffect(() => {
    track('Onboarding Step Viewed', { step_index: stepIndex, step_title: ONBOARDING_STEPS[stepIndex].title });
  }, [stepIndex]);

  const dismiss = (via) => {
    track('Onboarding Dismissed', { via, step_index_at_dismiss: stepIndex });
    onDismiss();
  };

  const step = (dir) => {
    setStepIndex((i) => Math.min(Math.max(i + dir, 0), total - 1));
  };

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') dismiss('escape');
      if (e.key === 'ArrowRight') step(1);
      if (e.key === 'ArrowLeft') step(-1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepIndex]);

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

  const isLast = stepIndex === total - 1;
  const current = ONBOARDING_STEPS[stepIndex];

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
      onClick={(e) => e.target === e.currentTarget && dismiss('click_outside')}
    >
      <motion.div
        initial={prefersReduced ? false : { opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        style={{ width: '100%', maxWidth: '540px' }}
      >
        <Box bg="surface" borderRadius="20px" overflow="hidden" boxShadow="0 40px 80px rgba(0,0,0,.4)" position="relative">
          <Box
            as="button"
            type="button"
            aria-label="Close"
            onClick={() => dismiss('close_button')}
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
            h="320px"
            bg="surface2"
            display="flex"
            alignItems="center"
            justifyContent="center"
            onMouseDown={handlePointerDown}
            onMouseUp={handlePointerUp}
            onTouchStart={handlePointerDown}
            onTouchEnd={handlePointerUp}
            cursor="grab"
            userSelect="none"
          >
            <AnimatePresence mode="wait">
              <motion.div
                key={stepIndex}
                initial={prefersReduced ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                <Image src={current.image} alt={current.alt} maxW="90%" maxH="90%" objectFit="contain" draggable={false} />
              </motion.div>
            </AnimatePresence>

            {stepIndex > 0 && (
              <Box
                as="button"
                type="button"
                aria-label="Previous step"
                onClick={() => step(-1)}
                position="absolute"
                left="8px"
                top="50%"
                transform="translateY(-50%) rotate(180deg)"
                color="brand"
                _hover={{ color: 'brandHover' }}
                _active={{ transform: 'translateY(-50%) rotate(180deg) scale(0.9)' }}
                transition="color .15s ease, transform .12s ease"
              >
                <I.chevRight size={22} />
              </Box>
            )}
            {!isLast && (
              <Box
                as="button"
                type="button"
                aria-label="Next step"
                onClick={() => step(1)}
                position="absolute"
                right="8px"
                top="50%"
                transform="translateY(-50%)"
                color="brand"
                _hover={{ color: 'brandHover' }}
                _active={{ transform: 'translateY(-50%) scale(0.9)' }}
                transition="color .15s ease, transform .12s ease"
              >
                <I.chevRight size={22} />
              </Box>
            )}
          </Box>

          <Flex justify="center" gap="5px" pt="10px">
            {ONBOARDING_STEPS.map((_, i) => (
              <Box
                key={i}
                w={i === stepIndex ? '16px' : '6px'}
                h="6px"
                borderRadius="4px"
                bg={i === stepIndex ? 'brass' : 'border'}
                transition="all .2s ease"
              />
            ))}
          </Flex>

          <Box p="24px">
            <Text fontSize="19px" fontWeight={700} color="text" lineHeight={1.35}>
              {current.title}
            </Text>
            <Text fontSize="15px" color="text2" lineHeight={1.55} mt="6px">
              {current.caption}
            </Text>

            <Flex align="center" justify="space-between" mt="22px">
              <Box
                as="button"
                type="button"
                onClick={() => dismiss('skip')}
                fontSize="13.5px"
                fontWeight={600}
                color="text3"
                _hover={{ color: 'text2' }}
              >
                Skip
              </Box>
              <Flex
                as="button"
                type="button"
                onClick={() => (isLast ? dismiss('completed') : step(1))}
                align="center"
                justify="center"
                gap="6px"
                bg="brand"
                color="onBrand"
                fontSize="14px"
                fontWeight={800}
                whiteSpace="nowrap"
                borderRadius="999px"
                px="20px"
                py="11px"
                transition="background .18s ease"
                _hover={{ bg: 'brandHover' }}
              >
                {isLast ? 'Get started' : 'Next'}
                <I.chevRight size={13} />
              </Flex>
            </Flex>
          </Box>
        </Box>
      </motion.div>
    </Box>
  );
}
