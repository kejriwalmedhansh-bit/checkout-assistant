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
 */
export default function JourneyChips({ steps, activeIndex, onSelect }) {
  return (
    <Flex align="center" gap="2px" mb="11px">
      {steps.map((s, i) => {
        const active = i === activeIndex;
        const tone = s.done ? 'green' : active ? 'amber' : 'text2';
        const toneSoft = s.done ? 'greenSoft' : active ? 'amberSoft' : 'surface3';
        return (
          <Flex key={s.key} align="center" gap="2px" flex={i === steps.length - 1 ? '0 0 auto' : '1'}>
            <Box
              as="button"
              type="button"
              onClick={() => onSelect(i)}
              display="flex"
              flexDirection="column"
              alignItems="center"
              gap="3px"
              px="8px"
              py="8px"
              flex="1"
              minW="0"
              borderRadius="10px"
              border="1.5px solid"
              borderColor={s.done ? 'green' : active ? 'amber' : 'border'}
              bg={toneSoft}
              opacity={active || s.done ? 1 : 0.65}
              transition="border-color .2s ease, background .2s ease, opacity .2s ease"
              _active={{ transform: 'scale(.97)' }}
              _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
            >
              <Box w="18px" h="18px" color={tone}>
                {s.done ? <I.check size={18} /> : <s.icon size={18} />}
              </Box>
              <Text fontSize="10.5px" fontWeight={700} color={s.done ? 'green' : active ? 'text' : 'text2'} whiteSpace="nowrap">
                {i + 1} · {s.label}
              </Text>
            </Box>
            {i < steps.length - 1 && (
              <Box color={s.done ? 'green' : 'border'} w="13px" h="13px" flex="0 0 auto" transition="color .25s ease">
                <I.chevRight size={13} />
              </Box>
            )}
          </Flex>
        );
      })}
    </Flex>
  );
}
