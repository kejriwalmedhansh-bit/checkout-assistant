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
 * One row in the vertical recommended-route checklist: a status dot (outline
 * → filled checkmark once done), a label + detail line, and an optional
 * action button that opens the real external link and marks the step done.
 */
export default function JourneyStep({
  tone = 'brand',
  icon: Ico,
  label,
  detail,
  link,
  checked = false,
  ready = false,
  pending = false,
  hinted = false,
  onCheck,
}) {
  const t = TONES[tone] || TONES.brand;
  const filled = checked || ready;

  return (
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

      <Box flex="1" minW={0}>
        <Text fontSize="13px" fontWeight={700} color="text">
          {label}
        </Text>
        {detail && (
          <Text fontSize="11.5px" color="text2" fontFamily="mono" mt="1px">
            {detail}
          </Text>
        )}
      </Box>

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
          position="relative"
          _hover={{ textDecoration: 'none', bg: checked ? 'brandHover' : 'brandSoft2' }}
          // Attention ring for the step the hint is pointing at. Pulses exactly
          // three times and stops — an endlessly animating control reads as a
          // game, which is the wrong feeling right before someone spends money.
          // Suppressed entirely under reduced-motion.
          sx={
            hinted
              ? {
                  '@keyframes dealoHintRing': {
                    '0%': { opacity: 0.85, transform: 'scale(1)' },
                    '70%': { opacity: 0, transform: 'scale(1.22)' },
                    '100%': { opacity: 0, transform: 'scale(1.22)' },
                  },
                  '&::before': {
                    content: '""',
                    position: 'absolute',
                    inset: '-4px',
                    borderRadius: '99px',
                    border: '2px solid',
                    borderColor: 'brand',
                    pointerEvents: 'none',
                    animation: 'dealoHintRing 1s cubic-bezier(.3,.7,.4,1) 3',
                  },
                  '@media (prefers-reduced-motion: reduce)': {
                    '&::before': { animation: 'none', opacity: 0.85 },
                  },
                }
              : undefined
          }
        >
          {checked ? '✓ Done' : pending ? 'Confirming…' : link.label}
        </Link>
      )}
    </Flex>
  );
}

/** Vertical connector line between checklist rows, aligned under the dots. */
export function JourneyConnector() {
  return (
    <Flex align="center" gap="14px">
      <Flex w="34px" flex="0 0 34px" justify="center">
        <Box w="2px" h="16px" bg="borderStrong" />
      </Flex>
      <Box flex="1" />
    </Flex>
  );
}
