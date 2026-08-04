import { Fragment, useEffect } from 'react';
import { Box, Flex, Link, Text } from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';

import FloatingOutlines from '@/components/common/FloatingOutlines';
import Logo from '@/components/common/Logo';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import { gradients } from '@/theme/foundations/colors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { useUiStore } from '@/store/uiStore';

// What actually happens, in the order it happens, said as pictures instead
// of sentences — per PRODUCT.md, design for the lower end of reading
// comfort by default. Replaces the earlier numbered 1-2-3 sentence list;
// the "Heads up" line below it exists because PRODUCT.md's real trust gap
// isn't online payment, it's that buying a gift voucher is an unfamiliar
// concept — naming it here means it's never a surprise on the results page.
const HOW_IT_WORKS = [
  { icon: I.link, label: 'Paste a link' },
  { icon: I.ticket, label: 'Buy a small voucher' },
  { icon: I.pay, label: 'Pay less' },
];

export default function SearchPage() {
  usePageTitle('Search');
  const navigate = useNavigate();
  const runSearch = useSearchStore((s) => s.runSearch);
  const onboardingSeen = useUiStore((s) => s.onboardingSeen);
  const tourActive = useUiStore((s) => s.tourActive);
  const startTour = useUiStore((s) => s.startTour);
  const advanceTour = useUiStore((s) => s.advanceTour);

  const heroGlow = gradients.promptHero;

  // First-ever visit: arm the live guided tour here, not in AppLayout —
  // its first step targets this page's own search box, so it only makes
  // sense to start once this page is actually on screen.
  useEffect(() => {
    if (!onboardingSeen && !tourActive) startTour();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = (q) => {
    if (tourActive) advanceTour();
    runSearch(q); // fire-and-forget; ProductSelectPage subscribes to the store
    navigate(ROUTES.select);
  };

  return (
    <Box position="relative">
      {/* Decorative layer only, clipped on its own — this Box (not the page
          content below) is what has overflow="hidden", since clipping the
          whole page also clipped the search box's own glow/shadow at the
          edges on narrow screens, cutting it off oddly. Isolating the clip
          to just this absolutely-positioned, pointer-events-none layer
          fixes the horizontal page-scroll bug without touching real UI. */}
      <Box position="absolute" inset={0} overflow="hidden" pointerEvents="none" zIndex={0}>
        {/* green hero glow washing in from the top — deliberately wider than
            the page (up to 130%) so it bleeds past the edges on wide screens */}
        <Box
          position="absolute"
          top="-140px"
          left="50%"
          transform="translateX(-50%)"
          w="min(1100px, 130%)"
          h="420px"
          bgImage={heroGlow}
        />

        {/* faint floating product outlines — "Recall" background from the
            2026-07-28 homepage redesign, homepage-only (not used on data-dense
            pages like results/product-picker, where it would compete with
            real content) */}
        <FloatingOutlines />
      </Box>

      <Flex
        direction="column"
        align="center"
        justify="center"
        textAlign="center"
        maxW="640px"
        mx="auto"
        pt={{ base: '12px', md: '64px' }}
        position="relative"
        zIndex={1}
      >
        {/* On mobile, AppLayout's own sticky topbar already shows a small
            "dealo" wordmark right above this page — this bigger hero logo
            repeats it, so the gap between them (pt above + mb below) needs
            to stay tight on phones specifically, not match the generous
            desktop spacing, or it reads as a large empty gap between two
            copies of the same logo. */}
        <Box mb={{ base: '10px', md: '22px' }}>
          <Link as={RouterLink} to={ROUTES.home} _hover={{ textDecoration: 'none' }}>
            <Logo size={{ base: '40px', md: '68px' }} />
          </Link>
        </Box>

        <Text
          fontSize={{ base: '26px', md: '44px' }}
          fontWeight={800}
          letterSpacing="-.03em"
          lineHeight={1.12}
          color="text"
        >
          Never pay full price,{' '}
          <Box as="span" color="brand">
            just search the product.
          </Box>
        </Text>
        <Text fontSize={{ base: '13px', md: '15px' }} color="text2" mt={{ base: '8px', md: '12px' }} maxW="440px" lineHeight={1.5}>
          Paste any product link, or type what you want to buy. We check every store and every
          gift-voucher discount, then show you the cheapest way to actually pay — no credit card
          needed.
        </Text>

        <Box
          data-tour="search-box"
          w="100%"
          mt={{ base: '18px', md: '36px' }}
          bg="surface"
          border="1.5px solid"
          borderColor="brand"
          borderRadius="lg"
          boxShadow="0 0 0 1px var(--chakra-colors-brand), 0 0 22px -6px var(--chakra-colors-brand)"
          p={{ base: '14px', md: '18px' }}
          textAlign="left"
        >
          <Text
            fontSize="10.5px"
            fontWeight={700}
            color="brandText"
            textTransform="uppercase"
            letterSpacing=".05em"
            mb="8px"
          >
            Type product name or paste link here
          </Text>
          <SearchBox
            initialValue=""
            onSubmit={handleSubmit}
            placeholder={'e.g. "Onitsuka Tiger Mexico 66" or paste a link'}
          />
        </Box>

        <Box
          w="100%"
          mt={{ base: '14px', md: '28px' }}
          bg="surface"
          border="1px solid"
          borderColor="border"
          borderRadius="lg"
          p={{ base: '14px 10px', md: '16px 14px' }}
        >
          {/* Grid, not flex — three genuinely equal-width columns (1fr each)
              with the two arrows in their own fixed-width columns between
              them. The earlier flex version gave the icons uneven visual
              spacing because the columns' widths depended on how long each
              label's text happened to be; a grid keeps every icon centered
              in an equal slice of the row regardless of label length. */}
          <Box display="grid" gridTemplateColumns="1fr auto 1fr auto 1fr" alignItems="center">
            {HOW_IT_WORKS.map((step, i) => (
              <Fragment key={step.label}>
                <Flex direction="column" align="center" gap="6px" minW="0" px="4px">
                  <Flex
                    w="38px"
                    h="38px"
                    flex="0 0 38px"
                    borderRadius="12px"
                    align="center"
                    justify="center"
                    bg={i === HOW_IT_WORKS.length - 1 ? 'greenSoft' : 'amberSoft'}
                    color={i === HOW_IT_WORKS.length - 1 ? 'green' : 'amber'}
                  >
                    <step.icon size={20} />
                  </Flex>
                  <Text fontSize="11px" fontWeight={700} color="text" textAlign="center" lineHeight={1.25}>
                    {step.label}
                  </Text>
                </Flex>
                {i < HOW_IT_WORKS.length - 1 && (
                  <Box color="border" px="4px">
                    <I.chevRight size={16} />
                  </Box>
                )}
              </Fragment>
            ))}
          </Box>
        </Box>

        <Flex
          w="100%"
          mt={{ base: '10px', md: '12px' }}
          gap="9px"
          align="flex-start"
          bg="amberSoft"
          borderRadius="md"
          p="11px 12px"
          textAlign="left"
        >
          <Box color="amber" mt="1px" flex="0 0 auto">
            <I.info size={15} />
          </Box>
          <Text fontSize="12px" color="text" lineHeight={1.45}>
            <Text as="span" fontWeight={700}>
              Heads up:
            </Text>{' '}
            step 2 is buying a small voucher yourself. Takes 30 seconds — that's how the discount
            works.
          </Text>
        </Flex>
      </Flex>
    </Box>
  );
}
