import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';

/**
 * Persistent, always-visible outline of the whole journey (Voucher → Cart →
 * Pay), sitting above one step's full detail at a time (see JourneyPanels).
 * This replaces a long vertical stack of fully-expanded steps — real
 * feedback was that scrolling through all three cost real drop-off. The
 * strip alone still tells you the whole sequence and roughly where you are
 * in it, so nothing about "what comes next" is hidden the way an earlier,
 * fully-hidden step-at-a-time version was criticized for; only the deep-dive
 * detail is one-at-a-time, reached by tapping a chip or swiping the panel.
 * Numbered + arrow-linked on purpose, not a flat row of equal tabs — flat
 * tabs read as independent categories, not a sequence to walk in order.
 *
 * The connector right after the active chip nudges rightward on a loop —
 * real users reported not understanding what to do at all, so the sequence
 * gets an actual moving cue pointing at "next," not just a static arrow.
 * Only that one connector animates (everything else stays still) so it
 * reads as "go this way" rather than turning the whole strip busy.
 *
 * A step may carry a `sub` line (e.g. "Buy voucher · ₹92,625"): the chip
 * then becomes a two-line bordered tab naming a place and what's paid there,
 * and both tabs share the row equally.
 */
export default function JourneyChips({ steps, activeIndex, onSelect }) {
  const withSub = steps.some((s) => s.sub);
  return (
    <Flex align="center" gap="2px" mb="10px">
      {steps.map((s, i) => {
        const active = i === activeIndex;
        return (
          <Flex key={s.key} align="center" gap="2px" flex={withSub || i < steps.length - 1 ? '1' : '0 0 auto'} minW="0">
            <Box
              as="button"
              type="button"
              onClick={() => onSelect(i)}
              display="flex"
              alignItems="center"
              gap="6px"
              px="8px"
              py="6px"
              flex="1"
              minW="0"
              borderRadius="10px"
              textAlign="left"
              bg={active ? 'amberSoft' : withSub ? 'surface' : 'transparent'}
              border={withSub ? '1px solid' : undefined}
              borderColor={active ? 'amber' : 'border'}
              opacity={active || s.done ? 1 : 0.75}
              transition="opacity .2s ease, background .2s ease"
              _active={{ transform: 'scale(.97)' }}
              _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
            >
              <Flex
                w={withSub ? '17px' : '20px'}
                h={withSub ? '17px' : '20px'}
                flex={withSub ? '0 0 17px' : '0 0 20px'}
                fontSize="10px"
                fontWeight={800}
                borderRadius="50%"
                align="center"
                justify="center"
                bg={s.done ? 'greenSoft' : active ? 'amber' : 'surface3'}
                color={s.done ? 'green' : active ? 'onBrand' : 'text3'}
                border="1.5px solid"
                borderColor={s.done ? 'green' : active ? 'amber' : 'border'}
              >
                {/* Two-line tabs carry their number here, leaving the width
                    for the place name and amount. */}
                {s.done ? <I.check size={10} /> : withSub ? i + 1 : <s.icon size={11} />}
              </Flex>
              <Box minW="0">
                <Text
                  fontSize="11.5px"
                  fontWeight={800}
                  color={s.done ? 'green' : active ? 'text' : 'text2'}
                  whiteSpace="nowrap"
                  overflow="hidden"
                  textOverflow="ellipsis"
                >
                  {withSub ? s.label : `${i + 1} · ${s.label}`}
                </Text>
                {s.sub && (
                  <Text fontSize="10.5px" color="text2" whiteSpace="nowrap" overflow="hidden" textOverflow="ellipsis" mt="1px">
                    {s.sub}
                  </Text>
                )}
              </Box>
            </Box>
            {i < steps.length - 1 && (
              <Box
                color={s.done ? 'green' : active ? 'amber' : 'border'}
                w="11px"
                h="11px"
                flex="0 0 auto"
                transition="color .25s ease"
                sx={
                  active
                    ? {
                        // Nudges toward the next step a few times, then rests.
                        '@keyframes dealoChipFlow': {
                          '0%, 100%': { opacity: 1, transform: 'translateX(0)' },
                          '50%': { opacity: 0.4, transform: 'translateX(3px)' },
                        },
                        animation: 'dealoChipFlow 1.4s cubic-bezier(0.65, 0, 0.35, 1) .6s 3',
                        '@media (prefers-reduced-motion: reduce)': { animation: 'none', opacity: 1, transform: 'none' },
                      }
                    : undefined
                }
              >
                <I.chevRight size={11} />
              </Box>
            )}
          </Flex>
        );
      })}
    </Flex>
  );
}
