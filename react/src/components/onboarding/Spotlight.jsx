import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';
import { Box, Text } from '@chakra-ui/react';

import { useUiStore } from '@/store/uiStore';
import { track } from '@/utils/analytics';
import { TOUR_STEPS } from './tourSteps';

/**
 * The live, first-search guided tour's full-page dim and the explanation
 * bar. The ring itself is no longer rendered here — each target (the
 * search box, a picker card's photo, a Journey step) renders its own via
 * TourRing.jsx, positioned with plain CSS relative to itself (see
 * useTourHighlight.js for why: computing an element's on-screen position in
 * JS and rendering a separate matching box elsewhere was fragile on real
 * phones). This component only needs to know *whether* to dim the page
 * (steps can opt out via `dim: false`, e.g. the picker, where dimming every
 * other card would wrongly suggest only one is tappable) and what to say in
 * the bottom bar — neither needs any target measurement at all.
 *
 * Steps advance when the user does the real thing (see tourSteps.js and the
 * `advanceTour()` calls at each page's own submit/select/click handler),
 * never on a timer.
 */
export default function Spotlight() {
  const tourActive = useUiStore((s) => s.tourActive);
  const tourStep = useUiStore((s) => s.tourStep);
  const skipTour = useUiStore((s) => s.skipTour);
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const step = TOUR_STEPS[tourStep];
  const location = useLocation();
  // The current route not matching this step's own page means `tourStep`
  // and what's actually on screen have fallen out of sync (stale route,
  // browser back/forward, a direct link) — stay silent rather than show
  // instructions for a step that isn't the one visible. Not a terminal
  // skip: navigating back to the right page brings the bar back correctly.
  const onExpectedPage = !step?.page || location.pathname === step.page;

  useEffect(() => {
    if (tourActive && step && onExpectedPage) track('Tour Step Shown', { step_index: tourStep, step_id: step.id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourActive, tourStep, onExpectedPage]);

  if (!tourActive || !step || !onExpectedPage) return null;

  return createPortal(
    <>
      {step.dim !== false && (
        // A plain full-viewport dim — no target-shaped cutout, no
        // coordinate math. The highlighted target rises above this via its
        // own locally-elevated z-index (see useTourHighlight.js's `dim`
        // return value, applied by each target) instead of a box-shadow
        // "hole" punched at a JS-computed position.
        <Box position="fixed" inset={0} zIndex={200} pointerEvents="none" bg="rgba(10,12,10,.6)" />
      )}

      {/* The explanatory text used to float right next to the target,
          wherever that happened to land — which meant it could (and did)
          land on top of real page content (the home page's "how it works"
          row, the heads-up banner) with no way to predict or avoid it for
          every page/target combination. Pinned to the bottom edge instead:
          always the same place, so nothing is ever covered by surprise.
          AppLayout reserves matching bottom padding on `main` while the
          tour is active, so even scrolled to the very end of a page,
          there's blank reserved space behind the bar, not real content. */}
      <Box
        position="fixed"
        zIndex={202}
        bottom={0}
        // Matches AppLayout's own sidebar width logic (only present at `lg`
        // and up — below that it's a drawer, not permanent chrome) so the
        // bar spans exactly the main content column, never overlapping the
        // sidebar's own bottom content (e.g. the "Step hints" toggle).
        left={{ base: 0, lg: sidebarCollapsed ? '76px' : '264px' }}
        right={0}
        bg="surface"
        borderTop="1.5px solid"
        borderColor="brass"
        boxShadow="0 -10px 28px -10px rgba(10,12,10,.3)"
        px={{ base: '16px', md: '24px' }}
        py="14px"
      >
        <Box maxW="640px" mx="auto" display="flex" alignItems="center" gap="16px">
          <Box flex="1" minW={0}>
            <Text fontSize="10px" fontWeight={700} color="text3" textTransform="uppercase" letterSpacing=".05em" mb="4px">
              Step {tourStep + 1} of {TOUR_STEPS.length}
            </Text>
            <Text fontSize="13.5px" color="text" lineHeight={1.45} fontWeight={600}>
              {step.text}
            </Text>
          </Box>
          <Box
            as="button"
            type="button"
            onClick={() => {
              track('Tour Skipped', { step_index: tourStep, step_id: step.id });
              skipTour();
            }}
            flex="0 0 auto"
            fontSize="11.5px"
            fontWeight={700}
            color="text3"
            textDecoration="underline"
            whiteSpace="nowrap"
            _hover={{ color: 'text2' }}
          >
            Skip tour
          </Box>
        </Box>
      </Box>
    </>,
    document.body,
  );
}
