import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import BrandVoucherCard from '@/components/dashboard/BrandVoucherCard';
import { soldApi } from '@/api/sold.api';
import { soldEventProps, track } from '@/utils/analytics';

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
const HUBBLE_ON = import.meta.env.VITE_HUBBLE_ENABLED === 'true';
const HUBBLE_FORCE = import.meta.env.VITE_HUBBLE_FORCE === 'true';

export default function VoucherChoicePicker({ choices, query }) {
  const [picked, setPicked] = useState(null);
  const shop = shopName(choices);
  // The chip's rate must be the one the card will show. When Dealo sells
  // this voucher itself (Hubble or Maximize) at a different rate from the
  // public listing, the chip shows Dealo's rate (owner's test, 30 Oct 2026:
  // "AJIO 7%" on the chip, 7.65% on the card).
  const [sold, setSold] = useState({});
  useEffect(() => {
    if (!HUBBLE_ON) return undefined;
    let live = true;
    choices.forEach((c) => {
      if (!c.brand_name) return;
      soldApi
        .brand(c.brand_name, HUBBLE_FORCE ? null : c.best_discount_pct)
        .then((res) => {
          if (!live || !res.available) return;
          setSold((prev) => ({ ...prev, [c.brand_name]: res.brand.discount_pct }));
          track('Dealo Voucher Shown', soldEventProps(res.brand, { merchant: c.brand_name, surface: 'choice_chip', bestPct: c.best_discount_pct }));
        })
        .catch(() => {});
    });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [choices.map((c) => c.brand_name).join('|')]);
  const rateOf = (c) => (sold[c.brand_name] != null ? sold[c.brand_name] : c.best_discount_pct);

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
            {rateOf(c) != null && (
              <Text as="span" fontFamily="mono" fontSize="12.5px" color="brand">
                {+Number(rateOf(c)).toFixed(2)}%
              </Text>
            )}
          </Box>
        ))}
      </Flex>
      {picked != null && <BrandVoucherCard voucher={choices[picked]} />}
    </Flex>
  );
}
