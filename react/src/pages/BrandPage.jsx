import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';

import BrandAvatar from '@/components/common/BrandAvatar';
import ALL_BRAND_DEALS from '@/data/allBrandDeals.json';
import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import { getBrandDeal } from '@/data/brandDeals';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageTitle } from '@/hooks/usePageTitle';
import { brandJsonLd, brandPageMeta, canClubText, multiUseText, whereToRedeem } from '@/seo/pageMeta';
import { outboundLink, track } from '@/utils/analytics';
import { ROUTES } from '@/routes/paths';

const SOURCE_LABEL = { gyftr: 'Gyftr', maximize: 'Maximize', buyhatke: 'BuyHatke' };

const normalizeKey = (name) => name.toLowerCase().replace(/[^a-z0-9]/g, '');

// These pages stay in sitemap.xml and take search traffic directly, so they
// cannot rely on the hand-typed `ratePct` in brandDeals.js — those had drifted
// up to 2 points low. The rate and the partner link come from the same
// generated file the rest of the site reads.
const LIVE_DEAL_BY_KEY = new Map(ALL_BRAND_DEALS.map((b) => [normalizeKey(b.name), b]));

function Badge({ children, ...props }) {
  return (
    <Flex
      align="center"
      gap="5px"
      px="10px"
      py="4px"
      borderRadius="99px"
      bg="surface3"
      color="text2"
      fontSize="11.5px"
      fontWeight={700}
      {...props}
    >
      {children}
    </Flex>
  );
}

function Fact({ icon, label, value }) {
  return (
    <Flex align="flex-start" gap="10px" p="13px 14px" borderRadius="13px" bg="surface2" border="1px solid" borderColor="border">
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

function Step({ n, children }) {
  return (
    <Flex align="flex-start" gap="12px" mb="14px">
      <Flex
        flex="0 0 auto"
        w="26px"
        h="26px"
        align="center"
        justify="center"
        borderRadius="99px"
        bg="brand"
        color="onBrand"
        fontSize="12px"
        fontWeight={800}
      >
        {n}
      </Flex>
      <Text m="3px 0 0" fontSize="13.5px" color="text2" lineHeight={1.6}>
        {children}
      </Text>
    </Flex>
  );
}

export default function BrandPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const brand = getBrandDeal(slug);
  const deal = brand ? LIVE_DEAL_BY_KEY.get(normalizeKey(brand.name)) : null;
  const ratePct = deal ? deal.pct : brand?.ratePct;

  useJsonLd(brand ? brandJsonLd(brand) : null);

  const meta = brand ? brandPageMeta(brand, ratePct) : null;
  usePageTitle(meta ? meta.title : 'Store not found', meta?.description);

  if (!brand) return <Navigate to={ROUTES.brands} replace />;

  return (
    <InfoPageShell title={`${brand.name} Gift Voucher deal`} subtitle={brand.tagline}>
      <BrandAvatar name={brand.name} size={72} logoSrc={`/brand-logos/${brand.slug}.webp`} radius="14px" fontSize="26px" />
      <Flex align="center" gap="8px" mt="14px" mb="20px" flexWrap="wrap">
        <Badge bg="brandSoft" color="brandText">
          <I.zap size={12} />
          {ratePct}% off{deal ? '' : `, checked ${brand.lastChecked}`}
        </Badge>
        {brand.online && <Badge>Works online</Badge>}
        {brand.offline && <Badge>Works in-store</Badge>}
      </Flex>

      <Text fontSize="14px" color="text2" lineHeight={1.65} mb="26px">
        {brand.blurb}
      </Text>

      <Text as="h2" m="0 0 14px" fontSize="15px" fontWeight={800} letterSpacing="-.01em">
        How to get the discount
      </Text>
      <Box mb="24px">
        {brand.steps.map((s, i) => (
          <Step key={s} n={i + 1}>
            {s}
          </Step>
        ))}
      </Box>

      <Text as="h2" m="0 0 14px" fontSize="15px" fontWeight={800} letterSpacing="-.01em">
        Quick facts
      </Text>
      <Box display="grid" gridTemplateColumns={{ base: '1fr', sm: 'repeat(2, 1fr)' }} gap="10px" mb="22px">
        <Fact icon={<I.globe size={15} />} label="Where to redeem" value={whereToRedeem(brand)} />
        <Fact icon={<I.doc size={15} />} label="Multi-use or single-use" value={multiUseText(brand)} />
        <Fact icon={<I.check size={15} />} label="Can be clubbed with offers" value={canClubText(brand)} />
      </Box>

      {brand.notes && (
        <Flex align="flex-start" gap="10px" p="14px 16px" borderRadius="14px" bg="amberSoft" mb="22px">
          <Box color="amber" mt="1px" flex="0 0 auto">
            <I.info size={16} />
          </Box>
          <Text m={0} fontSize="12.5px" color="text2" lineHeight={1.55}>
            {brand.notes}
          </Text>
        </Flex>
      )}

      {/* Was a button that navigated to the empty search homepage, leaving the
          reader to retype the brand they had just clicked. It now goes where
          the page has spent its whole length telling them to go. Falls back to
          search only when no live row exists for this brand. */}
      <Button
        as={deal ? 'a' : 'button'}
        href={deal ? outboundLink(deal.url, 'voucher_site', 'brand_page') : undefined}
        target={deal ? '_blank' : undefined}
        rel={deal ? 'noopener noreferrer' : undefined}
        variant="solid"
        bg="brand"
        color="onBrand"
        _hover={{ bg: 'brandHover', textDecoration: 'none' }}
        h="46px"
        w="100%"
        borderRadius="14px"
        fontSize="14px"
        fontWeight={700}
        onClick={
          deal
            ? () => track('Clicked Brand Voucher Link', {
                brand: brand.name, source: deal.source, pct: deal.pct, placement: 'brand-page',
              })
            : () => navigate(ROUTES.home)
        }
      >
        {deal
          ? `Buy on ${SOURCE_LABEL[deal.source] || deal.source} — ${deal.pct}% off`
          : `Search ${brand.name} on Dealo`}
      </Button>
    </InfoPageShell>
  );
}
