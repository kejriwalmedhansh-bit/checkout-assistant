import { Box, Collapse, Flex, Link, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';

/** Tone → soft circle background + accent color (semantic tokens). */
const TONES = {
  brand: { bg: 'brandSoft', color: 'brand', border: 'brand' },
  voucher: { bg: 'amberSoft', color: 'amber', border: 'amber' },
  checkout: { bg: 'greenSoft', color: 'green', border: 'green' },
};

function CheckIcon(props) {
  return (
    <Box
      as="svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      w="14px"
      h="14px"
      {...props}
    >
      <path d="M5 13l4 4L19 7" />
    </Box>
  );
}

/**
 * Vertical connector between two rows, aligned under the icon dots. Colors
 * in once the row above is done — a real, growing green line rather than a
 * neutral divider — so the checklist reads as one path being walked rather
 * than three independent rows.
 */
export function JourneyConnector({ done = false }) {
  return (
    <Flex align="center" gap="14px">
      <Flex w="34px" flex="0 0 34px" justify="center">
        <Box w="2px" h="12px" bg={done ? 'brand' : 'borderStrong'} transition="background .3s" />
      </Flex>
      <Box flex="1" />
    </Flex>
  );
}

/**
 * One accordion row: a header (icon dot, label, a one-line status, a chevron)
 * that's always visible and always clickable, so every step's existence and
 * rough state is visible at a glance — that's the "connected" part. Only the
 * open row expands into the full detail (the real amounts, the action
 * button, the dismissible hint) — that's what keeps "what do I do right now"
 * to one focused answer instead of three rows all shouting at once. Opening
 * a row is independent of completing it: any row can be inspected regardless
 * of order, it just won't have anything to do until its own turn.
 */
export default function JourneyRow({
  id,
  tone = 'brand',
  icon: Ico,
  label,
  compactStatus,
  facts,
  caption,
  link,
  checked = false,
  ready = false,
  pending = false,
  onCheck,
  isOpen,
  onToggle,
  hintText,
  hintVisible,
  onHideHint,
}) {
  const t = TONES[tone] || TONES.brand;
  const filled = checked || ready;

  return (
    <Box>
      <Flex
        as="button"
        type="button"
        onClick={onToggle}
        id={`journey-header-${id}`}
        aria-expanded={isOpen}
        aria-controls={`journey-panel-${id}`}
        w="100%"
        align="center"
        gap="14px"
        py="11px"
        textAlign="left"
        borderRadius="xs"
        transition="background .15s"
        _hover={{ bg: 'surface2' }}
        _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
      >
        <Flex
          w="34px"
          h="34px"
          flex="0 0 34px"
          borderRadius="50%"
          bg={filled ? 'brand' : t.bg}
          color={filled ? 'onBrand' : t.color}
          border="2px solid"
          borderColor={pending ? 'brand' : filled ? 'brand' : t.border}
          align="center"
          justify="center"
          transition="background .25s ease, border-color .25s ease"
          sx={{
            '@keyframes dealoStepPulse': { '0%, 100%': { opacity: 0.55 }, '50%': { opacity: 1 } },
            '@keyframes dealoStepPop': {
              '0%': { transform: 'scale(.7)' },
              '60%': { transform: 'scale(1.15)' },
              '100%': { transform: 'scale(1)' },
            },
            animation: pending
              ? 'dealoStepPulse .6s ease-in-out infinite'
              : checked
                ? 'dealoStepPop .35s cubic-bezier(.34,1.56,.64,1)'
                : 'none',
          }}
        >
          {checked ? <CheckIcon /> : Ico ? <Ico size={16} /> : null}
        </Flex>

        <Text fontSize="13.5px" fontWeight={700} color="text" flex="1" minW={0} noOfLines={1}>
          {label}
        </Text>

        <Text fontSize="11.5px" color="text2" fontFamily="mono" flex="0 0 auto" display={{ base: 'none', sm: 'block' }}>
          {compactStatus}
        </Text>

        <Box as="span" flex="0 0 auto" color="text3" transform={isOpen ? 'rotate(180deg)' : 'none'} transition="transform .2s">
          <I.chevDown size={16} />
        </Box>
      </Flex>

      <Collapse in={isOpen} animateOpacity>
        <Box id={`journey-panel-${id}`} pl="48px" pb="14px">
          <Box display={{ base: 'block', sm: 'none' }} mb="6px">
            <Text fontSize="11.5px" color="text2" fontFamily="mono">
              {compactStatus}
            </Text>
          </Box>

          {facts}

          {caption && (
            <Text fontSize="11px" color="text3" mt="6px">
              {caption}
            </Text>
          )}

          {link?.href && (
            <Flex mt="12px">
              <Link
                href={link.href}
                isExternal
                onClick={onCheck}
                pointerEvents={pending ? 'none' : 'auto'}
                fontSize="11.5px"
                fontWeight={700}
                color={checked ? 'onBrand' : 'brandText'}
                bg={checked ? 'brand' : 'brandSoft'}
                border="1px solid"
                borderColor="brand"
                borderRadius="99px"
                px="13px"
                py="7px"
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
              mt="10px"
              bg="surface2"
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
      </Collapse>
    </Box>
  );
}
