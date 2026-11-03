import { useEffect, useState } from 'react';
import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { Navigate, Link as RouterLink, useParams } from 'react-router-dom';

import BrandAvatar from '@/components/common/BrandAvatar';
import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import SHOP_PAGES from '@/data/shopPages.json';
import { getBrandDeal } from '@/data/brandDeals';
import { hubbleApi } from '@/api/hubble.api';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageTitle } from '@/hooks/usePageTitle';
import {
  DEALO_EXPLAINED,
  SELLER_NAME,
  SELLERS_EXPLAINED,
  pct,
  shopFaqs,
  shopJsonLd,
  shopPageMeta,
  whereToRedeemShop,
} from '@/seo/pageMeta';
import { outboundLink, track } from '@/utils/analytics';
import { fmt } from '@/utils/format';
import { shopLogos } from '@/utils/priceList';
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

function Fact({ icon, label, value }) {
  return (
    <Flex align="flex-start" gap="10px" p="13px 14px" borderRadius="12px" bg="surface2" border="1px solid" borderColor="border">
      <Flex flex="0 0 auto" w="30px" h="30px" align="center" justify="center" borderRadius="9px" bg="brassSoft" color="brass">
        {icon}
      </Flex>
      <Box>
        <Text m="0 0 2px" fontSize="11.5px" fontWeight={700}>
          {label}
        </Text>
        <Text m={0} fontSize="11.5px" color="text2" lineHeight={1.45}>
          {value}
        </Text>
      </Box>
    </Flex>
  );
}

/** The shop's logo from the same sources the price list uses (Brandfetch,
 * then the site's favicon), on a white disc; initials if both are missing. */
function ShopLogo({ shop, size = 56 }) {
  const sources = shopLogos(shop.website);
  const [tries, setTries] = useState(0);
  const src = sources[tries];
  const filled = tries === 0;
  return (
    <Flex w={`${size}px`} h={`${size}px`} borderRadius="14px" bg="white" border="1px solid" borderColor="border" align="center" justify="center" overflow="hidden" flexShrink={0}>
      {src ? (
        <Box as="img" src={src} alt={`${shop.name} logo`} decoding="async" w={filled ? '100%' : '28px'} h={filled ? '100%' : '28px'} objectFit={filled ? 'cover' : 'contain'} onError={() => setTries((t) => t + 1)} />
      ) : (
        <BrandAvatar name={shop.name} size={size} radius="14px" fontSize="22px" />
      )}
    </Flex>
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
      .brand(shop.name)
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
  const steps = curated?.steps?.length
    ? curated.steps
    : [
        hubble ? 'Tap Dealo above and pick the voucher amount.' : 'Pick the seller above with the best rate.',
        `Buy a ${shop.name} gift voucher for the amount you plan to spend.`,
        ...(shop.steps.length ? shop.steps.slice(0, 2) : [`Pay at ${shop.name} with the voucher code and keep the difference.`]),
      ];

  return (
    <InfoPageShell title={meta.heading} subtitle={meta.intro}>
      <Flex align="center" gap="14px" mb="18px">
        <ShopLogo shop={shop} />
        <Flex gap="8px" flexWrap="wrap">
          {shop.online && <Badge>Works online</Badge>}
          {shop.offline && <Badge>Works in store</Badge>}
          <Badge>Checked {shop.checked}</Badge>
        </Flex>
      </Flex>

      <H2>{hubble ? 'Today’s rate' : 'Today’s rate, every seller'}</H2>
      <Flex direction="column" gap="8px" mb="10px">
        {rows.map((r) => (
          <SellerRow key={r.source} shop={shop} seller={r} cheapest={!hubble && r.pct === topPct} />
        ))}
      </Flex>
      <Text fontSize="12px" color="text2" lineHeight={1.5} mb="26px">
        {hubble ? DEALO_EXPLAINED : SELLERS_EXPLAINED}
      </Text>

      {hubble?.cards?.length > 0 && (
        <Text fontSize="12.5px" color="text2" mb="26px">
          Dealo sells it in {hubble.cards.slice(0, 5).map((c) => fmt(c)).join(', ')}
          {hubble.typed ? ' or any amount you type' : ''}.
        </Text>
      )}

      <H2>How to get the discount</H2>
      <Box mb="24px">
        {steps.map((s, i) => (
          <Flex key={s} align="flex-start" gap="12px" mb="12px">
            <Flex flex="0 0 auto" w="26px" h="26px" align="center" justify="center" borderRadius="999px" bg="brand" color="onBrand" fontSize="12px" fontWeight={800}>
              {i + 1}
            </Flex>
            <Text m="3px 0 0" fontSize="13.5px" color="text2" lineHeight={1.6}>
              {s}
            </Text>
          </Flex>
        ))}
      </Box>

      <H2>Quick facts</H2>
      <Box display="grid" gridTemplateColumns={{ base: '1fr', sm: 'repeat(2, 1fr)' }} gap="10px" mb="22px">
        <Fact icon={<I.globe size={15} />} label="Where to redeem" value={whereToRedeemShop(shop)} />
        <Fact
          icon={<I.doc size={15} />}
          label="Multi-use or single-use"
          value={shop.multiUse === true ? 'Multi-use, spend it across orders' : shop.multiUse === false ? 'Single-use, the full value goes in one order' : 'Not stated by the shop'}
        />
        <Fact
          icon={<I.check size={15} />}
          label="Works with other offers"
          value={shop.canClub === true ? 'Yes, pays the price after sale and coupons' : shop.canClub === false ? 'No, cannot be combined with other offers' : 'Not stated, treat it as store credit'}
        />
        {shop.restrictions.length > 0 && <Fact icon={<I.alert size={15} />} label="Cannot be used for" value={shop.restrictions.join(' · ')} />}
      </Box>

      {curated?.notes && (
        <Flex align="flex-start" gap="10px" p="14px 16px" borderRadius="14px" bg="amberSoft" mb="22px">
          <Box color="amber" mt="1px" flex="0 0 auto">
            <I.info size={16} />
          </Box>
          <Text m={0} fontSize="12.5px" color="text2" lineHeight={1.55}>
            {curated.notes}
          </Text>
        </Flex>
      )}

      <H2>Questions people ask</H2>
      <Box mb="24px">
        {faqs.map((f) => (
          <Box key={f.q} mb="14px">
            <Text fontSize="13.5px" fontWeight={700} mb="3px">
              {f.q}
            </Text>
            <Text fontSize="13px" color="text2" lineHeight={1.6}>
              {f.a}
            </Text>
          </Box>
        ))}
      </Box>

      <Button as={RouterLink} to={ROUTES.home} variant="outline" h="46px" w="100%" borderRadius="14px" fontSize="14px" fontWeight={700}>
        Buying something specific? Search it on Dealo
      </Button>
    </InfoPageShell>
  );
}
