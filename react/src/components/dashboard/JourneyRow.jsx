import { Box, Flex, Link, Text } from '@chakra-ui/react';

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
 * One always-visible row in the checklist: icon dot, label, and the action
 * button side by side, with the real facts (price / voucher amounts) and a
 * dismissible hint always shown beneath — nothing is hidden behind a
 * dropdown, since every step's information matters regardless of which step
 * is currently active. Once a step is done, the whole row washes to a soft
 * green rather than only the icon dot changing — deliberately slow (see the
 * `background` transition below) so it reads as a gentle confirmation, not
 * a jarring flip.
 */
export default function JourneyRow({
  tone = 'brand',
  icon: Ico,
  label,
  facts,
  caption,
  link,
  checked = false,
  ready = false,
  pending = false,
  onCheck,
  hintText,
  hintVisible,
  onHideHint,
}) {
  const t = TONES[tone] || TONES.brand;
  const filled = checked || ready;

  return (
    <Box
      bg={filled ? 'brandSoft' : 'transparent'}
      borderRadius="10px"
      px={filled ? '11px' : '0'}
      mx={filled ? '-11px' : '0'}
      transition="background 1.4s ease, padding .3s ease, margin .3s ease"
    >
      <Flex align="center" gap="14px" py="11px">
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

        <Text fontSize="13.5px" fontWeight={700} color="text" flex="1" minW={0}>
          {label}
        </Text>

        {link?.href && (
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
            flex="0 0 auto"
            whiteSpace="nowrap"
            transition="background .2s"
            _hover={{ textDecoration: 'none', bg: checked ? 'brandHover' : 'brandSoft2' }}
          >
            {checked ? '✓ Done' : pending ? 'Confirming…' : link.label}
          </Link>
        )}
      </Flex>

      <Box pl="48px" pb="11px">
        {facts}

        {caption && (
          <Text fontSize="11px" color="text3" mt="6px">
            {caption}
          </Text>
        )}

        {hintVisible && (
          <Flex
            mt="10px"
            bg="brassSoft"
            border="1px solid"
            borderColor="brass"
            borderRadius="xs"
            px="12px"
            py="9px"
            gap="10px"
            align="flex-start"
            justify="space-between"
            fontSize="12px"
            color="text"
            lineHeight={1.45}
          >
            <Text>{hintText}</Text>
            <Box
              as="button"
              type="button"
              onClick={onHideHint}
              flex="0 0 auto"
              fontSize="11px"
              fontWeight={700}
              opacity={0.85}
              textDecoration="underline"
              whiteSpace="nowrap"
              color="brass"
              _hover={{ opacity: 1 }}
              _focusVisible={{ outline: '2px solid currentColor', outlineOffset: '2px', borderRadius: '4px' }}
            >
              Hide
            </Box>
          </Flex>
        )}
      </Box>
    </Box>
  );
}
