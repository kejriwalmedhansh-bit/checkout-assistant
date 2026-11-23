import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { Navigate, Link as RouterLink, useParams } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { ShopGrid } from '@/components/common/ShopLinkRow';
import SHOP_PAGES from '@/data/shopPages.json';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageTitle } from '@/hooks/usePageTitle';
import { buildGuides, guideJsonLd } from '@/seo/guides';
import { ROUTES } from '@/routes/paths';

const GUIDES = buildGuides(SHOP_PAGES);
const SHOP_BY_SLUG = new Map(SHOP_PAGES.map((s) => [s.slug, s]));
const CHECKED = SHOP_PAGES.map((s) => s.checked).sort().pop();

function H2({ children }) {
  return (
    <Text as="h2" m="26px 0 10px" fontSize="16px" fontWeight={800} letterSpacing="-.01em">
      {children}
    </Text>
  );
}

function Para({ children }) {
  return (
    <Text m="0 0 10px" fontSize="14px" color="text2" lineHeight={1.6}>
      {children}
    </Text>
  );
}

function Steps({ items, numbered }) {
  return (
    <Box as={numbered ? 'ol' : 'ul'} m="0 0 10px" pl="20px">
      {items.map((t) => (
        <Text as="li" key={t} fontSize="14px" color="text2" lineHeight={1.6} mb="6px">
          {t}
        </Text>
      ))}
    </Box>
  );
}

/** /guides/<slug>/ — plain answers to what people search, from src/seo/guides.js. */
export default function GuidePage() {
  const { slug } = useParams();
  const guide = GUIDES.find((g) => g.slug === slug);
  useJsonLd(guide ? guideJsonLd(guide, CHECKED) : null);
  usePageTitle(guide ? guide.title : 'Guide not found', guide?.description);

  if (!guide) return <Navigate to={ROUTES.home} replace />;
  const others = GUIDES.filter((g) => g.slug !== guide.slug);

  return (
    <InfoPageShell title={guide.heading} subtitle={guide.intro}>
      {guide.sections.map((sec) => (
        <Box key={sec.h}>
          <H2>{sec.h}</H2>
          {sec.p?.map((t) => (
            <Para key={t}>{t}</Para>
          ))}
          {sec.ol && <Steps items={sec.ol} numbered />}
          {sec.ul && <Steps items={sec.ul} />}
          {sec.table && (
            <Box border="1px solid" borderColor="border" borderRadius="12px" overflow="hidden" mb="10px">
              {sec.table.rows.map((r, i) => (
                <Box
                  key={r.label}
                  as={RouterLink}
                  to={r.href}
                  display="block"
                  p="10px 12px"
                  borderTop={i ? '1px solid' : 'none'}
                  borderColor="border"
                  _hover={{ textDecoration: 'none', bg: 'surface2' }}
                >
                  <Flex justify="space-between" align="baseline" gap="10px">
                    <Text m={0} fontSize="14px" fontWeight={700}>
                      {r.label}
                    </Text>
                    <Text m={0} fontSize="12px" color="text3" flexShrink={0}>
                      {r.count} shops
                    </Text>
                  </Flex>
                  <Text m="2px 0 0" fontSize="13px" color="text2" lineHeight={1.5}>
                    Biggest: {r.best} · Smallest: {r.least}
                  </Text>
                </Box>
              ))}
            </Box>
          )}
          {sec.shops && (
            <>
              <ShopGrid shops={sec.shops.map((sl) => SHOP_BY_SLUG.get(sl)).filter(Boolean)} />
              <Text fontSize="11.5px" color="text3" mt="8px">
                Rates checked {CHECKED}.{' '}
                <Text as={RouterLink} to={`${ROUTES.brands}/`} color="brand" fontWeight={700}>
                  See all shops →
                </Text>
              </Text>
            </>
          )}
        </Box>
      ))}

      <H2>Questions people ask</H2>
      {guide.faqs.map((f) => (
        <Box key={f.q} mb="12px">
          <Text fontSize="14px" fontWeight={700} mb="2px">
            {f.q}
          </Text>
          <Text fontSize="13.5px" color="text2" lineHeight={1.6}>
            {f.a}
          </Text>
        </Box>
      ))}

      {guide.note && (
        <Text fontSize="12px" color="text3" lineHeight={1.6} mt="18px">
          {guide.note}
        </Text>
      )}

      {others.length > 0 && (
        <Flex direction="column" gap="6px" mt="18px" mb="22px">
          {others.map((g) => (
            <Text key={g.slug} as={RouterLink} to={`${ROUTES.guideFor(g.slug)}/`} fontSize="13.5px" fontWeight={700} color="brand">
              {g.title} →
            </Text>
          ))}
        </Flex>
      )}

      <Button as={RouterLink} to={ROUTES.home} colorScheme="brand" h="46px" w="100%" borderRadius="14px" fontSize="14px" fontWeight={700}>
        Check your shop on Dealo
      </Button>
    </InfoPageShell>
  );
}
