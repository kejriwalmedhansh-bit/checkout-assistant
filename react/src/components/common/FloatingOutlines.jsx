import { Box } from '@chakra-ui/react';

/**
 * Faint, slowly-drifting product-outline shapes behind the homepage hero —
 * the "Recall" direction from the 2026-07-28 homepage-redesign mockup.
 * Deliberately muted/varied colors (NOT brand navy/copper) per feedback
 * that the brand color should stay reserved for the logo, button, and
 * badges rather than spreading across decorative background objects. The
 * two dashed connector lines ARE brand-colored (copper) on purpose — they're
 * the one part of this background meant to echo the logo's own dashed-route
 * icon, tying it back to the mark rather than existing as pure decoration.
 */

const ICON_PATHS = {
  headphones: (
    <>
      <path d="M6 32 A26 26 0 0 1 58 32" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" />
      <rect x="4" y="30" width="12" height="18" rx="6" fill="none" stroke="currentColor" strokeWidth="3.2" />
      <rect x="48" y="30" width="12" height="18" rx="6" fill="none" stroke="currentColor" strokeWidth="3.2" />
    </>
  ),
  phone: (
    <>
      <rect x="20" y="6" width="24" height="52" rx="6" fill="none" stroke="currentColor" strokeWidth="3" />
      <circle cx="32" cy="14.5" r="1.6" fill="currentColor" />
      <line x1="26" y1="52" x2="38" y2="52" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </>
  ),
  watch: (
    <>
      <rect x="24" y="4" width="16" height="12" rx="3" fill="none" stroke="currentColor" strokeWidth="3" />
      <circle cx="32" cy="32" r="15" fill="none" stroke="currentColor" strokeWidth="3" />
      <rect x="24" y="48" width="16" height="12" rx="3" fill="none" stroke="currentColor" strokeWidth="3" />
      <line x1="32" y1="25" x2="32" y2="32" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <line x1="32" y1="32" x2="37.5" y2="35.5" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </>
  ),
  bag: (
    <>
      <path d="M18 24 q0-12 14-12 q14 0 14 12" fill="none" stroke="currentColor" strokeWidth="3" />
      <rect x="10" y="24" width="44" height="32" rx="6" fill="none" stroke="currentColor" strokeWidth="3" />
      <rect x="26" y="34" width="12" height="9" rx="2" fill="none" stroke="currentColor" strokeWidth="2.6" />
    </>
  ),
  sneaker: (
    <>
      <path
        d="M4 44 Q4 36 12 36 L20 36 L30 24 L38 26 L36 34 L48 34 Q58 34 58 44 L58 48 L4 48 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinejoin="round"
      />
      <line x1="4" y1="44" x2="58" y2="44" stroke="currentColor" strokeWidth="2" />
    </>
  ),
};

// Muted, varied colors for the objects themselves — see comment above.
const MUTED = ['#8A97A6', '#B08A72', '#8FA089', '#A98B9A', '#7E9C9A'];

// Desktop values (top/left/size) are unchanged from the original design.
// mTop/mLeft/mSize are phone-only overrides — only needed for the 3 icons
// that sit in the page's top zone (logo/headline/subtext), which has no
// card behind it on mobile the way it does everywhere else on the page.
// sneaker/watch sit low enough to already be hidden behind the opaque
// "how it works" card on phone widths, so they just get scaled down a
// little defensively rather than repositioned.
const ITEMS = [
  {
    icon: 'phone',
    top: '10%', left: '8%', size: 74,
    mTop: '4%', mLeft: '2%', mSize: 32,
    anim: 'heroDrift1', dur: '40s', delay: '0s',
  },
  {
    icon: 'headphones',
    top: '18%', left: '88%', size: 82,
    mTop: '12%', mLeft: '84%', mSize: 34,
    anim: 'heroDrift2', dur: '46s', delay: '1.3s',
  },
  {
    icon: 'sneaker',
    top: '70%', left: '80%', size: 90,
    mTop: '70%', mLeft: '80%', mSize: 44,
    anim: 'heroDrift3', dur: '52s', delay: '2.6s',
  },
  {
    icon: 'watch',
    top: '78%', left: '10%', size: 62,
    mTop: '78%', mLeft: '10%', mSize: 30,
    anim: 'heroDrift1', dur: '36s', delay: '3.9s',
  },
  {
    icon: 'bag',
    top: '40%', left: '4%', size: 64,
    mTop: '30%', mLeft: '1%', mSize: 28,
    anim: 'heroDrift2', dur: '44s', delay: '5.2s',
  },
];

export default function FloatingOutlines({ opacity = 0.14 }) {
  return (
    <Box position="absolute" inset={0} zIndex={0} pointerEvents="none" overflow="hidden">
      {ITEMS.map((it, i) => (
        <Box
          key={i}
          as="svg"
          className="hero-floater"
          viewBox="0 0 64 64"
          position="absolute"
          top={{ base: it.mTop, md: it.top }}
          left={{ base: it.mLeft, md: it.left }}
          w={{ base: `${it.mSize}px`, md: `${it.size}px` }}
          h={{ base: `${it.mSize}px`, md: `${it.size}px` }}
          color={MUTED[i % MUTED.length]}
          opacity={{ base: opacity * 0.55, md: opacity }}
          sx={{ animationName: it.anim, animationDuration: it.dur, animationDelay: it.delay }}
        >
          {ICON_PATHS[it.icon]}
        </Box>
      ))}
      <Box
        as="svg"
        className="hero-connector"
        position="absolute"
        inset={0}
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        opacity={opacity + 0.1}
      >
        <path
          d="M10,20 Q35,5 55,22 T92,30"
          fill="none"
          stroke="var(--chakra-colors-brass)"
          strokeWidth="0.4"
          strokeDasharray="2 3"
          style={{ animation: 'heroDashMove 55s linear infinite' }}
        />
        <circle cx="92" cy="30" r="1.1" fill="var(--chakra-colors-brass)" />
        <path
          d="M8,78 Q30,90 50,76 T88,72"
          fill="none"
          stroke="var(--chakra-colors-brass)"
          strokeWidth="0.4"
          strokeDasharray="2 3"
          style={{ animation: 'heroDashMove 65s linear infinite reverse' }}
        />
        <circle cx="8" cy="78" r="1.1" fill="var(--chakra-colors-brass)" />
      </Box>
    </Box>
  );
}
