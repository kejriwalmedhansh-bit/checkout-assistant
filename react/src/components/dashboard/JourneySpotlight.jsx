import { Box, Flex, Link, Text } from '@chakra-ui/react';

const TONE = {
  brand: { bg: 'brandSoft', border: 'brand', text: 'brandText' },
  voucher: { bg: 'amberSoft', border: 'amber', text: 'amber' },
  checkout: { bg: 'brandSoft', border: 'brand', text: 'brandText' },
};

/** Small checkmark row for a step that's been superseded by a later one —
 * enough to confirm it happened without competing with the current step. */
export function JourneyDoneRow({ label }) {
  return (
    <Flex
      align="center"
      gap="10px"
      fontSize="12px"
      color="text2"
      bg="surface2"
      border="1px solid"
      borderColor="border"
      borderRadius="xs"
      px="12px"
      py="8px"
      mb="8px"
    >
      <Box as="span" color="brandText" fontWeight={700}>
        ✓
      </Box>
      <Text>{label}</Text>
    </Flex>
  );
}

/**
 * The one expanded, focused card for whichever step is next — everything the
 * old always-visible row showed (price/voucher facts, the action link, the
 * dismissible instructional hint) lives here too, just for a single step at a
 * time instead of three rows competing for attention at once.
 */
export default function JourneySpotlight({
  tone = 'brand',
  stepNumber,
  totalSteps,
  title,
  facts,
  link,
  checked = false,
  ready = false,
  pending = false,
  onCheck,
  hintText,
  hintVisible,
  onHideHint,
}) {
  const t = TONE[tone] || TONE.brand;
  const done = checked || ready;

  return (
    <Box
      border="1px solid"
      borderColor={done ? 'brand' : t.border}
      bg={done ? 'brandSoft' : t.bg}
      borderRadius="sm"
      p="16px 18px"
      transition="background .2s, border-color .2s"
    >
      {totalSteps > 1 && (
        <Text fontSize="10.5px" fontWeight={700} letterSpacing=".06em" textTransform="uppercase" color={done ? 'brandText' : t.text} mb="4px">
          Step {stepNumber} of {totalSteps}
        </Text>
      )}
      <Text fontSize="16px" fontWeight={800} letterSpacing="-.01em" color="text" mb={facts ? '8px' : '14px'}>
        {title}
      </Text>

      {facts}

      {link?.href && (
        <Flex justify="flex-end" mt="14px">
          <Link
            href={link.href}
            isExternal
            onClick={onCheck}
            pointerEvents={pending ? 'none' : 'auto'}
            fontSize="12.5px"
            fontWeight={700}
            color={checked ? 'onBrand' : 'brandText'}
            bg={checked ? 'brand' : 'surface'}
            border="1px solid"
            borderColor="brand"
            borderRadius="99px"
            px="16px"
            py="9px"
            whiteSpace="nowrap"
            transition="background .2s"
            _hover={{ textDecoration: 'none', bg: checked ? 'brandHover' : 'brandSoft2' }}
          >
            {checked ? '✓ Done' : pending ? 'Confirming…' : link.label}
          </Link>
        </Flex>
      )}

      {hintVisible && (
        <Flex
          mt="12px"
          bg="surface"
          border="1px solid"
          borderColor="border"
          borderRadius="xs"
          px="12px"
          py="9px"
          gap="10px"
          align="flex-start"
          justify="space-between"
          fontSize="12px"
          color="text2"
          lineHeight={1.45}
        >
          <Text>{hintText}</Text>
          <Box
            as="button"
            type="button"
            onClick={onHideHint}
            flex="0 0 auto"
            fontSize="11px"
            fontWeight={600}
            opacity={0.75}
            textDecoration="underline"
            whiteSpace="nowrap"
            color="text2"
            _hover={{ opacity: 1 }}
            _focusVisible={{ outline: '2px solid currentColor', outlineOffset: '2px', borderRadius: '4px' }}
          >
            Hide
          </Box>
        </Flex>
      )}
    </Box>
  );
}
