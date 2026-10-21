import { Box, Button, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * The voucher step when Dealo can sell the voucher itself (through Hubble):
 * the voucher drawn as a gift card, a strip that says why it saves money
 * (you pay less for a card worth more), and one button. Each figure appears
 * once: value on the card, price and saving on the strip.
 */
export default function HubbleVoucherPanel({ offer, onBuy }) {
  const pieces = offer.denominations;
  const several = pieces.length > 1 || pieces[0].count > 1;

  return (
    <Flex direction="column" gap="12px">
      <Box
        borderRadius="20px"
        p="18px"
        color="onBrand"
        bg="text"
        backgroundImage="repeating-linear-gradient(0deg, rgba(255,255,255,.035) 0 1px, transparent 1px 22px)"
        boxShadow="0 24px 50px -18px rgba(16,20,15,.45), 0 2px 6px rgba(16,20,15,.12)"
        minH="168px"
        display="flex"
        flexDirection="column"
        justifyContent="space-between"
      >
        <Flex justify="space-between" align="center">
          <Text fontWeight={700} fontSize="15px" opacity={0.92}>
            {offer.brand_name} Gift Voucher
          </Text>
          <Text as="span" fontFamily="mono" fontWeight={700} fontSize="13px" bg="brass" color="white" borderRadius="pill" px="10px" py="4px">
            {offer.discount_pct}% off
          </Text>
        </Flex>
        <Box>
          <Text fontSize="11px" letterSpacing=".12em" opacity={0.6}>
            {several ? 'VALUE · ' + pieces.map((p) => `${p.count} × ${fmt(p.amount)}`).join(' + ') : 'VALUE'}
          </Text>
          <Text fontFamily="mono" fontWeight={700} fontSize="36px" letterSpacing="-.02em" lineHeight={1.05}>
            {fmt(offer.voucher_total)}
          </Text>
        </Box>
      </Box>

      <Flex bg="greenSoft" border="1.5px solid" borderColor="green" borderRadius="16px" px="14px" py="12px" align="center" gap="10px">
        <Box>
          <Text fontSize="12px" fontWeight={700} letterSpacing=".06em" color="text2">
            YOU PAY
          </Text>
          <Text fontFamily="mono" fontWeight={700} fontSize="22px" lineHeight={1}>
            {fmt(Math.round(offer.you_pay))}
          </Text>
        </Box>
        <Flex flex="1" direction="column" align="center" color="green">
          <I.arrowUp size={18} />
          <Text fontSize="12px" fontWeight={700}>
            for this card
          </Text>
        </Flex>
        <Box textAlign="right">
          <Text fontSize="12px" fontWeight={700} letterSpacing=".06em" color="green">
            YOU SAVE
          </Text>
          <Text fontFamily="mono" fontWeight={700} fontSize="26px" lineHeight={1} color="green">
            {fmt(Math.round(offer.you_save))}
          </Text>
        </Box>
      </Flex>

      {offer.rest_at_shop > 0 && (
        <Text fontSize="13px" color="text2" textAlign="center">
          + {fmt(offer.rest_at_shop)} paid at {offer.brand_name} any way you like
        </Text>
      )}

      <Button
        onClick={onBuy}
        h="56px"
        borderRadius="pill"
        bg="amber"
        color="white"
        fontSize="17px"
        fontWeight={800}
        rightIcon={<I.arrowRight size={18} />}
        _hover={{ bg: 'amber', filter: 'brightness(0.95)' }}
        _active={{ transform: 'scale(0.97)' }}
        transition="transform 120ms cubic-bezier(.23,1,.32,1)"
      >
        Buy voucher
      </Button>
    </Flex>
  );
}
