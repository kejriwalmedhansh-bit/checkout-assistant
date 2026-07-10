import { Box, Flex, Link, Text } from '@chakra-ui/react';

/** Tone → soft circle background + accent color (semantic tokens). */
const TONES = {
  brand: { bg: 'orangeSoft', color: 'orange', border: 'orange' },
  voucher: { bg: 'amberSoft', color: 'amber', border: 'amber' },
  checkout: { bg: 'greenSoft', color: 'green', border: 'green' },
};

/**
 * One node in the recommended-route journey: a colored icon circle, a label, a
 * detail line, a price line, and an optional external link button.
 */
export default function JourneyStep({ tone = 'brand', icon: Ico, label, detail, price, link }) {
  const t = TONES[tone] || TONES.brand;

  return (
    <Flex direction="column" align="center" gap="7px" flex={1} minW="90px" textAlign="center">
      <Flex
        w="52px"
        h="52px"
        borderRadius="50%"
        bg={t.bg}
        color={t.color}
        border="1.5px solid"
        borderColor={t.border}
        align="center"
        justify="center"
      >
        {Ico && <Ico size={22} />}
      </Flex>
      <Text fontSize="12px" fontWeight={600} color="text">
        {label}
      </Text>
      {detail && (
        <Text fontSize="11px" color="text2" lineHeight={1.4}>
          {detail}
        </Text>
      )}
      {price && (
        <Text fontSize="13px" fontWeight={600} color={t.color}>
          {price}
        </Text>
      )}
      {link?.href && (
        <Link
          href={link.href}
          isExternal
          fontSize="11px"
          fontWeight={500}
          color="orangeText"
          bg="orangeSoft"
          border="1px solid"
          borderColor="orange"
          borderRadius="6px"
          px="8px"
          py="3px"
          _hover={{ textDecoration: 'none', bg: 'orangeSoft2' }}
        >
          {link.label}
        </Link>
      )}
    </Flex>
  );
}

/** Small arrow connector between journey nodes. */
export function JourneyConnector() {
  return (
    <Box
      alignSelf="flex-start"
      mt="25px"
      flex="0 0 20px"
      h="1.5px"
      bg="borderStrong"
      position="relative"
      _after={{
        content: '""',
        position: 'absolute',
        right: '-4px',
        top: '-3.5px',
        border: '4px solid transparent',
        borderLeftColor: 'var(--chakra-colors-borderStrong)',
      }}
    />
  );
}
