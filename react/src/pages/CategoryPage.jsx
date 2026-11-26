import { Button, Flex, Text } from '@chakra-ui/react';
import { Navigate, Link as RouterLink, useParams } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { ShopGrid } from '@/components/common/ShopLinkRow';
import SHOP_PAGES from '@/data/shopPages.json';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageTitle } from '@/hooks/usePageTitle';
import { CATEGORIES, categoryBySlug, categoryJsonLd, categoryMeta, categoryShops } from '@/seo/categories';
import { ROUTES } from '@/routes/paths';
import { shortDate } from '@/seo/pageMeta';

/**
 * /gift-cards/<slug>/ — every shop page of one kind (food, fashion, travel…),
 * biggest discount first, each linking to its own page. Rates are the ones
 * baked into shopPages.json at build time, same as the prerendered copy.
 */
export default function CategoryPage() {
  const { slug } = useParams();
  const cat = categoryBySlug(slug);
  const shops = cat ? categoryShops(cat, SHOP_PAGES) : [];
  const meta = cat ? categoryMeta(cat, shops) : null;
  useJsonLd(cat ? categoryJsonLd(cat, shops) : null);
  usePageTitle(meta ? meta.title : 'Category not found', meta?.description);

  if (!cat) return <Navigate to={ROUTES.brands} replace />;
  const checked = shops.map((s) => s.checked).sort().pop();

  return (
    <InfoPageShell title={meta.heading} subtitle={meta.intro}>
      <ShopGrid shops={shops} />
      {checked && (
        <Text fontSize="11.5px" color="text3" mt="10px">
          Rates checked {shortDate(checked)}. Each shop page shows today’s rate when you open it.
        </Text>
      )}

      <Text as="h2" m="28px 0 10px" fontSize="13px" fontWeight={700} color="text3" letterSpacing=".02em" textTransform="uppercase">
        Other kinds of shops
      </Text>
      <Flex gap="8px" flexWrap="wrap" mb="24px">
        {CATEGORIES.filter((c) => c.slug !== cat.slug).map((c) => (
          <Text
            key={c.slug}
            className="dealo-press" as={RouterLink}
            to={`${ROUTES.categoryFor(c.slug)}/`}
            px="12px"
            py="6px"
            borderRadius="999px"
            border="1px solid"
            borderColor="border"
            bg="surface2"
            fontSize="12.5px"
            fontWeight={700}
            color="text"
            _hover={{ textDecoration: 'none', borderColor: 'borderStrong' }}
          >
            {c.short}
          </Text>
        ))}
      </Flex>

      <Button as={RouterLink} to={ROUTES.home} variant="outline" h="46px" w="100%" borderRadius="14px" fontSize="14px" fontWeight={700}>
        Buying something specific? Search it on Dealo
      </Button>
    </InfoPageShell>
  );
}
