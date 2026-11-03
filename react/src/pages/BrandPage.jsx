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
  SELLER_NAME,
  SELLERS_EXPLAINED,
  pct,
  shopFaqs,
  shopJsonLd,
  shopPageMeta,
  whereToRedeemShop,
} from '@/seo/pageMeta';
import { outboundLink, track } from '@/utils/analytics';
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
      <Text fontSize="12px" color="text2" lineHeight={1.5} mb="22px">
        {hubble ? 'Issued through Hubble, an official gift voucher issuer. The shop accepts it like store credit.' : SELLERS_EXPLAINED}
      </Text>


      <H2>About this voucher</H2>
      <Box px="14px" borderRadius="14px" bg="surface2" border="1px solid" borderColor="border" mb="18px">
        <FactRow icon={<I.globe size={15} />} q="Where to redeem?" a={whereToRedeemShop(shop)} />
        <FactRow icon={<I.pay size={15} />} q="How do I pay?" a={hubble ? 'From your bank app; the code arrives in seconds' : 'On the seller’s site, best rate from your bank app'} />
        <FactRow
          icon={<I.doc size={15} />}
          q="Multi-use or single-use?"
          a={shop.multiUse === true ? 'Multi-use, spend it across orders' : shop.multiUse === false ? 'Must use the full value in one go' : 'Not stated by the shop'}
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

      <Button as={RouterLink} to={ROUTES.home} variant="outline" h="46px" w="100%" borderRadius="14px" fontSize="14px" fontWeight={700}>
        Buying something specific? Search it on Dealo
      </Button>
    </InfoPageShell>
  );
}
