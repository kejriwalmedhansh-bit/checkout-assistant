import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import { apiClient } from '@/api/client';
import { track } from '@/utils/analytics';
import { fmt } from '@/utils/format';

/**
 * Three real savings on the home page, so a first-time visitor sees what
 * Dealo does before typing anything.
 *
 * Prices come live from /voucher-check, the same check the extension and
 * chat apps use, so they move with every voucher refresh and never promise
 * a number the results page won't show. A shop whose check fails or has no
 * deal is simply left out; if all three fail the block doesn't render.
 */
const EXAMPLES = [
  { label: 'Skechers', domain: 'skechers.in', amount: 6000, query: 'Skechers' },
  { label: 'MakeMyTrip hotel', domain: 'makemytrip.com', amount: 15000, query: 'MakeMyTrip hotel', choice: 'Hotels' },
  { label: 'Lifestyle', domain: 'lifestylestores.com', amount: 5000, query: 'Lifestyle' },
];

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

  return (
    <Box w="100%" textAlign="left">
      <Text fontSize="11px" fontWeight={700} letterSpacing=".08em" textTransform="uppercase" color="text3" mb="8px">
        Today on Dealo
      </Text>
      <Flex direction="column" gap="6px">
        {rows.map((r) => (
          <Flex
            key={r.label}
            as="button"
            type="button"
            onClick={() => {
              track('Clicked Home Example', { shop: r.label });
              onPick(r.query);
            }}
            align="center"
            justify="space-between"
            gap="10px"
            w="100%"
            minH="48px"
            px="14px"
            py="10px"
            bg="surface"
            border="1px solid"
            borderColor="border"
            borderRadius="md"
            textAlign="left"
            transition="transform .16s cubic-bezier(0.23, 1, 0.32, 1)"
            _hover={{ borderColor: 'borderStrong' }}
            _active={{ transform: 'scale(0.98)' }}
            _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
          >
            <Text fontSize="14px" fontWeight={700} color="text" minW={0}>
              {r.label}
            </Text>
            <Flex align="baseline" gap="8px" flex="0 0 auto" fontFamily="mono" fontSize="13px">
              <Text as="s" color="text3">
                {fmt(r.amount)}
              </Text>
              <Text fontWeight={700} color="brand">
                {fmt(r.pay)}
              </Text>
            </Flex>
          </Flex>
        ))}
      </Flex>
      <Text fontSize="12px" color="text3" mt="6px">
        Tap a shop to see how.
      </Text>
    </Box>
  );
}
