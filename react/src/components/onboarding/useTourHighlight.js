import { useUiStore } from '@/store/uiStore';
import { TOUR_STEPS } from './tourSteps';

/**
 * Whether a given real element is the live tour's current target. Replaces
 * the old approach (Spotlight.jsx computing the target's on-screen position
 * in JS via getBoundingClientRect() and rendering a separate position:fixed
 * box elsewhere in the DOM) — that math could mismatch the actual visible
 * viewport on real phones (keyboard open, pinch-zoom, the address bar
 * animating in/out all shift the relationship between the "layout viewport"
 * getBoundingClientRect measures against and what's actually on screen),
 * which is what caused the ring to appear oversized/offset on a real iPhone
 * despite looking correct in desktop testing.
 *
 * Callers render their own ring locally (see TourRing.jsx) inside a
 * `position: relative` wrapper around the real target — pure CSS, laid out
 * by the browser in the target's own coordinate space, so there's no
 * coordinate math left to get wrong.
 */
export function useTourHighlight(stepId) {
  const tourActive = useUiStore((s) => s.tourActive);
  const tourStep = useUiStore((s) => s.tourStep);
  const step = TOUR_STEPS[tourStep];
  const active = Boolean(stepId) && tourActive && step?.id === stepId;
  return { active, dim: active ? step.dim !== false : false };
}
