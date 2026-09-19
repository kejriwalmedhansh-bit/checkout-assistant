/**
 * One motion vocabulary for the whole site, so every entrance, press and
 * change of state moves the same way. Strong ease-out: movement starts at
 * once (feels responsive) and settles gently (feels calm, not bouncy).
 *
 * Durations: presses ~150ms, small swaps ~250ms, page content ~400ms.
 * Anything longer than that is decoration and should be rare.
 */
export const EASE_OUT = [0.23, 1, 0.32, 1];
export const EASE_OUT_CSS = 'cubic-bezier(0.23, 1, 0.32, 1)';
export const EASE_IN_OUT_CSS = 'cubic-bezier(0.65, 0, 0.35, 1)';

/** Content arriving on a page: short rise + fade, never from nothing. */
export const enter = (delay = 0) => ({
  initial: { opacity: 0, transform: 'translateY(8px)' },
  animate: { opacity: 1, transform: 'translateY(0px)' },
  transition: { duration: 0.4, delay, ease: EASE_OUT },
});
