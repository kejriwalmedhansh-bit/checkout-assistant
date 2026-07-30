import { useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

/**
 * A short line with a small tappable "i" that reveals the fuller
 * explanation beneath it. Used anywhere copy was trimmed down to a phrase —
 * the longer justification isn't gone, just one tap away instead of always
 * on screen. Purely local, uncontrolled state: each note remembers its own
 * open/closed state independently.
 */
export default function InfoNote({ short, full, fontSize = '12.5px', color = 'text3', fontWeight, mt = '4px' }) {
  const [open, setOpen] = useState(false);
  return (
    <Box mt={mt}>
      <Flex align="baseline" gap="6px">
        <Text fontSize={fontSize} color={color} fontWeight={fontWeight}>
          {short}
        </Text>
        <Box
          as="button"
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label="More detail"
          flex="0 0 auto"
          w="15px"
          h="15px"
          borderRadius="50%"
          border="1px solid"
          borderColor="border"
          bg={open ? 'brand' : 'surface3'}
          color={open ? 'onBrand' : 'text3'}
          fontSize="9.5px"
          fontWeight={700}
          fontStyle="italic"
          fontFamily="serif"
          display="inline-flex"
          alignItems="center"
          justifyContent="center"
          lineHeight="1"
          transition="background .12s ease, color .12s ease"
          _hover={{ bg: open ? 'brandHover' : 'brandSoft', color: open ? 'onBrand' : 'brand' }}
          _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
        >
          i
        </Box>
      </Flex>
      {open && (
        <Text
          mt="6px"
          fontSize="12px"
          color="text"
          bg="surface3"
          borderLeft="2px solid"
          borderColor="brand"
          borderRadius="xs"
          px="10px"
          py="8px"
        >
          {full}
        </Text>
      )}
    </Box>
  );
}
