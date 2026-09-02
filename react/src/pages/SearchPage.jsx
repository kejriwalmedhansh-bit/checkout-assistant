import { Fragment, useEffect } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';

import FloatingOutlines from '@/components/common/FloatingOutlines';
import Logo from '@/components/common/Logo';
import SearchBox from '@/components/common/SearchBox';
import { HOW_IT_WORKS } from '@/components/onboarding/tourSteps';
import TourRing from '@/components/onboarding/TourRing';
import { useTourHighlight } from '@/components/onboarding/useTourHighlight';
import { gradients } from '@/theme/foundations/colors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { useUiStore } from '@/store/uiStore';

export default function SearchPage() {
  usePageTitle('Search');
  const navigate = useNavigate();
  const runSearch = useSearchStore((s) => s.runSearch);
  const query = useSearchStore((s) => s.query);
  const onboardingSeen = useUiStore((s) => s.onboardingSeen);
  const tourActive = useUiStore((s) => s.tourActive);
  const startTour = useUiStore((s) => s.startTour);
  const advanceTour = useUiStore((s) => s.advanceTour);
  const { active: searchBoxHighlighted, dim: searchBoxDim } = useTourHighlight('search-box');

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
    <Box
      position="relative"
      flex="1"
      display="flex"
      alignItems="center"
      justifyContent="center"
    >
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
        maxW="600px"
        mx="auto"
        w="100%"
        position="relative"
        zIndex={1}
      >
        {/* Logo leads on this page — search box, headline and everything
            below now read in natural top-down order instead of the old
            search-box-then-logo-below-it sequence, which is what read as
            "weird." AppLayout's sidebar/topbar logo is a separate nav
            element, not a duplicate of this one. Not a link: this page IS
            home, so it has nowhere useful to navigate to — it previously
            looked clickable (hover states, cursor) but did nothing. */}
        <Box mb={{ base: '28px', md: '40px' }}>
          <Logo size={{ base: '30px', md: '38px' }} />
        </Box>

        <Text
          as="h1"
          fontSize={{ base: '24px', md: '38px' }}
          fontWeight={800}
          letterSpacing="-.03em"
          lineHeight={1.14}
          color="text"
          m={0}
        >
          Never pay full price.{' '}
          <Box as="span" color="brand">
            Just search.
          </Box>
        </Text>

        <Box
          position="relative"
          zIndex={searchBoxHighlighted && searchBoxDim ? 201 : undefined}
          w="100%"
          mt={{ base: '32px', md: '52px' }}
          bg="surface"
          border="1.5px solid"
          borderColor="brand"
          borderRadius="lg"
          boxShadow="0 0 0 1px var(--chakra-colors-brand), 0 0 22px -6px var(--chakra-colors-brand)"
          p={{ base: '14px', md: '18px' }}
          textAlign="left"
        >
          {searchBoxHighlighted && <TourRing />}
          <SearchBox
            initialValue={query}
            onSubmit={handleSubmit}
            placeholder={'e.g. "Onitsuka Tiger Mexico 66" or paste a link'}
          />
        </Box>

        {/* The 3-icon strip is the "how it works" copy — pictures instead
            of a sentence, per PRODUCT.md. It also carries the one thing the
            old paragraph + separate "Heads up" banner used to spell out in
            two blocks of prose: step 2's icon (a ticket, not a card) is
            the entire "you're buying a voucher, not paying us" signal, and
            the caption underneath gives the one fact a picture can't:
            that it only takes 30 seconds. */}
        <Box
          w="100%"
          mt={{ base: '28px', md: '44px' }}
          bg="surface"
          border="1px solid"
          borderColor="border"
          borderRadius="lg"
          p={{ base: '16px 10px 12px', md: '20px 14px 14px' }}
        >
          {/* Grid, not flex — three genuinely equal-width columns (1fr each)
              with the two arrows in their own fixed-width columns between
              them. The earlier flex version gave the icons uneven visual
              spacing because the columns' widths depended on how long each
              label's text happened to be; a grid keeps every icon centered
              in an equal slice of the row regardless of label length. */}
          <Box display="grid" gridTemplateColumns="1fr auto 1fr auto 1fr" alignItems="start">
            {HOW_IT_WORKS.map((step, i) => (
              <Fragment key={step.label}>
                <Flex direction="column" align="center" gap="6px" minW="0" px="4px">
                  <Flex
                    w="42px"
                    h="42px"
                    flex="0 0 42px"
                    borderRadius="12px"
                    align="center"
                    justify="center"
                    bg={i === HOW_IT_WORKS.length - 1 ? 'greenSoft' : 'amberSoft'}
                    color={i === HOW_IT_WORKS.length - 1 ? 'green' : 'amber'}
                  >
                    <step.icon size={22} />
                  </Flex>
                  <Text fontSize="11px" fontWeight={700} color="text" textAlign="center" lineHeight={1.25}>
                    {step.label}
                  </Text>
                  {step.caption && (
                    <Text
                      fontFamily="mono"
                      fontSize="9.5px"
                      color="text3"
                      textAlign="center"
                      lineHeight={1.2}
                      mt="-2px"
                    >
                      {step.caption}
                    </Text>
                  )}
                </Flex>
                {/* Connector echoes the logo mark's own dashed path instead
                    of a generic chevron — the same visual language used for
                    "route" appears here as literally connecting the steps
                    of a route. */}
                {i < HOW_IT_WORKS.length - 1 && (
                  <Box mt="19px" px="2px" flex="0 0 auto">
                    <svg width="22" height="10" viewBox="0 0 22 10" fill="none">
                      <path
                        d="M0 5H22"
                        stroke="var(--chakra-colors-borderStrong)"
                        strokeWidth="2"
                        strokeDasharray="4 4"
                      />
                      <path
                        d="M17 1L21 5L17 9"
                        stroke="var(--chakra-colors-borderStrong)"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </Box>
                )}
              </Fragment>
            ))}
          </Box>
        </Box>
      </Flex>
    </Box>
  );
}
