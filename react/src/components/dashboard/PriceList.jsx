import { useEffect, useState } from 'react';
import { Box, Button, Flex, Link, Text } from '@chakra-ui/react';

import BrandAvatar from '@/components/common/BrandAvatar';
import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';
import { affiliateUrl, fmt } from '@/utils/format';
import { shopIcon, shortDelivery } from '@/utils/priceList';

const ROWS_SHOWN = 4;

/** Shop icon on a white disc, so dark and light icons both read on either theme. */
function ShopLogo({ shop }) {
  return (
    <Flex
      w="34px"
      h="34px"
      borderRadius="full"
      bg="white"
      border="1px solid"
      borderColor="border"
      boxShadow="0 1px 3px rgba(18,21,26,.10)"
      align="center"
      justify="center"
      overflow="hidden"
      gridRow="1 / span 2"
    >
      <BrandAvatar name={shop.merchant} size={22} radius="6px" logoSrc={shopIcon(shop.link)} />
    </Flex>
  );
}

/**
 * Shown instead of the gift card steps when the gift card saves too little
 * to be worth the extra steps (see shouldShowPriceList). Every shop checked,
 * cheapest first and largest, with a bar for how much more each costs.
 * Each row opens that shop (the arrow on the right says so); the shopper
 * picks, so there is no single "Go to" button. A shop's gift card stays
 * reachable as a small tag on its own row, which opens the usual gift card
 * view via onPickGiftCard.
 */
export default function PriceList({ shops, onPickGiftCard }) {
  const [showAll, setShowAll] = useState(false);
  const best = shops[0];
  const priciest = shops.reduce((hi, s) => (s.price > hi.price ? s : hi), best);
  const span = priciest.price - best.price || 1;
  const ties = shops.filter((s) => s.price === best.price).length;
  const rows = showAll ? shops : shops.slice(0, ROWS_SHOWN);
  const hidden = shops.length - rows.length;

  useEffect(() => {
    track('Price List Shown', { shops: shops.length, cheapest: best.merchant, spread: priciest.price - best.price });
    // Once per result, not per re-render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [best.merchant, best.price, shops.length]);

  const note =
    priciest.price > best.price
      ? `${fmt(priciest.price - best.price)} less than ${priciest.merchant}`
      : ties > 1
        ? `Same price at ${ties} shops`
        : null;

  return (
    <Flex direction="column" gap="10px">
      <Card px="14px" pt="12px" pb="4px">
        <Text fontSize="11px" fontWeight={700} letterSpacing=".06em" textTransform="uppercase" color="brand">
          Cheapest first · {shops.length} shops checked
        </Text>
        {note && (
          <Text fontSize="12px" color="text2" mt="2px" mb="2px">
            {note}
          </Text>
        )}
        {rows.map((s, i) => {
          const diff = s.price - best.price;
          const gc = s.voucher && s.voucherRoute ? Math.round(s.price - s.voucherRoute.final_cost) : 0;
          return (
            <Box key={s.merchant} borderTop={i ? '1px solid' : 'none'} borderColor="border" py={i ? '9px' : '10px'}>
              <Link
                href={s.link ? affiliateUrl(s.link, 'price_list') : undefined}
                isExternal
                onClick={() => track('Clicked Price List Shop', { merchant: s.merchant, rank: i + 1 })}
                role="group"
                display="grid"
                gridTemplateColumns="34px 1fr auto 16px"
                columnGap="10px"
                rowGap="3px"
                alignItems="center"
                _hover={{ textDecoration: 'none' }}
              >
                <ShopLogo shop={s} />
                <Text fontSize={i ? '14px' : '16px'} fontWeight={i ? 600 : 700} color="text" noOfLines={1}>
                  {s.merchant}
                </Text>
                <Text fontFamily="mono" fontSize={i ? '14px' : '22px'} fontWeight={700} color="text" textAlign="right">
                  {fmt(s.price)}
                </Text>
                <Box gridColumn="4" gridRow="1 / span 3" color="text3" _groupHover={{ color: 'brand' }} aria-hidden>
                  <I.chevRight size={16} />
                </Box>
                <Flex gridColumn="2 / 4" align="center" gap="8px" minW={0}>
                  <Box flex="1" h="4px" bg="surface3" borderRadius="2px" overflow="hidden" minW="30px">
                    <Box
                      h="100%"
                      w={diff ? `${Math.max(6, (diff / span) * 100)}%` : '100%'}
                      bg={diff ? 'borderStrong' : 'brand'}
                      borderRadius="2px"
                    />
                  </Box>
                  <Text fontFamily="mono" fontSize="11px" fontWeight={600} color={diff ? 'text3' : 'brand'} flex="0 0 auto">
                    {diff ? `+${fmt(diff)}` : i === 0 ? 'Cheapest' : 'Same price'}
                  </Text>
                </Flex>
                {s.delivery && (
                  <Text gridColumn="2 / 4" fontSize="11px" color="text3" noOfLines={1}>
                    {shortDelivery(s.delivery)}
                  </Text>
                )}
              </Link>
              {gc > 0 && (
                <Box
                  as="button"
                  type="button"
                  onClick={() => {
                    track('Clicked Price List Gift Card', { merchant: s.merchant, saving: gc });
                    onPickGiftCard(s.voucherRoute);
                  }}
                  ml="44px"
                  mt="5px"
                  fontSize="11px"
                  fontWeight={600}
                  color="amber"
                  bg="amberSoft"
                  borderRadius="pill"
                  px="8px"
                  py="2px"
                  _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
                >
                  −{fmt(gc)} with {s.voucher.offline_only ? 'in-store ' : ''}Gift Voucher ›
                </Box>
              )}
            </Box>
          );
        })}
      </Card>

      {hidden > 0 && (
        <Button variant="ghost" size="sm" color="text2" fontWeight={500} onClick={() => setShowAll(true)}>
          Show {hidden} more shop{hidden > 1 ? 's' : ''}
        </Button>
      )}

    </Flex>
  );
}
