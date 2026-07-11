import { Box, Flex, Link, ListItem, Text, UnorderedList } from '@chakra-ui/react';

import Eyebrow from '@/components/common/Eyebrow';
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

  const steps = [
    <>
      Buy a {fmt(v.upi?.voucher_amount)} {rec.merchant} voucher on{' '}
      <Link href={v.voucher_url} isExternal color="orangeText" fontWeight={500}>
        Gyftr
      </Link>{' '}
      using UPI — you pay {fmt(paid)}
    </>,
    ...(txnsNeeded > 1
      ? [
          `Buy in ${txnsNeeded} separate Gyftr transactions (${fmt(
            v.upi?.purchase_cap_per_txn,
          )} cap per transaction)`,
        ]
      : []),
    `Add your item to your ${rec.merchant} cart`,
    v.upi?.remainder
      ? `Apply the voucher at checkout — pay the remaining ${fmt(v.upi.remainder)} with any method`
      : 'Apply the voucher at checkout — your full order is covered',
  ];

  const instructions = v.redemption_instructions || [];

  return (
    <Box bg="surface2" border="1px solid" borderColor="border" borderRadius="sm" p="14px 18px">
      <Eyebrow>How to do it</Eyebrow>
      <Flex direction="column" gap="10px" mt="12px">
        {steps.map((s, i) => (
          <Flex key={i} gap="12px" align="flex-start">
            <Flex
              w="22px"
              h="22px"
              flex="0 0 auto"
              borderRadius="50%"
              bg="orange"
              color="white"
              align="center"
              justify="center"
              fontSize="11px"
              fontWeight={600}
              mt="1px"
            >
              {i + 1}
            </Flex>
            <Text fontSize="13px" color="text2" lineHeight={1.5}>
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
