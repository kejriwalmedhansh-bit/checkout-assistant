import { Box, Flex, Link, SimpleGrid, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { outboundLink, track } from '@/utils/analytics';

const SOURCE_LABELS = { maximize: 'Maximize', buyhatke: 'BuyHatke', gyftr: 'Gyftr' };

/**
 * A search Dealo can't price as a product (`mode: "voucher_group"` from POST
 * /search): a shop we have no gift card for ("No DMart deal yet") or a
 * grocery item. Shows the gift cards for that kind of shopping, best rate
 * first; each card goes straight to the site that sells it.
 */
export default function VoucherGroupCards({ headline, line, cards, group, query }) {
  return (
    <Flex direction="column" gap="14px">
      <Box>
        <Text as="h2" fontSize="17px" fontWeight={800} color="text" m={0}>{headline}</Text>
        {line && <Text fontSize="13px" color="text2" mt="2px">{line}</Text>}
      </Box>
      <SimpleGrid columns={2} spacing="10px">
        {cards.map((c) => {
          const link = c.voucher_url ? outboundLink(c.voucher_url, 'voucher_site', 'voucher_group_card') : null;
          return (
            <Card key={`${c.brand_name}-${c.voucher_source}`} p="14px" display="flex" flexDirection="column" gap="8px" minW={0}>
              <Flex align="center" gap="8px" minW={0}>
                <Flex w="30px" h="30px" flex="0 0 auto" borderRadius="8px" bg="amberSoft" color="amber" align="center" justify="center">
                  <I.ticket size={16} />
                </Flex>
                <Text fontSize="13.5px" fontWeight={700} color="text" lineHeight="1.2" overflowWrap="anywhere">
                  {c.choice_label || c.brand_name}
                </Text>
              </Flex>
              <Box>
                <Text fontFamily="mono" fontSize="22px" fontWeight={700} color="amber" lineHeight={1}>
                  {+Number(c.best_discount_pct).toFixed(2)}%
                </Text>
                <Text fontSize="11.5px" color="text3" mt="3px">
                  off · via {SOURCE_LABELS[c.voucher_source] || 'Gyftr'}
                </Text>
              </Box>
              {link && (
                <Link
                  href={link}
                  isExternal
                  onClick={() => track('Clicked Brand Voucher Link', { query, brand: c.brand_name, group, discount_pct: c.best_discount_pct })}
                  mt="auto"
                  display="inline-flex"
                  alignItems="center"
                  justifyContent="center"
                  gap="4px"
                  bg="amber"
                  color="onBrand"
                  fontSize="13px"
                  fontWeight={700}
                  borderRadius="9px"
                  py="9px"
                  minH="40px"
                  _hover={{ textDecoration: 'none', opacity: 0.92 }}
                >
                  Buy gift card
                  <I.arrowRight size={14} />
                </Link>
              )}
            </Card>
          );
        })}
      </SimpleGrid>
      <Text fontSize="12.5px" color="text3">Buy the amount you need, then use it at that shop&rsquo;s checkout.</Text>
    </Flex>
  );
}
