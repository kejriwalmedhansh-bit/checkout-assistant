import { useEffect, useState } from 'react';
import { Box, Button, Flex, Input, Link, Text, Wrap, WrapItem } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import BuyFlow from '@/components/hubble/BuyFlow';
import { soldApi } from '@/api/sold.api';
import { fmt } from '@/utils/format';
import { outboundLink, track } from '@/utils/analytics';

const HUBBLE_ON = import.meta.env.VITE_HUBBLE_ENABLED === 'true';
const HUBBLE_FORCE = import.meta.env.VITE_HUBBLE_FORCE === 'true';

/**
 * The same card when Dealo sells the voucher itself (Hubble). There is no
 * cart on a shop-name search, so the one new thing is "how much?": Hubble's
 * own card values as quick picks, or a typed amount within its range. The
 * price strip and the Buy button then come from /hubble/offer for that
 * amount, so what is shown is what Hubble charges. The outside link is not
 * shown here (owner's call, 28 Oct 2026).
 */
function HubbleBrandCard({ brand, merchant, query }) {
  const quick = brand.cards.length ? brand.cards.slice(0, 4) : [500, 1000, 2000, 5000].filter((a) => a >= brand.min_amount && (!brand.max_amount || a <= brand.max_amount));
  const [amount, setAmount] = useState(quick[1] || quick[0] || brand.min_amount);
  const [typed, setTyped] = useState('');
  const [offer, setOffer] = useState(null);
  const [buying, setBuying] = useState(false);
  const inRange = (a) => a >= brand.min_amount && (!brand.max_amount || a <= brand.max_amount);

  useEffect(() => {
    let live = true;
    setOffer(null);
    if (!inRange(amount)) return undefined;
    const t = setTimeout(() => {
      soldApi
        .offer(merchant, amount, brand.in_store)
        .then((res) => live && res.available && setOffer(res.offer))
        .catch(() => {});
    }, 250);
    return () => {
      live = false;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [amount, merchant]);

  const pick = (a) => {
    setTyped('');
    setAmount(a);
  };
  const onTyped = (value) => {
    const digits = value.replace(/\D/g, '').slice(0, 6);
    setTyped(digits);
    if (digits) setAmount(Number(digits));
  };
  const where = brand.in_store
    ? `Works in store · show the code at the ${brand.brand_name} counter`
    : brand.works.includes('OFFLINE')
      ? 'Works online and in store'
      : `Works on ${brand.brand_name}'s website and app`;

  return (
    <Card p="22px 20px">
      <Flex align="center" gap="14px" mb="18px">
        <Flex w="44px" h="44px" flex="0 0 auto" borderRadius="12px" bg="amberSoft" color="amber" align="center" justify="center">
          <I.ticket size={22} />
        </Flex>
        <Box minW={0}>
          <Text fontSize="16px" fontWeight={800} color="text" noOfLines={1}>
            {brand.brand_name} Gift Voucher
          </Text>
          <Text fontSize="12px" color="text3" mt="1px">
            sold by Dealo
          </Text>
        </Box>
      </Flex>

      <Box mb="12px">
        <Text fontFamily="mono" fontSize="30px" fontWeight={700} color="amber" lineHeight={1}>
          {brand.discount_pct}% off
        </Text>
        <Text fontSize="12.5px" color="text2" mt="4px">
          Pay by UPI, voucher in seconds
        </Text>
      </Box>
      <Flex display="inline-flex" align="center" gap="6px" bg="surface2" border="1px solid" borderColor="border" borderRadius="pill" px="10px" py="5px" fontSize="12px" fontWeight={700} color="text2" mb="16px">
        {brand.in_store ? <I.store size={13} /> : <I.globe size={13} />}
        {where}
      </Flex>

      <Text fontSize="11px" color="text3" fontWeight={600} letterSpacing=".04em" textTransform="uppercase" mb="8px">
        How much do you need?
      </Text>
      <Wrap spacing="6px" mb="4px">
        {quick.map((a) => (
          <WrapItem key={a}>
            <Button
              size="sm"
              h="36px"
              px="12px"
              fontFamily="mono"
              fontWeight={700}
              borderRadius="10px"
              border="1.5px solid"
              borderColor={amount === a && !typed ? 'text' : 'border'}
              bg={amount === a && !typed ? 'text' : 'surface2'}
              color={amount === a && !typed ? 'onBrand' : 'text'}
              onClick={() => pick(a)}
              _hover={{}}
            >
              {fmt(a)}
            </Button>
          </WrapItem>
        ))}
        {brand.typed && (
          <WrapItem>
            <Input
              value={typed}
              onChange={(e) => onTyped(e.target.value)}
              inputMode="numeric"
              placeholder="or type ₹"
              w="120px"
              h="36px"
              fontFamily="mono"
              fontWeight={700}
              fontSize="16px"
              borderRadius="10px"
            />
          </WrapItem>
        )}
      </Wrap>
      {!inRange(amount) && (
        <Text fontSize="12px" color="danger" fontWeight={600} mt="4px">
          Between {fmt(brand.min_amount)} and {fmt(brand.max_amount)}
        </Text>
      )}

      <Flex bg="greenSoft" border="1.5px solid" borderColor="green" borderRadius="14px" px="12px" py="10px" align="center" gap="10px" mt="14px" opacity={offer ? 1 : 0.55}>
        <Box>
          <Text fontSize="11px" fontWeight={700} letterSpacing=".06em" color="text2">
            YOU PAY
          </Text>
          <Text fontFamily="mono" fontWeight={700} fontSize="20px" lineHeight={1}>
            {offer ? fmt(Math.round(offer.you_pay)) : '…'}
          </Text>
        </Box>
        <Text flex="1" textAlign="center" color="green" fontSize="12px" fontWeight={700}>
          for this card
        </Text>
        <Box textAlign="right">
          <Text fontSize="11px" fontWeight={700} letterSpacing=".06em" color="green">
            YOU SAVE
          </Text>
          <Text fontFamily="mono" fontWeight={700} fontSize="22px" lineHeight={1} color="green">
            {offer ? fmt(Math.round(offer.you_save)) : '…'}
          </Text>
        </Box>
      </Flex>

      <Button
        onClick={() => {
          track('Hubble Shop Card Buy', { query, brand: brand.brand_name, amount });
          setBuying(true);
        }}
        isDisabled={!offer}
        w="100%"
        h="52px"
        mt="14px"
        borderRadius="pill"
        bg="amber"
        color="white"
        fontSize="16px"
        fontWeight={800}
        rightIcon={<I.arrowRight size={16} />}
        _hover={{ bg: 'amber', filter: 'brightness(0.95)' }}
      >
        Buy voucher
      </Button>

      {buying && offer && (
        <BuyFlow offer={offer} merchant={merchant} price={amount} onClose={() => setBuying(false)} />
      )}
    </Card>
  );
}


/**
 * Shown instead of the picker when the query directly names a voucher brand
 * (see `mode: "brand_voucher"` from POST /search) — L1 price discovery is
 * skipped entirely, so there's no "you pay" final price here, only the
 * brand-level voucher terms. Same amber "voucher" tone JourneyRow already
 * uses elsewhere for this concept. Can come from Gyftr, Maximize, or
 * BuyHatke — whichever has the best headline rate (see `_pick_better_voucher`
 * in search_service.py).
 */
const SOURCE_LABELS = { maximize: 'Maximize', buyhatke: 'BuyHatke', gyftr: 'Gyftr' };

export default function BrandVoucherCard({ voucher, query }) {
  // Dealo's own voucher for this shop (Hubble or Maximize, whichever rate is
  // better for the shopper), when it is close enough to this card's. Decided
  // by the server; see /sold/brand.
  const [hubble, setHubble] = useState(null);
  useEffect(() => {
    if (!HUBBLE_ON || !voucher?.brand_name) return undefined;
    let live = true;
    soldApi
      .brand(voucher.brand_name, HUBBLE_FORCE ? null : voucher.best_discount_pct)
      .then((res) => live && res.available && setHubble(res.brand))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [voucher?.brand_name, voucher?.best_discount_pct]);
  if (hubble) return <HubbleBrandCard brand={hubble} merchant={voucher.brand_name} query={query} />;

  // A type-any-amount card (Amazon Pay on Maximize: ₹100–₹10,000) shows its
  // range even when the seller also lists quick-pick amounts — the list would
  // read as the only amounts on offer.
  const anyAmount = Boolean(voucher.is_custom_denom && voucher.custom_min != null && voucher.custom_max != null);
  const denominations = anyAmount ? [] : voucher.denominations || [];
  const method = voucher.best_payment_method || 'UPI';
  const sourceLabel = SOURCE_LABELS[voucher.voucher_source] || 'Gyftr';
  // Never fabricate a store link — a guessed gyftr.com/{slug} URL is wrong
  // whenever this voucher actually came from Maximize (or the backend just
  // didn't have a real URL for this brand). Trust > a confident wrong link.
  const link = voucher.voucher_url ? outboundLink(voucher.voucher_url, 'voucher_site', 'brand_voucher_card') : null;
  // How many vouchers one booking takes, said plainly whenever the terms cap
  // it. Yatra's flight cards are 40% off but only three ₹500 cards fit one
  // booking — with no booking amount here, the rate alone would oversell it,
  // so a single-amount card also states the most it can ever save.
  const limit = voucher.stack_limit;
  const oneAmount = !anyAmount && new Set(denominations).size === 1 ? denominations[0] : null;
  const perBooking = limit === 1
    ? `${oneAmount ? `One ${fmt(oneAmount)} voucher` : 'One voucher'} per booking`
    : limit > 1
      ? `Up to ${limit} ${oneAmount ? `× ${fmt(oneAmount)} vouchers` : 'vouchers'} per booking`
      : null;
  const maxSaving = limit && oneAmount && voucher.best_discount_pct != null
    ? Math.floor((limit * oneAmount * voucher.best_discount_pct) / 100)
    : null;

  return (
    <Card p="22px 20px">
      <Flex align="center" gap="14px" mb="18px">
        <Flex
          w="44px" h="44px" flex="0 0 auto" borderRadius="12px"
          bg="amberSoft" color="amber" align="center" justify="center"
        >
          <I.ticket size={22} />
        </Flex>
        <Box minW={0}>
          <Text fontSize="16px" fontWeight={800} color="text" noOfLines={1}>
            {voucher.brand_name} Gift Voucher
          </Text>
          <Text fontSize="12px" color="text3" mt="1px">
            via {sourceLabel}
          </Text>
        </Box>
      </Flex>

      {voucher.best_discount_pct != null && (
        <Box mb="16px">
          <Text fontFamily="mono" fontSize="30px" fontWeight={700} color="amber" lineHeight={1}>
            {voucher.best_discount_pct}% off
          </Text>
          <Text fontSize="12.5px" color="text2" mt="4px">
            Best rate, paying by {method}
          </Text>
        </Box>
      )}

      {(voucher.covers || perBooking) && (
        <Box mb="16px" fontSize="12.5px" color="text2">
          {voucher.covers && <Text>Works for: {voucher.covers}</Text>}
          {perBooking && (
            <Text fontWeight={600} color="text">
              {perBooking}{maxSaving ? ` · saves at most ${fmt(maxSaving)}` : ''}
            </Text>
          )}
        </Box>
      )}

      {denominations.length > 0 && (
        <Box mb="18px">
          <Text fontSize="11px" color="text3" fontWeight={600} letterSpacing=".04em" textTransform="uppercase" mb="8px">
            Available denominations
          </Text>
          <Wrap spacing="6px">
            {denominations.map((d) => (
              <WrapItem key={d}>
                <Box
                  bg="surface2" border="1px solid" borderColor="border" borderRadius="8px"
                  px="10px" py="4px" fontFamily="mono" fontSize="12.5px" fontWeight={600} color="text2"
                >
                  {fmt(d)}
                </Box>
              </WrapItem>
            ))}
          </Wrap>
        </Box>
      )}

      {anyAmount && (
        <Box mb="18px">
          <Text fontSize="11px" color="text3" fontWeight={600} letterSpacing=".04em" textTransform="uppercase" mb="8px">
            Voucher amount
          </Text>
          <Box
            display="inline-block" bg="surface2" border="1px solid" borderColor="border" borderRadius="8px"
            px="10px" py="4px" fontFamily="mono" fontSize="12.5px" fontWeight={600} color="text2"
          >
            Any amount, {fmt(voucher.custom_min)}–{fmt(voucher.custom_max)}
          </Box>
        </Box>
      )}

      {link ? (
        <Link
          href={link}
          isExternal
          display="inline-flex"
          alignItems="center"
          justifyContent="center"
          gap="6px"
          w="100%"
          bg="amber"
          color="onBrand"
          fontSize="13.5px"
          fontWeight={700}
          borderRadius="10px"
          py="12px"
          _hover={{ textDecoration: 'none', opacity: 0.92 }}
        >
          Buy voucher on {sourceLabel}
          <I.arrowRight size={15} />
        </Link>
      ) : (
        <Text fontSize="12px" color="text3" textAlign="center">
          Store link unavailable right now — search for {voucher.brand_name} on {sourceLabel} directly.
        </Text>
      )}
    </Card>
  );
}
