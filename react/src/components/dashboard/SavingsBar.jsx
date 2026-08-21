import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * The savings node — the first stop on the same route the steps below
 * continue (see RouteWire, rendered directly under this by ResultsPage).
 * Used to be a full-width hero (a 46px headline on its own); that pushed the
 * actual "what do I do" steps below it far enough down a phone screen that
 * a real user reported not knowing what to do at all. Compact and
 * left-aligned like a chip/row now, so the reward and the action it
 * requires can both sit in view together instead of the reward alone
 * filling the screen. Renders nothing when there is no positive saving.
 *
 * `voucherRequired` used to add a visible "once you complete both steps
 * below" line — that sentence is now conveyed visually by the wire
 * connecting straight into the step card, so sighted users read it from the
 * layout. The same fact is kept as a screen-reader-only line so it isn't
 * lost for anyone who can't see the connector.
 *
 * `cardCashback` folds a selected card's ₹ cashback into the headline
 * number once one's picked — the checkout price itself (`originalPrice` →
 * `finalPrice`) never nets cashback out (that's still just the voucher
 * price), but "YOU SAVE" is the shopper's real total benefit, so it's the
 * voucher discount plus the cashback, with a one-line breakdown underneath
 * so the number isn't a mystery. When there's no voucher discount at all
 * (e.g. the skip-the-voucher path), the headline is cashback alone.
 */
export default function SavingsBar({ originalPrice, finalPrice, saving, cardCashback = 0, voucherRequired = false }) {
  const voucherSaving = saving > 0 ? saving : 0;
  const totalSaving = voucherSaving + (cardCashback || 0);
  if (!totalSaving || totalSaving <= 0) return null;

  const pct = originalPrice ? Math.round((totalSaving / originalPrice) * 100) : null;

  return (
    <Box
      bg="greenSoft"
      border="1.5px solid"
      borderColor="green"
      borderRadius="md"
      borderBottomRadius={0}
      px="14px"
      py="12px"
    >
      <Flex align="center" gap="12px">
        <Flex
          w="40px"
          h="40px"
          flex="0 0 auto"
          borderRadius="50%"
          bg="green"
          color="onBrand"
          align="center"
          justify="center"
        >
          <I.trendUp size={18} />
        </Flex>

        <Box minW={0}>
          <Text fontSize="10px" fontWeight={700} color="green" letterSpacing=".02em">
            YOU SAVE
          </Text>
          <Text
            fontFamily="mono"
            fontSize="22px"
            fontWeight={800}
            color="green"
            lineHeight={1.1}
            letterSpacing="-.01em"
          >
            {fmt(totalSaving)}
          </Text>
          <Flex align="center" gap="6px" fontSize="11px" fontFamily="mono" color="text2">
            <Text as="span" textDecoration="line-through" color="text3">
              {fmt(originalPrice)}
            </Text>
            <Text as="span" color="text3">
              →
            </Text>
            <Text as="span" fontWeight={700} color="text">
              {fmt(finalPrice)}
            </Text>
          </Flex>
          {cardCashback > 0 && (
            <Text fontSize="10.5px" fontFamily="mono" color="text2" mt="2px">
              {voucherSaving > 0 ? `${fmt(voucherSaving)} voucher + ${fmt(cardCashback)} cashback` : `${fmt(cardCashback)} cashback`}
            </Text>
          )}
        </Box>

        {pct != null && pct > 0 && (
          <Box
            as="span"
            ml="auto"
            alignSelf="flex-start"
            fontFamily="mono"
            bg="green"
            color="onBrand"
            fontSize="10.5px"
            fontWeight={700}
            borderRadius="999px"
            px="8px"
            py="3px"
            whiteSpace="nowrap"
          >
            {pct}% off
          </Box>
        )}
      </Flex>

      {voucherRequired && (
        <Box
          position="absolute"
          width="1px"
          height="1px"
          padding="0"
          margin="-1px"
          overflow="hidden"
          whiteSpace="nowrap"
          border="0"
          sx={{ clipPath: 'inset(50%)' }}
        >
          Complete the steps below to get this price.
        </Box>
      )}
    </Box>
  );
}
