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
        color={filled ? 'white' : t.color}
        border="2px solid"
        borderColor={filled ? 'brand' : t.border}
        align="center"
        justify="center"
        transition="background .2s, border-color .2s"
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
          fontSize="11.5px"
          fontWeight={700}
          color={checked ? 'white' : 'brandText'}
          bg={checked ? 'brand' : 'brandSoft'}
          border="1px solid"
          borderColor="brand"
          borderRadius="99px"
          px="13px"
          py="7px"
          flex="0 0 auto"
          whiteSpace="nowrap"
          _hover={{ textDecoration: 'none', bg: checked ? 'brandHover' : 'brandSoft2' }}
        >
          {checked ? '✓ Done' : link.label}
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
