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
 */
export default function JourneyChips({ steps, activeIndex, onSelect }) {
  return (
    <Flex align="center" gap="2px" mb="10px">
      {steps.map((s, i) => {
        const active = i === activeIndex;
        return (
          <Flex key={s.key} align="center" gap="2px" flex={i === steps.length - 1 ? '0 0 auto' : '1'}>
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
              bg={active ? 'amberSoft' : 'transparent'}
              opacity={active || s.done ? 1 : 0.75}
              transition="opacity .2s ease, background .2s ease"
              _active={{ transform: 'scale(.97)' }}
              _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
            >
              <Flex
                w="20px"
                h="20px"
                flex="0 0 20px"
                borderRadius="50%"
                align="center"
                justify="center"
                bg={s.done ? 'greenSoft' : active ? 'amber' : 'surface3'}
                color={s.done ? 'green' : active ? 'onBrand' : 'text3'}
                border="1.5px solid"
                borderColor={s.done ? 'green' : active ? 'amber' : 'border'}
              >
                {s.done ? <I.check size={11} /> : <s.icon size={11} />}
              </Flex>
              <Text fontSize="11.5px" fontWeight={800} color={s.done ? 'green' : active ? 'text' : 'text2'} whiteSpace="nowrap">
                {i + 1} · {s.label}
              </Text>
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
                        '@keyframes dealoChipFlow': {
                          '0%': { opacity: 0, transform: 'translateX(-3px)' },
                          '30%': { opacity: 1, transform: 'translateX(0)' },
                          '70%': { opacity: 1, transform: 'translateX(1px)' },
                          '100%': { opacity: 0, transform: 'translateX(4px)' },
                        },
                        animation: 'dealoChipFlow 1.3s ease-in-out infinite',
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
