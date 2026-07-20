import { Box, Flex, Link, ListItem, Text, UnorderedList } from '@chakra-ui/react';

import { fmt, paidForVoucher } from '@/utils/format';

/**
 * Numbered "How to do it" steps for a voucher route, plus an optional
 * "Before you buy" list from the (already backend-cleaned) Gyftr redemption
 * instructions. Renders nothing when the route has no voucher.
 */
export default function HowToSteps({ rec }) {
  const v = rec.voucher || null;
  if (!v) return null;

  const paid = paidForVoucher(v);
  const txnsNeeded = v.upi?.txns_needed || 1;
  const breakdown = v.upi?.denomination_breakdown || [];

  // Gyftr only sells fixed denominations — a customer can't buy one voucher
  // for the full total when more than one denomination is needed, so this
  // must say exactly what to buy, not just the total amount. Singular,
  // natural phrasing when it's just one voucher (the common case).
  const singleVoucher = breakdown.length === 1 && breakdown[0].count === 1;
  const buyLabel =
    breakdown.length > 0 && !singleVoucher
      ? breakdown.map((b) => `${b.count} × ${fmt(b.denom)}`).join(' + ') +
        ` in ${rec.merchant} Gift Vouchers`
      : `a ${fmt(v.upi?.voucher_amount)} ${rec.merchant} Gift Voucher`;

  const steps = [
    <>
      Buy {buyLabel} from{' '}
      <Link href={v.voucher_url} isExternal color="brandText" fontWeight={500}>
        our voucher partner
      </Link>{' '}
      — you pay {fmt(paid)}
    </>,
    ...(txnsNeeded > 1
      ? [
          `You'll need to buy this in ${txnsNeeded} separate purchases (up to ${fmt(
            v.upi?.purchase_cap_per_txn,
          )} each time)`,
        ]
      : []),
    `Add your item to your ${rec.merchant} cart`,
    v.upi?.remainder
      ? `Use the Gift Voucher at checkout — pay the remaining ${fmt(v.upi.remainder)} any way you like`
      : 'Use the Gift Voucher at checkout — it covers your full order',
  ];

  const instructions = v.redemption_instructions || [];

  return (
    // This is the block the customer actually works from while spending money,
    // so it carries a brand-tinted ground and an accent rail rather than
    // sitting in the same neutral surface as everything around it. Amber stays
    // reserved for the "Before you buy" caution below — two accents for two
    // different kinds of important.
    <Box
      bg="brandSoft2"
      border="1px solid"
      borderColor="brandSoft"
      borderLeft="3px solid"
      borderLeftColor="brand"
      borderRadius="sm"
      p="16px 18px"
    >
      {/* A real heading, not the 11px uppercase eyebrow used for card titles —
          the instructions were getting lost against the surrounding text. */}
      <Text fontSize="15px" fontWeight={700} color="brandText" letterSpacing="-.01em">
        How to do it
      </Text>
      <Flex direction="column" gap="11px" mt="12px">
        {steps.map((s, i) => (
          <Flex key={i} gap="12px" align="flex-start">
            <Flex
              w="22px"
              h="22px"
              flex="0 0 auto"
              borderRadius="50%"
              bg="brand"
              color="onBrand"
              align="center"
              justify="center"
              fontSize="11px"
              fontWeight={600}
              mt="1px"
            >
              {i + 1}
            </Flex>
            <Text fontSize="13.5px" color="text" lineHeight={1.55}>
              {s}
            </Text>
          </Flex>
        ))}
      </Flex>

      {instructions.length > 0 && (
        <Box mt="14px" bg="amberSoft" border="1px solid" borderColor="amber" borderRadius="sm" p="12px 14px">
          <Text fontSize="13px" fontWeight={700} color="amber" mb="6px">
            Before you buy
          </Text>
          <UnorderedList spacing="3px" pl="18px" m={0}>
            {instructions.map((line, i) => (
              <ListItem key={i} fontSize="13px" color="text2" lineHeight={1.55}>
                {line}
              </ListItem>
            ))}
          </UnorderedList>
        </Box>
      )}
    </Box>
  );
}
