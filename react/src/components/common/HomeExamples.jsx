import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import { apiClient } from '@/api/client';
import { track } from '@/utils/analytics';
import { fmt } from '@/utils/format';

/**
 * Six shops with today's real price on a ₹5,000 bill, as a grid of big
 * thumb-sized tiles under the search box. Tapping one runs the search for
 * that shop. Replaced three long rows that were tapped twice in a week
 * (9–14 Nov 2026); owner pick from the 2026-11-14 mockup.
 *
 * Prices come live from /voucher-check, the same check the extension and
 * chat apps use, so they move with every voucher refresh and never promise
 * a number the results page won't show. A shop whose check fails or has no
 * deal is simply left out; if all fail the block doesn't render.
 */
const BILL = 5000;
const EXAMPLES = [
  { label: 'Lifestyle', domain: 'lifestylestores.com', query: 'Lifestyle' },
  { label: 'AJIO', domain: 'ajio.com', query: 'AJIO' },
  { label: 'Nykaa', domain: 'nykaa.com', query: 'Nykaa' },
  { label: 'Myntra', domain: 'myntra.com', query: 'Myntra' },
  { label: 'Croma', domain: 'croma.com', query: 'Croma' },
  { label: 'PVR', domain: 'pvrcinemas.com', query: 'PVR' },
].map((ex) => ({ amount: BILL, ...ex }));

async function priceFor(ex) {
  const { data } = await apiClient.get('/voucher-check', { params: { domain: ex.domain, price: ex.amount } });
  if (!data?.has_voucher) return null;
  const deal = ex.choice
    ? [data, ...(data.product_choices || [])].find((d) => d.choice_label === ex.choice)
    : data;
  if (!deal?.effective_price || deal.remainder > 0) return null;
  const pay = Math.min(deal.effective_price, data.dealo?.you_pay ?? Infinity);
  return pay < ex.amount ? { ...ex, pay: Math.round(pay) } : null;
}

export default function HomeExamples({ onPick }) {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    let alive = true;
    Promise.allSettled(EXAMPLES.map(priceFor)).then((res) => {
      if (alive) setRows(res.map((r) => (r.status === 'fulfilled' ? r.value : null)).filter(Boolean));
    });
    return () => {
      alive = false;
    };
  }, []);

  if (!rows.length) return null;

  // Three to a row; an odd leftover (a shop with no deal today) would sit
  // alone, so drop to the largest multiple of three.
  const shown = rows.length >= 3 ? rows.slice(0, rows.length - (rows.length % 3)) : rows;

  return (
    <Box w="100%" textAlign="left">
      <Text fontSize="11px" fontWeight={700} letterSpacing=".08em" textTransform="uppercase" color="text3" mb="8px">
        Or tap a shop
      </Text>
      <Box display="grid" gridTemplateColumns="repeat(3, minmax(0, 1fr))" gap="8px">
        {shown.map((r) => (
          <Flex
            key={r.label}
            as="button"
            type="button"
            onClick={() => {
              track('Clicked Home Example', { shop: r.label });
              onPick(r.query);
            }}
            direction="column"
            align="center"
            justify="center"
            gap="2px"
            minH="60px"
            px="6px"
            py="10px"
            bg="surface"
            border="1px solid"
            borderColor="border"
            borderRadius="md"
            transition="transform .16s cubic-bezier(0.23, 1, 0.32, 1)"
            _hover={{ borderColor: 'borderStrong' }}
            _active={{ transform: 'scale(0.96)' }}
            _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
          >
            <Text fontSize="14px" fontWeight={700} color="text" noOfLines={1}>
              {r.label}
            </Text>
            <Text fontFamily="mono" fontSize="12px" fontWeight={600} color="green">
              pay {fmt(r.pay)}
            </Text>
          </Flex>
        ))}
      </Box>
      <Text fontSize="12px" color="text3" mt="6px">
        On a {fmt(BILL)} bill, today.
      </Text>
    </Box>
  );
}
