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
 * modal, this doesn't show a picture of the app — it dims the real page and
 * puts a highlighted ring around the actual element the user should tap
 * next (found live via `document.querySelector('[data-tour="<id>"]')`), with
 * a short instruction bubble beside it. It never blocks input: the dim
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

  // Steps flagged `noDim` (e.g. the product picker, where every card is
  // tappable — dimming the rest would wrongly suggest otherwise) skip the
  // dim/ring entirely and just anchor the tooltip above the target's own
  // top edge, unconditionally — there's no ring to avoid overlapping, and
  // targets like the whole candidate list can be far taller than the
  // viewport, so the below-target placement math doesn't apply.
  const tooltipTop = step.noDim ? top - 12 : (() => {
    const spaceBelow = window.innerHeight - (top + height);
    return spaceBelow < 140 ? top - 12 : top + height + 12;
  })();
  const placeAbove = step.noDim ? true : window.innerHeight - (top + height) < 140;

  return createPortal(
    <>
      {!step.noDim && (
        <>
          {/* Dim layer with a cutout: a box positioned exactly over the
              target whose box-shadow covers the rest of the viewport.
              Pointer-events are off throughout — the real element
              underneath stays clickable. */}
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
            transition="top .25s ease, left .25s ease, width .25s ease, height .25s ease"
          />
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
            transition="top .25s ease, left .25s ease, width .25s ease, height .25s ease"
            sx={{
              '@keyframes dealoSpotlightPulse': {
                '0%, 100%': { boxShadow: '0 0 0 0px var(--chakra-colors-brass)' },
                '50%': { boxShadow: '0 0 0 5px transparent' },
              },
              animation: prefersReduced ? 'none' : 'dealoSpotlightPulse 1.8s ease-in-out infinite',
            }}
          />
        </>
      )}

      <Box
        position="fixed"
        zIndex={202}
        top={`${tooltipTop}px`}
        left={`${Math.min(Math.max(left, 12), window.innerWidth - 292)}px`}
        transform={placeAbove ? 'translateY(-100%)' : 'none'}
        w="280px"
        bg="surface"
        border="1.5px solid"
        borderColor="brass"
        borderRadius="14px"
        boxShadow="0 12px 32px -8px rgba(10,12,10,.35)"
        p="14px 16px"
      >
        <Text fontSize="10px" fontWeight={700} color="text3" textTransform="uppercase" letterSpacing=".05em" mb="4px">
          Step {tourStep + 1} of {TOUR_STEPS.length}
        </Text>
        <Text fontSize="13.5px" color="text" lineHeight={1.45} fontWeight={600}>
          {step.text}
        </Text>
        <Box
          as="button"
          type="button"
          onClick={() => {
            track('Tour Skipped', { step_index: tourStep, step_id: step.id });
            skipTour();
          }}
          mt="10px"
          fontSize="11.5px"
          fontWeight={700}
          color="text3"
          textDecoration="underline"
          _hover={{ color: 'text2' }}
        >
          Skip tour
        </Box>
      </Box>
    </>,
    document.body,
  );
}
