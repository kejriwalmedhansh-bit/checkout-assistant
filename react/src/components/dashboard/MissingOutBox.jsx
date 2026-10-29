import { useState } from 'react';
import { Box, Flex, Link, Text } from '@chakra-ui/react';

import { track } from '@/utils/analytics';
import { fmt } from '@/utils/format';
import { applyLink, CARD_CHOICES, choiceFor } from '@/utils/myCards';
import { shopLogos } from '@/utils/priceList';

/**
 * For a shopper without the card: one box under the top deal, shown only
 * when that card would really beat it (myCards.missingOut). "Have an HDFC
 * credit card? Flipkart would be ₹1,28,900 (₹6,000 off) · Apply now".
 */
export default function MissingOutBox({ deal, cheapest }) {
  const [logoFailed, setLogoFailed] = useState(false);
  if (!deal) return null;
  const { shop, offer, pay } = deal;
  const site = CARD_CHOICES.find((c) => c.id === choiceFor(offer.bank))?.site;
  const link = applyLink(offer);
  return (
    <Flex align="center" gap="12px" bg="surface" border="1px solid" borderColor="border" borderRadius="14px" px="14px" py="12px">
      {site && !logoFailed && (
        <Box as="img" src={shopLogos(`https://${site}`)[0]} alt="" w="32px" h="32px" borderRadius="full" border="1px solid" borderColor="border" flex="0 0 auto" onError={() => setLogoFailed(true)} />
      )}
      <Box flex="1" minW={0}>
        <Text fontSize="14px" fontWeight={700} color="text">
          Have {/^(hdfc|sbi|icici|axis|hsbc|idfc|au|rbl)/i.test(offer.bank) ? 'an' : 'a'} {offer.bank} credit card?
        </Text>
        <Text fontSize="13px" color="text2" mt="1px">
          {shop.merchant} would be{' '}
          <Text as="span" fontFamily="mono" fontWeight={700} color="text">
            {fmt(pay)}
          </Text>
          , {fmt(cheapest - pay)} less than the deal above{offer.cashback ? ' (as cashback)' : ''}
        </Text>
      </Box>
      {link && (
        <Link
          href={link}
          isExternal
          onClick={() => track('Clicked Apply For Card', { merchant: shop.merchant, bank: offer.bank, saving: offer.saving })}
          flex="0 0 auto"
          bg="brand"
          color="white"
          fontSize="13px"
          fontWeight={700}
          px="12px"
          py="8px"
          borderRadius="10px"
          _hover={{ textDecoration: 'none', opacity: 0.92 }}
        >
          Apply now ›
        </Link>
      )}
    </Flex>
  );
}
