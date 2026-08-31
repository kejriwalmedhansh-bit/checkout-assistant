import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { I } from '@/components/common/icons';
import { getBrandDeal } from '@/data/brandDeals';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';

const SITE_URL = 'https://getdealo.in';

/**
 * HowTo (matches the numbered redemption steps shown on the page) +
 * BreadcrumbList, not Product/Offer — Dealo doesn't sell the voucher or
 * take a price on this page, it explains a discount rate, so Offer schema
 * would misrepresent what's actually here and risks Google rejecting or
 * penalizing the markup for not matching visible content.
 */
function buildJsonLd(brand) {
  return [
    {
      '@context': 'https://schema.org',
      '@type': 'HowTo',
      name: `How to get the ${brand.name} Gift Voucher discount`,
      description: brand.blurb,
      step: brand.steps.map((text, i) => ({
        '@type': 'HowToStep',
        position: i + 1,
        text,
      })),
    },
    {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Dealo', item: `${SITE_URL}/` },
        { '@type': 'ListItem', position: 2, name: 'Store deals', item: `${SITE_URL}/brands` },
        { '@type': 'ListItem', position: 3, name: brand.name, item: `${SITE_URL}/brands/${brand.slug}` },
      ],
    },
  ];
}

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

  useJsonLd(brand ? buildJsonLd(brand) : null);

  usePageTitle(
    brand ? `${brand.name} Gift Voucher discount` : 'Store not found',
    brand
      ? `${brand.name} Gift Vouchers sell at ${brand.ratePct}% off through the official voucher partner — buy one, spend it like store credit at ${brand.name}, and save the difference.`
      : undefined
  );

  if (!brand) return <Navigate to={ROUTES.brands} replace />;

  return (
    <InfoPageShell title={`${brand.name} Gift Voucher deal`} subtitle={brand.tagline}>
      <Flex align="center" gap="8px" mb="20px" flexWrap="wrap">
        <Badge bg="brandSoft" color="brandText">
          <I.zap size={12} />
          {brand.ratePct}% off, checked {brand.lastChecked}
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

      <Button
        variant="solid"
        bg="brand"
        color="onBrand"
        _hover={{ bg: 'brandHover' }}
        h="46px"
        w="100%"
        borderRadius="14px"
        fontSize="14px"
        fontWeight={700}
        onClick={() => navigate(ROUTES.home)}
      >
        Search {brand.name} on Dealo
      </Button>
    </InfoPageShell>
  );
}
