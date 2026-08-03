import step1 from '@/assets/onboarding/step-1-search.png';
import step2 from '@/assets/onboarding/step-2-pick-product.png';
import step3 from '@/assets/onboarding/step-3-route.png';
import step4 from '@/assets/onboarding/step-4-checkout.png';

/**
 * Content for the first-visit walkthrough (see OnboardingOverlay). Kept
 * separate from the component so copy/screenshots can change without
 * touching the overlay's logic.
 */
export const ONBOARDING_STEPS = [
  {
    image: step1,
    alt: 'Dealo home screen with the search box',
    title: 'Paste a link, or just search',
    caption: "Drop in a product link, or type what you're looking for — no account needed.",
  },
  {
    image: step2,
    alt: 'Dealo product picker showing matching listings',
    title: 'Pick the exact one',
    caption: "We'll show matching listings across stores — tap the one that's really yours.",
  },
  {
    image: step3,
    alt: 'Dealo route screen showing a gift-voucher saving',
    title: 'See the cheaper way to pay',
    caption: 'We find a gift-voucher route that gets you the same product for less.',
  },
  {
    image: step4,
    alt: 'Dealo final price screen showing the amount you pay',
    title: 'Check out for less',
    caption: 'Buy the small voucher, then pay with it at checkout — savings, no catch.',
  },
];
