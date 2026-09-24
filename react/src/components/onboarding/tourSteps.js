import { I } from '@/components/common/icons';

// What actually happens, in the order it happens, said as pictures instead
// of sentences — per PRODUCT.md, design for the lower end of reading
// comfort by default. Shown inline on the homepage (SearchPage.jsx).
export const HOW_IT_WORKS = [
  { icon: I.link, label: 'Paste a link' },
  // `caption` is the one fact the icon alone can't carry — that step 2 is a
  // real, verified purchase and takes seconds, not a scam pattern. Replaces
  // the old separate "Heads up" paragraph on the homepage (SearchPage.jsx)
  // per the design system's copy rule that this mechanic must always be
  // explained, just said in as few words as the rule allows.
  { icon: I.ticket, label: 'Buy a voucher', caption: '30 sec · verified' },
  { icon: I.pay, label: 'Pay less' },
];
