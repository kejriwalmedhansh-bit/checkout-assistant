import { Flex } from '@chakra-ui/react';

/** Tone presets → soft background + accent text color (semantic tokens). */
const TONES = {
  green: { bg: 'greenSoft', color: 'green' },
  brand: { bg: 'brandSoft', color: 'brandText' },
  cyan: { bg: 'cyanSoft', color: 'cyan' },
  amber: { bg: 'amberSoft', color: 'amber' },
  violet: { bg: 'violetSoft', color: 'violet' },
  neutral: { bg: 'surface3', color: 'text2' },
};

/**
 * Pill chip — the design's `.chip`. Use `tone` for a preset, or pass `bg`/`color`
 * explicitly. `mono` (default true) applies the JetBrains Mono treatment.
 */
export default function Chip({ tone, mono = true, children, ...props }) {
  const preset = tone ? TONES[tone] || TONES.neutral : {};
  return (
    <Flex
      as="span"
      align="center"
      gap="6px"
      display="inline-flex"
      fontFamily={mono ? 'mono' : 'body'}
      fontSize="11.5px"
      fontWeight={500}
      letterSpacing=".03em"
      px="10px"
      py="4px"
      borderRadius="9999px"
      whiteSpace="nowrap"
      lineHeight={1.4}
      {...preset}
      {...props}
    >
      {children}
    </Flex>
  );
}
