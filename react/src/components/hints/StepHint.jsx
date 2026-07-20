import { Box, Flex, Text } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';

const MotionBox = motion(Box);

/**
 * The small "do this next" bubble that sits under the current unfinished
 * journey step.
 *
 * It appears on every visit rather than once, because the voucher-then-checkout
 * order isn't obvious even to someone who has used Dealo before — and getting
 * it wrong means paying full price. `Journey` decides which step is current and
 * moves this bubble down the list as steps get ticked off, so it always points
 * at something true rather than guessing on a timer.
 *
 * Motion is deliberately restrained: enter 240ms, exit 140ms (leaving faster
 * than arriving reads as responsive rather than sluggish), and the attention
 * ring on the target button pulses three times and then stops — see
 * `JourneyStep`. A permanently animating arrow would make a money app feel like
 * a game at the exact moment someone is about to spend real money.
 */
export default function StepHint({ text, onHide }) {
  const prefersReduced = useReducedMotion();

  return (
    <MotionBox
      initial={prefersReduced ? { opacity: 0 } : { opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={prefersReduced ? { opacity: 0 } : { opacity: 0, y: -4 }}
      transition={{
        duration: prefersReduced ? 0.12 : 0.24,
        ease: [0.16, 1, 0.3, 1],
      }}
      // Aligned past the 34px status dot + 14px gap so the bubble sits under
      // the step's text rather than under its number.
      ml={{ base: '0', sm: '48px' }}
      mb="4px"
      position="relative"
      role="status"
    >
      {/* caret pointing up at the step above */}
      <Box
        position="absolute"
        top="-4px"
        left="18px"
        w="9px"
        h="9px"
        bg="brand"
        transform="rotate(45deg)"
        borderRadius="2px"
      />
      <Flex
        bg="brand"
        color="onBrand"
        borderRadius="sm"
        p="9px 12px"
        gap="10px"
        align="flex-start"
        justify="space-between"
      >
        <Text fontSize="12.5px" lineHeight={1.45} fontWeight={500}>
          {text}
        </Text>
        <Box
          as="button"
          type="button"
          onClick={onHide}
          flex="0 0 auto"
          fontSize="11px"
          fontWeight={600}
          opacity={0.75}
          textDecoration="underline"
          whiteSpace="nowrap"
          mt="1px"
          _hover={{ opacity: 1 }}
          _focusVisible={{ outline: '2px solid currentColor', outlineOffset: '2px', borderRadius: '4px' }}
        >
          Hide
        </Box>
      </Flex>
    </MotionBox>
  );
}
