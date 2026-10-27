import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  Box,
  Button,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerOverlay,
  Flex,
  Link,
  Text,
} from '@chakra-ui/react';

import BrandAvatar from '@/components/common/BrandAvatar';
import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';
import { affiliateUrl, fmt } from '@/utils/format';
import { shopLogos, shortDelivery } from '@/utils/priceList';

const ROWS_SHOWN = 4;

// Banks: their website (for the bank's own logo beside a card offer, same
// Brandfetch icon lookup as the shop logos) and the page where you apply
// for their credit card. Co-branded cards come first so "Flipkart Axis"
// opens that card's own page, not Axis Bank's list. Unknown banks show no
// logo and no apply link.
// TODO: swap the apply pages for affiliate links once a partner is picked.
const BANKS = [
  ['flipkart axis', 'axisbank.com', 'https://www.axisbank.com/retail/cards/credit-card/flipkart-axisbank-credit-card'],
  ['flipkart sbi', 'sbicard.com', 'https://www.sbicard.com/en/personal/credit-cards/flipkart-sbi-card.html'],
  ['hdfc', 'hdfcbank.com', 'https://www.hdfcbank.com/personal/pay/cards/credit-cards'],
  ['icici', 'icicibank.com', 'https://www.icicibank.com/personal-banking/cards/credit-card'],
  ['axis', 'axisbank.com', 'https://www.axisbank.com/retail/cards/credit-card'],
  ['sbi', 'sbicard.com', 'https://www.sbicard.com/en/personal/credit-cards.page'],
  ['kotak', 'kotak.com', 'https://www.kotak.com/en/personal-banking/cards/credit-cards.html'],
  ['idfc', 'idfcfirstbank.com', 'https://www.idfcfirstbank.com/credit-card'],
  ['bob', 'bankofbaroda.in', 'https://www.bankofbaroda.in/personal-banking/digital-products/cards/credit-cards'],
  ['hsbc', 'hsbc.co.in', 'https://www.hsbc.co.in/credit-cards/'],
];
const bankFor = (bank) => BANKS.find(([k]) => bank.toLowerCase().includes(k));
// Only credit cards get an apply link; a debit card means a new bank account.
const applyLink = (o) => (o.card === 'Credit Card' ? bankFor(o.bank)?.[2] : null);
const cardName = (o) => `${o.bank} ${o.card}`;

function BankLogo({ bank, size }) {
  const site = bankFor(bank)?.[1];
  const [failed, setFailed] = useState(false);
  if (!site || failed) return null;
  return (
    <Box
      as="img"
      src={shopLogos(`https://${site}`)[0]}
      alt=""
      w={`${size}px`}
      h={`${size}px`}
      borderRadius="4px"
      flex="0 0 auto"
      onError={() => setFailed(true)}
    />
  );
}

/** Pop-up for a shopper without the card: the card with the best offer
 * first, with what it saves on this item and where to apply; the shop's
 * other cards below it. Slides up from the bottom on a phone. */
function GetCardSheet({ shop, offers, onClose }) {
  const [best, ...rest] = offers;
  const apply = (o) => () => track('Clicked Apply For Card', { merchant: shop.merchant, bank: o.bank, saving: o.saving });
  return (
    <Drawer isOpen placement="bottom" onClose={onClose}>
      <DrawerOverlay bg="rgba(10,12,10,.6)" backdropFilter="blur(2px)" />
      <DrawerContent bg="surface" borderTopRadius="20px" maxW="520px" mx="auto">
        <DrawerCloseButton top="14px" right="14px" />
        <DrawerBody px="20px" pt="22px" pb="max(22px, env(safe-area-inset-bottom))">
          <Flex align="center" gap="10px" pr="32px">
            <BankLogo bank={best.bank} size={36} />
            <Text fontSize="17px" fontWeight={700} color="text">{cardName(best)}</Text>
          </Flex>
          <Text mt="14px" fontSize="22px" fontWeight={800} color="text" lineHeight="1.2">
            Save {fmt(best.saving)} on this at {shop.merchant}
          </Text>
          <Text mt="4px" fontFamily="mono" fontSize="15px" color="text2">
            <Text as="s" color="text3">{fmt(shop.price)}</Text> → <Text as="span" fontWeight={700} color="cyan">{fmt(shop.price - best.saving)}</Text>
            {best.cashback && <Text as="span" fontFamily="body" color="text3"> · as cashback</Text>}
          </Text>
          <Button
            as={Link}
            href={applyLink(best)}
            isExternal
            onClick={apply(best)}
            mt="18px"
            w="100%"
            h="50px"
            bg="brand"
            color="white"
            fontSize="16px"
            fontWeight={700}
            borderRadius="12px"
            _hover={{ textDecoration: 'none', opacity: 0.92 }}
          >
            Apply for {cardName(best)} ↗
          </Button>
          <Text mt="8px" fontSize="12.5px" color="text3" textAlign="center">
            Opens {best.bank}&apos;s website. New cards usually take 1–2 weeks to arrive.
          </Text>
          {rest.length > 0 && (
            <Flex direction="column" gap="10px" mt="20px" pt="14px" borderTop="1px solid" borderColor="border">
              <Text fontSize="11px" fontWeight={700} letterSpacing=".06em" textTransform="uppercase" color="text3">
                Other cards at {shop.merchant}
              </Text>
              {rest.map((o) => (
                <Flex key={cardName(o)} align="center" gap="8px" fontSize="14px">
                  <BankLogo bank={o.bank} size={20} />
                  <Box flex="1" minW={0}>
                    <Text color="text" fontWeight={600} noOfLines={1}>{cardName(o)}</Text>
                    <Text color="text2" fontSize="12.5px">
                      Save {fmt(o.saving)}{o.cashback ? ' as cashback' : ''}
                    </Text>
                  </Box>
                  {applyLink(o) && (
                    <Link href={applyLink(o)} isExternal onClick={apply(o)} color="brand" fontWeight={700} fontSize="14px">
                      Apply ↗
                    </Link>
                  )}
                </Flex>
              ))}
            </Flex>
          )}
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  );
}

/** A shop's bank card offers, shown the way the shops themselves do it
 * (Flipkart: "₹1,28,900 with Bank offer"): the price after the best card,
 * with the bank's logo; tapping it lists the other cards. Takes the place
 * of the Gift Voucher tag on that row. Never reorders the list: Dealo does
 * not know which cards the shopper has, so the shopper decides. Below it,
 * "No card? Get one" opens GetCardSheet. */
function CardOffers({ shop, offers, indent, small }) {
  const [open, setOpen] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [best, ...rest] = offers;
  const after = (o) => fmt(shop.price - o.saving);
  const applicable = offers.filter(applyLink);
  return (
    <Box ml={`${indent}px`} mt="6px">
      <Box
        as="button"
        type="button"
        onClick={() => {
          if (rest.length) setOpen((v) => !v);
          track('Clicked Price List Card Offer', { merchant: shop.merchant, bank: best.bank, saving: best.saving });
        }}
        display="inline-flex"
        alignItems="center"
        gap="6px"
        flexWrap="wrap"
        textAlign="left"
        fontSize={`${small + 1}px`}
        color="cyan"
        bg="cyanSoft"
        borderRadius="10px"
        px="9px"
        py="5px"
        _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
      >
        <BankLogo bank={best.bank} size={16} />
        <Text as="span" fontFamily="mono" fontWeight={700}>{after(best)}</Text>
        <Text as="span" fontWeight={600}>with {cardName(best)}</Text>
        {rest.length > 0 && <Text as="span" color="text3" fontWeight={500}>· {open ? 'less' : `${rest.length} more`}</Text>}
      </Box>
      {open && (
        <Flex direction="column" gap="6px" mt="8px" pl="2px">
          {rest.map((o) => (
            <Flex key={cardName(o)} align="center" gap="6px" fontSize={`${small}px`} color="text2" flexWrap="wrap">
              <BankLogo bank={o.bank} size={14} />
              <Text as="span" fontFamily="mono" fontWeight={700} color="text">{after(o)}</Text>
              <Text as="span">with {cardName(o)}</Text>
              {o.cashback && <Text as="span" color="text3">· as cashback</Text>}
            </Flex>
          ))}
        </Flex>
      )}
      {applicable.length > 0 && (
        <Box
          as="button"
          type="button"
          display="block"
          mt="6px"
          fontSize={`${small}px`}
          fontWeight={600}
          color="text2"
          textDecoration="underline"
          textUnderlineOffset="2px"
          onClick={() => {
            setSheet(true);
            track('Opened Get Card', { merchant: shop.merchant, bank: applicable[0].bank });
          }}
        >
          No card? Get one ›
        </Box>
      )}
      {sheet && <GetCardSheet shop={shop} offers={applicable} onClose={() => setSheet(false)} />}
    </Box>
  );
}

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
export default function PriceList({ shops, onPickGiftCard, afterFirst = null }) {
  const [showAll, setShowAll] = useState(false);
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
      </Box>
      <Flex ref={stackRef} direction="column" gap="8px" minH={fillH ? `${fillH}px` : undefined}>
        {rows.map((s, i) => {
          const diff = s.price - best.price;
          const gc = s.voucher && s.voucherRoute ? Math.round(s.price - s.voucherRoute.final_cost) : 0;
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
              {gc > 0 && !s.cardOffers?.length && (
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
              {s.cardOffers?.length > 0 && (
                <CardOffers shop={s} offers={s.cardOffers} indent={sz.logo + 10} small={sz.small} />
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
