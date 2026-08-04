import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Box, Text } from '@chakra-ui/react';
import { useReducedMotion } from 'framer-motion';

import { useUiStore } from '@/store/uiStore';
import { track } from '@/utils/analytics';
import { TOUR_STEPS } from './tourSteps';

const PAD = 8; // gap between the highlighted ring and the real element's edge

/**
 * The live, first-search guided tour. Unlike the old screenshot-carousel
 * modal, this doesn't show a picture of the app — it puts a highlighted
 * ring around the actual element the user should tap next (found live via
 * `document.querySelector('[data-tour="<id>"]')`), with the explanation
 * text in a bar fixed to the bottom of the screen (see AppLayout's matching
 * reserved padding) rather than floating next to the target, so it can
 * never end up covering real page content. It never blocks input: the dim
 * layer and ring are `pointer-events: none`, so the real button underneath
 * still works exactly as normal — the tour is just narration, not a gate.
 *
 * Steps advance when the user does the real thing (see tourSteps.js and the
 * `advanceTour()` calls at each page's own submit/select/click handler),
 * never on a timer. If a step's target isn't in the DOM yet (e.g. search
 * results still loading), this polls until it appears rather than giving up.
 */
export default function Spotlight() {
  const tourActive = useUiStore((s) => s.tourActive);
  const tourStep = useUiStore((s) => s.tourStep);
  const skipTour = useUiStore((s) => s.skipTour);
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed);
  const prefersReduced = useReducedMotion();

  const [rect, setRect] = useState(null);
  const rafRef = useRef(null);
  const step = TOUR_STEPS[tourStep];

  useEffect(() => {
    if (!tourActive || !step) {
      setRect(null);
      return undefined;
    }

    let cancelled = false;
    const measureOnce = () => {
      const el = document.querySelector(`[data-tour="${step.id}"]`);
      if (el) {
        const r = el.getBoundingClientRect();
        setRect({ top: r.top, left: r.left, width: r.width, height: r.height, radius: getComputedStyle(el).borderRadius });
      } else {
        setRect(null);
      }
    };
    const loop = () => {
      if (cancelled) return;
      measureOnce();
      rafRef.current = requestAnimationFrame(loop);
    };
    loop();

    // rAF is throttled/paused while the tab is backgrounded — and this
    // tour's own step 3 (buy the voucher) opens Gyftr in a new tab, which
    // backgrounds this one mid-loop. Without this, the highlight can freeze
    // on whatever rect it last measured (sometimes mid-transition) and stay
    // wrong even after the loop resumes, since resuming doesn't imply an
    // immediate frame. Force one fresh measurement the instant focus/
    // visibility changes, on top of the regular loop.
    window.addEventListener('focus', measureOnce);
    document.addEventListener('visibilitychange', measureOnce);

    return () => {
      cancelled = true;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.removeEventListener('focus', measureOnce);
      document.removeEventListener('visibilitychange', measureOnce);
    };
  }, [tourActive, tourStep, step]);

  useEffect(() => {
    if (tourActive && step) track('Tour Step Shown', { step_index: tourStep, step_id: step.id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourActive, tourStep]);

  if (!tourActive || !step || !rect) return null;

  const top = rect.top - PAD;
  const left = rect.left - PAD;
  const width = rect.width + PAD * 2;
  const height = rect.height + PAD * 2;

  return createPortal(
    <>
      {/* Steps can set `dim: false` (e.g. the product picker, ringing just
          the first card's photo as a demo) to skip the full-page dim layer
          while still showing the ring — a ring alone on a small target
          reads as "here's an example," not "only this works," so it
          doesn't have the old "why is everything else faded" problem that
          dimming the whole list did. */}
      {step.dim !== false && (
        /* Dim layer with a cutout: a box positioned exactly over the
           target whose box-shadow covers the rest of the viewport.
           Pointer-events are off throughout — the real element
           underneath stays clickable. */
        <Box
          position="fixed"
          zIndex={200}
          pointerEvents="none"
          top={`${top}px`}
          left={`${left}px`}
          w={`${width}px`}
          h={`${height}px`}
          borderRadius={rect.radius && rect.radius !== '0px' ? rect.radius : '12px'}
          boxShadow="0 0 0 9999px rgba(10,12,10,.6)"
        />
      )}
      {/* No CSS transition on position/size here (deliberately removed) —
          this box is already repositioned every animation frame by the
          polling loop above, which is its own smooth, 60fps "animation."
          A separate CSS transition on top of that was chasing a
          continuously-updating target (worse yet, one that's sometimes
          itself mid-animation, e.g. the results page's own step-switch
          slide or a card's entrance scale), and two independent
          animations racing each other is exactly what read as a jittery,
          unstable border. Snapping instantly to each frame's real
          measurement tracks the true position with zero lag instead. */}
      <Box
        position="fixed"
        zIndex={201}
        pointerEvents="none"
        top={`${top}px`}
        left={`${left}px`}
        w={`${width}px`}
        h={`${height}px`}
        borderRadius={rect.radius && rect.radius !== '0px' ? rect.radius : '12px'}
        border="2px solid"
        borderColor="brass"
        sx={{
          '@keyframes dealoSpotlightPulse': {
            '0%, 100%': { boxShadow: '0 0 0 0px var(--chakra-colors-brass)' },
            '50%': { boxShadow: '0 0 0 5px transparent' },
          },
          animation: prefersReduced ? 'none' : 'dealoSpotlightPulse 1.8s ease-in-out infinite',
        }}
      />

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
