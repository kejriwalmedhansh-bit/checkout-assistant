import { useEffect, useState } from 'react';
import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { Navigate, Link as RouterLink, useParams } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import { ShopGrid, ShopLogo } from '@/components/common/ShopLinkRow';
import SHOP_PAGES from '@/data/shopPages.json';
import { getBrandDeal } from '@/data/brandDeals';
import { hubbleApi } from '@/api/hubble.api';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageTitle } from '@/hooks/usePageTitle';
import { BILL, categoryOf, inr, moreHeading, payOn, similarShops } from '@/seo/categories';
import {
  SELLER_NAME,
  SELLERS_EXPLAINED,
  buyAmounts,
  defaultBuyAmount,
  hasBuyBox,
  isMultiUse,
  isSubscription,
  payFor,
  pct,
  planPrices,
  shopFaqs,
  shopJsonLd,
  shopPageMeta,
  whereToRedeemShop,
} from '@/seo/pageMeta';
import { outboundLink, track } from '@/utils/analytics';
import { ROUTES } from '@/routes/paths';

const HUBBLE_ON = import.meta.env.VITE_HUBBLE_ENABLED === 'true';
const SHOP_BY_SLUG = new Map(SHOP_PAGES.map((s) => [s.slug, s]));
// Same slug rule as buy_slug() in src/services/hubble_service.py.
const buySlug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

/**
 * /brands/<slug>/ — the page Google sends people to for "<shop> gift card
 * discount". One table: today's rate from every seller, cheapest first,
 * Dealo's own voucher with a Buy button, partners with a link out. The
 * partner rates are baked in at build time (scripts/build_shop_pages.py);
 * Dealo's rate is re-read live when the page opens, since it is the one
 * the page can sell.
 */

function Badge({ children, ...props }) {
  return (
    <Flex align="center" gap="5px" px="10px" py="4px" borderRadius="999px" bg="surface3" color="text2" fontSize="11.5px" fontWeight={700} {...props}>
      {children}
    </Flex>
  );
}

/** One line of "About this voucher": the question in bold, the answer under it. */
function FactRow({ icon, q, a }) {
  return (
    <Flex align="flex-start" gap="12px" py="10px" borderBottom="1px dashed" borderColor="border" _last={{ borderBottom: 'none' }}>
      <Box color="brass" mt="2px" flex="0 0 auto">
        {icon}
      </Box>
      <Box minW={0}>
        <Text m={0} fontSize="13.5px" fontWeight={700}>
          {q}
        </Text>
        <Text m={0} fontSize="12.5px" color="text2" lineHeight={1.45}>
          {a}
        </Text>
      </Box>
    </Flex>
  );
}

/** A section folded behind its heading, the way Maximize keeps "How to
 * redeem" and the terms off the first screen. Open by default on wide
 * screens is not needed: the crawler reads the prerendered copy. */
function Fold({ title, children }) {
  const [open, setOpen] = useState(false);
  return (
    <Box border="1px solid" borderColor="border" borderRadius="14px" mb="10px" overflow="hidden">
      <Flex as="button" type="button" onClick={() => setOpen((o) => !o)} w="100%" align="center" justify="space-between" px="14px" py="12px" bg="surface2" fontSize="14px" fontWeight={700} textAlign="left">
        {title}
        <Box color="text2" transform={open ? 'rotate(180deg)' : 'none'} transition="transform .15s">
          <I.chevDown size={16} />
        </Box>
      </Flex>
      {open && (
        <Box px="14px" py="12px">
          {children}
        </Box>
      )}
    </Box>
  );
}

function H2({ children }) {
  return (
    <Text as="h2" m="0 0 12px" fontSize="15px" fontWeight={800} letterSpacing="-.01em">
      {children}
    </Text>
  );
}

/** One seller's row: who, today's rate, what happens on tap. */
function SellerRow({ shop, seller, cheapest }) {
  const isDealo = seller.source === 'dealo';
  const name = SELLER_NAME[seller.source];
  const sub = isDealo
    ? 'Sold by Dealo · code in seconds'
    : seller.card_pct > 0 && seller.card_pct < seller.pct
      ? `${pct(seller.pct)} from your bank app · ${pct(seller.card_pct)} by card`
      : seller.card_pct === 0
        ? 'Pay from your bank app, not by card'
        : 'Official gift voucher seller';
  const common = {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    p: '12px 14px',
    borderRadius: '14px',
    border: '1.5px solid',
    borderColor: cheapest ? 'green' : 'border',
    bg: cheapest ? 'greenSoft' : 'surface2',
    _hover: { textDecoration: 'none', borderColor: cheapest ? 'green' : 'borderStrong' },
  };
  const body = (
    <>
      <Box flex="1" minW={0}>
        <Flex align="center" gap="8px" flexWrap="wrap">
          <Text fontSize="14px" fontWeight={800}>
            {name}
          </Text>
          {cheapest && (
            <Badge bg="green" color="white">
              Cheapest today
            </Badge>
          )}
        </Flex>
        <Text fontSize="12px" color="text2" mt="2px">
          {sub}
        </Text>
      </Box>
      <Text fontFamily="mono" fontWeight={800} fontSize="20px" color={cheapest ? 'green' : 'text'} flexShrink={0}>
        {pct(seller.pct)} off
      </Text>
      <Box color="text2" flexShrink={0}>
        {isDealo ? <I.arrowRight size={16} /> : <I.external size={14} />}
      </Box>
    </>
  );
  if (isDealo) {
    return (
      <Box
        as={RouterLink}
        to={`${ROUTES.buyFor(buySlug(seller.brand_name || shop.name))}?src=page`}
        onClick={() => track('Clicked Brand Voucher Link', { brand: shop.name, source: 'dealo', pct: seller.pct, placement: 'brand-page' })}
        {...common}
      >
        {body}
      </Box>
    );
  }
  return (
    <Box
      as="a"
      href={outboundLink(seller.url, 'voucher_site', 'brand_page')}
      target="_blank"
      rel="noopener noreferrer"
      onClick={() => track('Clicked Brand Voucher Link', { brand: shop.name, source: seller.source, pct: seller.pct, placement: 'brand-page' })}
      {...common}
    >
      {body}
    </Box>
  );
}

/** The buy box (test pages, see BUY_BOX_SHOPS): pick an amount, see what you
 * pay, buy. Everything a buyer needs on the first phone screen. */
function BuyBox({ shop, hubble }) {
  const sub = isSubscription(shop);
  const amounts = buyAmounts(shop, hubble);
  const [amount, setAmount] = useState(defaultBuyAmount(shop, hubble));
  const pay = payFor(amount, hubble.pct);
  const facts = (hubble.facts || []).slice(0, 4);
  return (
    <Box mb="22px">
      <Box p="14px" borderRadius="16px" bg="surface2" border="1px solid" borderColor="border" mb="10px">
        <Text m="0 0 8px" fontSize="12.5px" fontWeight={700} color="text2">
          {sub ? 'Which plan do you want?' : `How much will you spend at ${shop.name}?`}
        </Text>
        <Flex gap="8px" flexWrap="wrap" mb="14px">
          {amounts.map((a) => (
            <Box
              key={a}
              as="button"
              type="button"
              aria-pressed={a === amount}
              onClick={() => setAmount(a)}
              px="12px"
              h="40px"
              borderRadius="12px"
              border="1.5px solid"
              borderColor={a === amount ? 'green' : 'borderStrong'}
              bg={a === amount ? 'greenSoft' : 'surface'}
              color={a === amount ? 'green' : 'text'}
              fontFamily="mono"
              fontWeight={700}
              fontSize="14px"
            >
              {inr(a)}
            </Box>
          ))}
        </Flex>
        <Flex justify="space-between" align="flex-end" gap="10px" mb="12px">
          <Box>
            <Text m={0} fontSize="12.5px" fontWeight={700} color="text2">
              You pay
            </Text>
            <Text m={0} fontFamily="mono" fontWeight={800} fontSize="28px" lineHeight={1.1}>
              {inr(pay)}
            </Text>
          </Box>
          <Box textAlign="right">
            <Text m={0} fontFamily="mono" fontSize="13px" color="text3" textDecoration="line-through">
              {inr(amount)}
            </Text>
            <Text m={0} fontSize="12.5px" fontWeight={700} color="green">
              You keep {inr(amount - pay)}
            </Text>
          </Box>
        </Flex>
        <Button
          as={RouterLink}
          to={`${ROUTES.buyFor(buySlug(hubble.brand_name || shop.name))}?amount=${amount}&src=page`}
          onClick={() => track('Clicked Brand Voucher Link', { brand: shop.name, source: 'dealo', pct: hubble.pct, amount, placement: 'brand-page-buybox' })}
          variant="primary"
          _hover={{ textDecoration: 'none', bg: 'brandHover' }}
          h="48px"
          w="100%"
          borderRadius="14px"
          fontSize="15px"
          fontWeight={700}
        >
          Buy for {inr(pay)}
        </Button>
        <Text m="10px 0 0" fontSize="12px" color="text2" lineHeight={1.5}>
          Pay from your bank app. The code arrives in seconds.
          {hubble.typed && hubble.min_amount && hubble.max_amount ? ` Any amount from ${inr(hubble.min_amount)} to ${inr(hubble.max_amount)}.` : ''}
        </Text>
      </Box>
      {facts.length > 0 && (
        <Box display="grid" gridTemplateColumns="1fr 1fr" gap="8px" mb="10px">
          {facts.map((f) => (
            <Box key={f.title + f.sub} p="9px 10px" borderRadius="12px" bg="surface3">
              <Text m={0} fontSize="12.5px" fontWeight={700} lineHeight={1.35}>
                {f.title}
              </Text>
              <Text m={0} fontSize="12.5px" color="text2" lineHeight={1.35}>
                {f.sub}
              </Text>
            </Box>
          ))}
        </Box>
      )}
      <Text m={0} fontSize="12px" color="text2" lineHeight={1.5}>
        Issued through Hubble, an official gift voucher issuer. Dealo never sees your card number, UPI PIN or OTP.
      </Text>
    </Box>
  );
}

export default function BrandPage() {
  const { slug } = useParams();
  const shop = SHOP_BY_SLUG.get(slug);
  // The six original pages carry hand-written copy; keep it where it exists.
  const curated = getBrandDeal(slug);

  // Dealo's own rate, live: it is the one this page sells.
  const [hubble, setHubble] = useState(shop?.hubble || null);
  useEffect(() => {
    if (!HUBBLE_ON || !shop) return undefined;
    let live = true;
    hubbleApi
      // Ask by the name Dealo's catalogue lists the voucher under ("MakeMyTrip
      // Hotel", "Superdry-Luxe Gift Card"), which is not always the page's name.
      // Asking by the page's name made the Buy row vanish on those pages.
      .brand(shop.hubble?.brand_name || shop.name)
      .then((res) => {
        if (!live) return;
        setHubble(res.available && res.brand?.discount_pct ? { ...shop.hubble, ...res.brand, pct: res.brand.discount_pct } : null);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [shop]);

  const meta = shop ? shopPageMeta(shop) : null;
  useJsonLd(shop ? shopJsonLd(shop) : null);
  usePageTitle(meta ? meta.title : 'Store not found', meta?.description);

  if (!shop) return <Navigate to={ROUTES.brands} replace />;

  // Dealo alone where Dealo sells it (owner's call, 3 Nov 2026); the
  // partner list only for shops Dealo cannot sell.
  const rows = hubble ? [{ source: 'dealo', pct: hubble.pct, brand_name: hubble.brand_name }] : [...shop.sellers].sort((a, b) => b.pct - a.pct);
  const topPct = rows[0]?.pct;
  const faqs = shopFaqs(shop);
  const cat = categoryOf(shop.slug);
  const similar = similarShops(shop, SHOP_PAGES);
  // A subscription voucher buys a plan, not shopping: the page lists what
  // each plan costs and gives the service's own terms and steps, word for word.
  const sub = isSubscription(shop);
  // Test pages put the price and the Buy button first (see BUY_BOX_SHOPS).
  const box = Boolean(hubble) && hasBuyBox(shop);
  const multiUse = isMultiUse(shop, hubble);
  const plans = planPrices(shop, hubble?.pct);
  const subSteps = hubble?.steps?.length ? hubble.steps : shop.steps;
  const subTerms = hubble?.terms || [];
  const steps = sub
    ? [hubble ? 'Tap Dealo above and pick the plan amount.' : 'Pick the seller above with the best rate.', ...(subSteps.length ? subSteps : [`Redeem the code on ${shop.name}.`])]
    : curated?.steps?.length
    ? curated.steps
    : [
        hubble ? 'Tap Dealo above and pick the voucher amount.' : 'Pick the seller above with the best rate.',
        `Buy a ${shop.name} gift voucher for the amount you plan to spend.`,
        // Where Dealo sells the voucher, the steps are the ones for Dealo's own
        // voucher, not a partner's (a partner's can name its own app).
        ...(hubble?.steps?.length ? hubble.steps : shop.steps.length ? shop.steps.slice(0, 2) : [`Pay at ${shop.name} with the voucher code and keep the difference.`]),
      ];

  return (
    <InfoPageShell title={meta.heading} subtitle={meta.intro}>
      <Flex align="center" gap="14px" mb="18px">
        <ShopLogo shop={shop} />
        <Flex gap="8px" flexWrap="wrap">
          {shop.online && !sub && <Badge>Works online</Badge>}
          {shop.offline && <Badge>Works in store</Badge>}
          <Badge>Checked {shop.checked}</Badge>
        </Flex>
      </Flex>

      {box ? (
        <BuyBox shop={shop} hubble={hubble} />
      ) : (
        <>
        <H2>{hubble ? 'Today’s rate' : 'Today’s rate, every seller'}</H2>
        <Flex direction="column" gap="8px" mb="10px">
          {rows.map((r) => (
            <SellerRow key={r.source} shop={shop} seller={r} cheapest={!hubble && r.pct === topPct} />
          ))}
        </Flex>
        {sub && plans.length > 0 && (
          <Box px="14px" borderRadius="14px" bg="surface2" border="1px solid" borderColor="border" mb="10px">
            {plans.map((x) => (
              <Flex key={x.face} justify="space-between" align="center" py="10px" borderBottom="1px dashed" borderColor="border" _last={{ borderBottom: 'none' }}>
                <Text m={0} fontSize="13.5px" fontWeight={700}>
                  {inr(x.face)} plan
                </Text>
                <Text m={0} fontSize="13.5px" fontWeight={800} color="green" fontFamily="mono">
                  You pay {inr(x.pay)}
                </Text>
              </Flex>
            ))}
          </Box>
        )}
        {!sub && topPct > 0 && (
          <Text fontSize="13.5px" fontWeight={700} mb="6px">
            Every {inr(BILL)} you spend at {shop.name} costs {inr(payOn(topPct))} with the gift card.
          </Text>
        )}
        <Text fontSize="12px" color="text2" lineHeight={1.5} mb="22px">
          {!hubble
            ? SELLERS_EXPLAINED
            : sub
              ? `Issued through Hubble, an official gift voucher issuer. You redeem the code on ${shop.name} itself.`
              : 'Issued through Hubble, an official gift voucher issuer. The shop accepts it like store credit.'}
        </Text>
        </>
      )}


      {sub && subTerms.length > 0 && (
        <>
          <H2>Good to know, in {shop.name}’s words</H2>
          <Box px="14px" borderRadius="14px" bg="surface2" border="1px solid" borderColor="border" mb="18px">
            {subTerms.map((t) => (
              <FactRow key={t} icon={<I.doc size={15} />} q="" a={t} />
            ))}
          </Box>
        </>
      )}
      {!sub && <H2>About this voucher</H2>}
      <Box display={sub ? 'none' : 'block'} px="14px" borderRadius="14px" bg="surface2" border="1px solid" borderColor="border" mb="18px">
        <FactRow icon={<I.globe size={15} />} q="Where to redeem?" a={whereToRedeemShop(shop)} />
        <FactRow icon={<I.pay size={15} />} q="How do I pay?" a={hubble ? 'From your bank app; the code arrives in seconds' : 'On the seller’s site, best rate from your bank app'} />
        <FactRow
          icon={<I.doc size={15} />}
          q="Multi-use or single-use?"
          a={multiUse === true ? 'Multi-use, spend it across orders' : multiUse === false ? 'Must use the full value in one go' : 'Not stated by the shop'}
        />
        <FactRow
          icon={<I.check size={15} />}
          q="Can it be clubbed with other offers?"
          a={shop.canClub === true ? 'Yes, it pays the price after sale and coupons' : shop.canClub === false ? 'No, not with other offers' : 'Not stated, treat it as store credit'}
        />
        {shop.stack && <FactRow icon={<I.ticket size={15} />} q="Several vouchers in one order?" a={shop.stack} />}
        {shop.restrictions.length > 0 && <FactRow icon={<I.alert size={15} />} q="Not valid for" a={shop.restrictions.join(' · ')} />}
      </Box>

      <Fold title="How to redeem">
        {steps.map((st, i) => (
          <Flex key={st} align="flex-start" gap="10px" mb="8px">
            <Text flex="0 0 auto" w="20px" fontSize="13px" fontWeight={800} color="brand">
              {i + 1}.
            </Text>
            <Text m={0} fontSize="13px" color="text2" lineHeight={1.55}>
              {st}
            </Text>
          </Flex>
        ))}
        {curated?.notes && (
          <Text mt="6px" fontSize="12.5px" color="text2">
            {curated.notes}
          </Text>
        )}
      </Fold>
      <Fold title="Questions people ask">
        {faqs.map((f) => (
          <Box key={f.q} mb="12px">
            <Text fontSize="13px" fontWeight={700} mb="2px">
              {f.q}
            </Text>
            <Text fontSize="12.5px" color="text2" lineHeight={1.55}>
              {f.a}
            </Text>
          </Box>
        ))}
      </Fold>

      {similar.length > 0 && (
        <>
          <H2>{moreHeading(cat)}</H2>
          <ShopGrid shops={similar} />
          <Text as={RouterLink} to={`${ROUTES.categoryFor(cat.slug)}/`} display="inline-block" mt="10px" mb="22px" fontSize="13px" fontWeight={700} color="brand">
            All {cat.name.toLowerCase()} →
          </Text>
        </>
      )}

      <Button as={RouterLink} to={ROUTES.home} variant="outline" h="46px" w="100%" borderRadius="14px" fontSize="14px" fontWeight={700}>
        Buying something specific? Search it on Dealo
      </Button>
    </InfoPageShell>
  );
}
