import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Link, Text } from '@chakra-ui/react';

import BrandAvatar from '@/components/common/BrandAvatar';
import Card from '@/components/common/Card';
import CardPicker from '@/components/dashboard/CardPicker';
import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';
import { affiliateUrl, fmt } from '@/utils/format';
import { applyLink, bestRealOffer, CARD_CHOICES, loadMyCards, myBestOffer, saveMyCards, worthAsking } from '@/utils/myCards';
import { shopLogos, shortDelivery } from '@/utils/priceList';

const ROWS_SHOWN = 4;

// Sizes by how many shops are on screen. A short list would leave half the
// phone empty, so with 2-4 shops each card grows to share the screen; from
// 5 shops the list fills it anyway and keeps the compact size.
const SIZES = {
  2: { logo: 52, name: 18, price: 20, top: 26, bar: 8, small: 13 },
  3: { logo: 46, name: 17, price: 18, top: 24, bar: 6, small: 12 },
  4: { logo: 40, name: 15.5, price: 16, top: 22, bar: 5, small: 11.5 },
};
const COMPACT = { logo: 34, name: 14, price: 14, top: 22, bar: 4, small: 11 };
// Room left under the cards for the WhatsApp button and the phone's own bar.
const BOTTOM_ROOM = 84;
// On a laptop a card never stretches past this, so the list stays tidy;
// on a phone the cards always reach the bottom.
const MAX_CARD_H = 190;
const LAPTOP_W = 992;

/** Shop logo on a white disc. Brandfetch's square icon fills the disc;
 * if it is missing, the site's favicon sits inside it; failing both, the
 * shop's initials. */
function ShopLogo({ shop, size }) {
  const sources = shopLogos(shop.link);
  const [tries, setTries] = useState(0);
  const src = sources[tries];
  const filled = tries === 0;
  return (
    <Flex
      w={`${size}px`}
      h={`${size}px`}
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
      {src ? (
        <Box
          as="img"
          src={src}
          alt={`${shop.merchant} logo`}
          loading="lazy"
          decoding="async"
          w={filled ? '100%' : '22px'}
          h={filled ? '100%' : '22px'}
          objectFit={filled ? 'cover' : 'contain'}
          onError={() => setTries((t) => t + 1)}
        />
      ) : (
        <BrandAvatar name={shop.merchant} size={size} radius="999px" />
      )}
    </Flex>
  );
}

/**
 * Shown instead of the gift card steps when the gift card saves too little
 * to be worth the extra steps (see shouldShowPriceList). Every shop checked,
 * cheapest first and largest, one card per shop (the cheapest outlined),
 * with a bar for how much more each costs. With few shops the cards share
 * the screen down to the bottom instead of leaving it empty.
 * Each row opens that shop (the arrow on the right says so); the shopper
 * picks, so there is no single "Go to" button. A shop's gift card stays
 * reachable as a small tag on its own row, which opens the usual gift card
 * view via onPickGiftCard.
 */
export default function PriceList({ shops: listed, onPickGiftCard, afterFirst = null }) {
  const [showAll, setShowAll] = useState(false);
  // Banks the shopper has cards from: null until asked, [] for "None".
  const [myCards, setMyCards] = useState(loadMyCards);
  const [picking, setPicking] = useState(false);
  const ask = picking || (myCards === null && worthAsking(listed));
  // What this shopper pays: their card's offer comes off, and the order
  // follows that (owner's call 2026-10-27, replacing the card-free order).
  const shops = listed
    .map((s) => {
      const mine = myBestOffer(s, myCards);
      return { ...s, listPrice: s.price, mine, price: s.price - (mine?.saving || 0) };
    })
    .sort((a, b) => a.hyperlocal - b.hyperlocal || a.price - b.price);
  const topReal = listed.map(bestRealOffer).filter(Boolean).sort((a, b) => b.saving - a.saving)[0];
  const myLabel = (myCards || []).map((id) => CARD_CHOICES.find((c) => c.id === id)?.label).filter(Boolean).join(', ');
  const pick = (ids) => {
    saveMyCards(ids);
    setMyCards(ids);
    setPicking(false);
    setShowAll(false);
    track('Picked My Cards', { cards: ids.join(',') || 'none' });
  };
  const best = shops[0];
  const priciest = shops.reduce((hi, s) => (s.price > hi.price ? s : hi), best);
  const span = priciest.price - best.price || 1;
  const ties = shops.filter((s) => s.price === best.price).length;
  const rows = showAll ? shops : shops.slice(0, ROWS_SHOWN);
  const hidden = shops.length - rows.length;
  const sz = SIZES[shops.length] || COMPACT;
  const grow = !!SIZES[shops.length];

  // Fill from where the cards start down to the bottom of the screen.
  const stackRef = useRef(null);
  const [fillH, setFillH] = useState(null);
  useLayoutEffect(() => {
    if (!grow) return setFillH(null);
    const measure = () => {
      const top = stackRef.current?.getBoundingClientRect().top ?? 0;
      const room = window.innerHeight - top - BOTTOM_ROOM;
      setFillH(window.innerWidth >= LAPTOP_W ? Math.min(rows.length * MAX_CARD_H, room) : room);
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [grow, rows.length]);

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
      <Box px="2px">
        <Text fontSize="11px" fontWeight={700} letterSpacing=".06em" textTransform="uppercase" color="brand">
          Cheapest first · {shops.length} shops checked
        </Text>
        {note && (
          <Text fontSize="12px" color="text2" mt="2px">
            {note}
          </Text>
        )}
        {myCards !== null && !ask && (
          <Text fontSize="12px" color="text2" mt="2px">
            {myCards.length ? `With your ${myLabel} card${myCards.length > 1 ? 's' : ''}` : 'No credit card offers added'} ·{' '}
            <Box as="button" type="button" color="brand" fontWeight={600} onClick={() => setPicking(true)}>
              Change
            </Box>
          </Text>
        )}
      </Box>
      {ask && <CardPicker initial={myCards || []} topSaving={topReal && fmt(topReal.saving)} onDone={pick} />}
      <Flex ref={stackRef} direction="column" gap="8px" minH={fillH ? `${fillH}px` : undefined}>
        {rows.map((s, i) => {
          const diff = s.price - best.price;
          const gc = s.voucher && s.voucherRoute ? Math.round(s.listPrice - s.voucherRoute.final_cost) : 0;
          const other = !s.mine && myCards !== null && !ask ? bestRealOffer(s) : null;
          const first = i === 0;
          return (
            <Fragment key={s.merchant}>
            <Card
              flex={grow ? '1' : undefined}
              display="flex"
              flexDirection="column"
              justifyContent="center"
              px="14px"
              py="10px"
              border={first ? '1.5px solid' : '1px solid'}
              borderColor={first ? 'brand' : 'border'}
            >
              <Link
                href={s.link ? affiliateUrl(s.link, 'price_list') : undefined}
                isExternal
                onClick={() => track('Clicked Price List Shop', { merchant: s.merchant, rank: i + 1 })}
                role="group"
                display="grid"
                gridTemplateColumns={`${sz.logo}px 1fr auto 16px`}
                columnGap="10px"
                rowGap="4px"
                alignItems="center"
                _hover={{ textDecoration: 'none' }}
              >
                <ShopLogo shop={s} size={sz.logo} />
                <Text fontSize={`${first ? sz.name + 1 : sz.name}px`} fontWeight={first ? 700 : 600} color="text" noOfLines={1}>
                  {s.merchant}
                </Text>
                <Text fontFamily="mono" fontSize={`${first ? sz.top : sz.price}px`} fontWeight={700} color="text" textAlign="right">
                  {fmt(s.price)}
                </Text>
                <Box gridColumn="4" gridRow="1 / span 3" color="text3" _groupHover={{ color: 'brand' }} aria-hidden>
                  <I.chevRight size={16} />
                </Box>
                <Flex gridColumn="2 / 4" align="center" gap="8px" minW={0}>
                  <Box flex="1" h={`${sz.bar}px`} bg="surface3" borderRadius="3px" overflow="hidden" minW="30px">
                    <Box
                      h="100%"
                      w={diff ? `${Math.max(6, (diff / span) * 100)}%` : '100%'}
                      bg={diff ? 'borderStrong' : 'brand'}
                      borderRadius="3px"
                    />
                  </Box>
                  <Text fontFamily="mono" fontSize={`${sz.small}px`} fontWeight={600} color={diff ? 'text3' : 'brand'} flex="0 0 auto">
                    {diff ? `+${fmt(diff)}` : first ? 'Cheapest' : 'Same price'}
                  </Text>
                </Flex>
                {s.delivery && (
                  <Text gridColumn="2 / 4" fontSize={`${sz.small}px`} color="text3" noOfLines={1}>
                    {shortDelivery(s.delivery)}
                  </Text>
                )}
              </Link>
              {/* Owner's call 2026-10-26: a card offer replaces the Gift Voucher
                  tag on that row; both at once was too much to take in. */}
              {gc > 0 && !s.mine && (
                <Box
                  as="button"
                  type="button"
                  onClick={() => {
                    track('Clicked Price List Gift Card', { merchant: s.merchant, saving: gc });
                    onPickGiftCard(s.voucherRoute);
                  }}
                  alignSelf="flex-start"
                  ml={`${sz.logo + 10}px`}
                  mt="6px"
                  fontSize={`${sz.small}px`}
                  fontWeight={600}
                  color="amber"
                  bg="amberSoft"
                  borderRadius="pill"
                  px="9px"
                  py="3px"
                  _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
                >
                  −{fmt(gc)} with {s.voucher.offline_only ? 'in-store ' : ''}Gift Voucher ›
                </Box>
              )}
              {s.mine && (
                <Text ml={`${sz.logo + 10}px`} mt="6px" fontSize={`${sz.small + 0.5}px`} color="text2">
                  <Text as="span" fontFamily="mono">{fmt(s.listPrice)}</Text>{' '}
                  <Text as="span" color="brand" fontWeight={600}>
                    − {fmt(s.mine.saving)}{s.mine.cashback ? ' cashback' : ''} with your {s.mine.bank} card
                  </Text>
                </Text>
              )}
              {other && (
                <Text ml={`${sz.logo + 10}px`} mt="6px" fontSize={`${sz.small}px`} color="text3">
                  {fmt(other.saving)} off with {other.bank} {other.card}
                  {applyLink(other) && (
                    <>
                      {' · '}
                      <Link
                        href={applyLink(other)}
                        isExternal
                        color="text2"
                        fontWeight={600}
                        textDecoration="underline"
                        onClick={() => track('Clicked Apply For Card', { merchant: s.merchant, bank: other.bank, saving: other.saving })}
                      >
                        Get this card
                      </Link>
                    </>
                  )}
                </Text>
              )}
            </Card>
            {first && afterFirst}
            </Fragment>
          );
        })}
      </Flex>

      {hidden > 0 && (
        <Button variant="ghost" size="sm" color="text2" fontWeight={500} onClick={() => setShowAll(true)}>
          Show {hidden} more shop{hidden > 1 ? 's' : ''}
        </Button>
      )}

    </Flex>
  );
}
