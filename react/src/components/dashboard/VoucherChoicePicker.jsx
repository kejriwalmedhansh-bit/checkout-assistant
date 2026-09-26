import { useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import BrandVoucherCard from '@/components/dashboard/BrandVoucherCard';
import { track } from '@/utils/analytics';

// "MakeMyTrip" from "MakeMyTrip Hotel e-Pay", "MakeMyTrip Cab"... — the first
// word every card name shares, spelled as in the shortest name. Same rule as
// the WhatsApp bot's _shop_name.
function shopName(choices) {
  const firsts = choices.map((c) => (c.brand_name || '').trim().split(/[\s-]+/)[0]);
  if (firsts[0] && new Set(firsts.map((f) => f.toLowerCase())).size === 1) {
    const shortest = choices.reduce((a, c, i) => ((c.brand_name || '').length < (choices[a].brand_name || '').length ? i : a), 0);
    return firsts[shortest];
  }
  return choices[0].brand_name || '';
}

/**
 * Shops like MakeMyTrip sell a different voucher for hotels, cabs, flights…
 * The shopper says what they're buying before any voucher is shown, the same
 * question the extension asks — nothing is pre-picked, so nobody booking a
 * flight lands on the hotels-only card by default. Choices come best rate
 * first from POST /search (`voucher_choices`).
 */
export default function VoucherChoicePicker({ choices, query }) {
  const [picked, setPicked] = useState(null);
  const shop = shopName(choices);

  const pick = (i) => {
    setPicked(i);
    track('Voucher Type Picked', { query, choice: choices[i].choice_label, brand: choices[i].brand_name });
  };

  return (
    <Flex direction="column" gap="14px">
      <Box>
        <Text fontSize="17px" fontWeight={800} color="text">What are you buying?</Text>
        <Text fontSize="12.5px" color="text3" mt="2px">{shop} has a different voucher for each</Text>
      </Box>
      <Flex wrap="wrap" gap="6px" role="group" aria-label={`${shop} voucher types`}>
        {choices.map((c, i) => (
          <Box
            as="button"
            type="button"
            key={`${c.brand_name}-${c.voucher_source}`}
            onClick={() => pick(i)}
            aria-pressed={picked === i}
            display="inline-flex"
            alignItems="baseline"
            gap="6px"
            px="12px"
            py="8px"
            minH="40px"
            borderRadius="999px"
            border="1px solid"
            borderColor={picked === i ? 'amber' : 'border'}
            bg={picked === i ? 'amberSoft' : 'surface'}
            fontSize="14px"
            fontWeight={600}
            color="text"
            cursor="pointer"
            transition="background .15s, border-color .15s"
            _hover={{ borderColor: 'amber' }}
            _focusVisible={{ outline: '2px solid', outlineColor: 'amber', outlineOffset: '2px' }}
          >
            {c.choice_label}
            {c.best_discount_pct != null && (
              <Text as="span" fontFamily="mono" fontSize="12.5px" color="brand">
                {+Number(c.best_discount_pct).toFixed(2)}%
              </Text>
            )}
          </Box>
        ))}
      </Flex>
      {picked != null && <BrandVoucherCard voucher={choices[picked]} />}
    </Flex>
  );
}
