import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { Navigate, Link as RouterLink, useParams } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { ShopGrid } from '@/components/common/ShopLinkRow';
import SHOP_PAGES from '@/data/shopPages.json';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageTitle } from '@/hooks/usePageTitle';
import { buildGuides, guideJsonLd } from '@/seo/guides';
import { ROUTES } from '@/routes/paths';
import { pct, shortDate } from '@/seo/pageMeta';

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

const TONE = { up: 'green', down: 'danger', same: 'borderStrong' };

/** One bar cut into "went up / the same / went down", to scale. */
function SplitBar({ up, same, down, h = '14px' }) {
  const parts = [['up', up], ['same', same], ['down', down]].filter(([, n]) => n > 0);
  return (
    <Flex h={h} gap="2px" borderRadius="pill" overflow="hidden" role="img" aria-label={`${up} went up, ${same} stayed the same, ${down} went down`}>
      {parts.map(([dir, n]) => (
        <Box key={dir} flex={n} minW="2px" bg={TONE[dir]} />
      ))}
    </Flex>
  );
}

/** The shop's best rate over time as a small stepped line: it only moves on a day we read a new rate. */
function RateLine({ points, dir, from, to }) {
  const W = 84;
  const H = 26;
  const PAD = 3;
  const t = (iso) => Date.parse(iso);
  const span = t(to) - t(from) || 1;
  const rates = points.map(([, r]) => r);
  const lo = Math.min(...rates);
  const range = Math.max(...rates) - lo || 1;
  const x = (iso) => (PAD + ((W - 2 * PAD) * (t(iso) - t(from))) / span).toFixed(1);
  const y = (r) => (H - PAD - ((H - 2 * PAD) * (r - lo)) / range).toFixed(1);
  const d =
    `M${x(points[0][0])},${y(points[0][1])}` +
    points.slice(1).map(([day, r]) => ` H${x(day)} V${y(r)}`).join('') +
    ` H${x(to)}`;
  const stroke = `var(--chakra-colors-${TONE[dir]})`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden="true" style={{ flexShrink: 0 }}>
      <path d={d} fill="none" stroke={stroke} strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx={x(to)} cy={y(points[points.length - 1][1])} r="2.6" fill={stroke} />
    </svg>
  );
}

/** Shops whose discount moved: name, the line, then "was → now" and the change. Each row opens the shop's page. */
function Movers({ rows }) {
  const from = rows.map((r) => r.points[0][0]).sort()[0];
  const to = rows.map((r) => r.lastRead).sort().pop();
  return (
    <Box border="1px solid" borderColor="border" borderRadius="12px" overflow="hidden" bg="surface" mb="10px">
      {rows.map((r, i) => (
        <Flex
          key={r.slug}
          className="dealo-press"
          as={RouterLink}
          to={`${ROUTES.brands}/${r.slug}/`}
          align="center"
          gap="10px"
          p="10px 12px"
          borderTop={i ? '1px solid' : 'none'}
          borderColor="border"
          _hover={{ textDecoration: 'none', bg: 'surface2' }}
        >
          <Box flex="1" minW={0}>
            <Text m={0} fontSize="14px" fontWeight={700}>
              {r.name}
            </Text>
            <Text m={0} fontSize="11.5px" color="text3">
              {r.cat}
            </Text>
            {r.dealo && (
              <Text as="span" display="inline-block" mt="3px" px="8px" py="1px" borderRadius="pill" bg="brandSoft" color="brand" fontSize="11px" fontWeight={700}>
                {pct(r.dealo)} on Dealo today
              </Text>
            )}
          </Box>
          <RateLine points={r.points} dir={r.dir} from={from} to={to} />
          <Box textAlign="right" fontFamily="mono" flexShrink={0} sx={{ fontVariantNumeric: 'tabular-nums' }}>
            <Text m={0} fontSize="13px">
              <Text as="span" color="text3">
                {pct(r.was)} →{' '}
              </Text>
              <Text as="span" fontWeight={700}>
                {pct(r.now)}
              </Text>
            </Text>
            <Text m={0} fontSize="11px" fontWeight={700} color={TONE[r.dir]}>
              {r.diff > 0 ? '+' : '−'}
              {pct(Math.abs(r.diff)).replace('%', '')} pts
            </Text>
          </Box>
        </Flex>
      ))}
    </Box>
  );
}

/** Up / same / down for each type of shop; the bar's length is how many shops that type has. */
function TypeBars({ cats }) {
  const most = Math.max(...cats.map((c) => c.total));
  return (
    <Flex direction="column" gap="12px" mb="10px">
      {cats.map((c) => (
        <Box key={c.name}>
          <Flex justify="space-between" align="baseline" gap="8px">
            <Text m={0} fontSize="14px" fontWeight={700}>
              {c.name}
            </Text>
            <Text m={0} fontSize="12px" color="text3">
              {c.total} shops
            </Text>
          </Flex>
          <Box w={`${Math.max(18, (100 * c.total) / most)}%`} my="4px">
            <SplitBar up={c.up} same={c.same} down={c.down} h="8px" />
          </Box>
          <Flex gap="12px" fontSize="12px" fontFamily="mono" color="text2">
            <Text as="span" color="green">
              {c.up} up
            </Text>
            <Text as="span">{c.same} same</Text>
            <Text as="span" color="danger">
              {c.down} down
            </Text>
          </Flex>
        </Box>
      ))}
    </Flex>
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
          {sec.links && (
            <Box m="0 0 10px">
              {sec.links.map((l) => (
                <Text
                  key={l.href}
                  as="a"
                  href={l.href}
                  target="_blank"
                  rel="nofollow noopener noreferrer"
                  display="block"
                  fontSize="13px"
                  fontWeight={700}
                  color="brand"
                  lineHeight={1.5}
                  mb="6px"
                >
                  {l.label} ↗
                </Text>
              ))}
            </Box>
          )}
          {sec.split && (
            <Box mb="10px">
              <SplitBar {...sec.split} />
              <Flex mt="10px" gap="8px">
                {[
                  ['up', 'went up'],
                  ['same', 'stayed the same'],
                  ['down', 'went down'],
                ].map(([dir, label]) => (
                  <Box key={dir} flex="1">
                    <Text m={0} fontFamily="mono" fontSize="24px" fontWeight={700} lineHeight={1.1} color={dir === 'same' ? 'text' : TONE[dir]}>
                      {sec.split[dir]}
                    </Text>
                    <Text m={0} fontSize="12px" fontWeight={600} color="text2">
                      {label}
                    </Text>
                  </Box>
                ))}
              </Flex>
            </Box>
          )}
          {sec.movers && <Movers rows={sec.movers} />}
          {sec.cats && <TypeBars cats={sec.cats} />}
          {sec.cite && (
            <Box border="1px dashed" borderColor="brass" bg="brassSoft" borderRadius="12px" p="12px" mb="10px">
              <Text m={0} fontSize="13px" lineHeight={1.55}>
                <Text as="span" fontWeight={800}>
                  Writing about gift cards?{' '}
                </Text>
                {sec.cite}
              </Text>
            </Box>
          )}
          {sec.table && (
            <Box border="1px solid" borderColor="border" borderRadius="12px" overflow="hidden" mb="10px">
              {sec.table.rows.map((r, i) => (
                <Box
                  key={r.label}
                  className="dealo-press"
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
                Rates checked {shortDate(CHECKED)}.{' '}
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
