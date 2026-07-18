import { useState } from 'react';
import { Box, Button, Collapse, Flex } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import AltItem from './AltItem';

/**
 * "This one not working for you?" — hidden by default. Reveals up to 3
 * alternatives. There are deliberately no "Fastest" / "Max savings" buckets.
 */
export default function AlternativesToggle({ alternatives = [], onSelect, selectedMerchant }) {
  const [open, setOpen] = useState(false);
  const alts = alternatives.slice(0, 3);
  if (alts.length === 0) return null;

  return (
    <Box>
      <Button
        variant="ghost"
        w="100%"
        justifyContent="space-between"
        onClick={() => setOpen((v) => !v)}
        rightIcon={
          <Box as="span" transform={open ? 'rotate(180deg)' : 'none'} transition="transform .2s">
            <I.chevDown size={16} />
          </Box>
        }
        color="text2"
        fontWeight={500}
      >
        {open ? 'Hide other options' : 'This one not working for you?'}
      </Button>
      <Collapse in={open} animateOpacity>
        <Flex direction="column" gap="8px" mt="10px">
          {alts.map((a, i) => (
            <AltItem
              key={`${a.merchant}-${i}`}
              alt={a}
              onSelect={onSelect}
              isSelected={selectedMerchant === a.merchant}
            />
          ))}
        </Flex>
      </Collapse>
    </Box>
  );
}
