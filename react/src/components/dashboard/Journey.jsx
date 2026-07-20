import { useState } from 'react';
import { Box, Flex } from '@chakra-ui/react';
import { AnimatePresence } from 'framer-motion';

import { I } from '@/components/common/icons';
import StepHint from '@/components/hints/StepHint';
import { fmt, affiliateUrl, paidForVoucher } from '@/utils/format';
import { useUiStore } from '@/store/uiStore';
import JourneyStep, { JourneyConnector } from './JourneyStep';

/**
 * The recommended-route checklist, vertical:
 *   buy at the merchant → [buy a Gift Voucher] → pay & done.
 * Each action button opens the real link in a new tab and checks itself off
 * — a to-do list, not a locked sequence (either can be done first). The
 * final "pay" row has no button; it just reflects ready once the voucher
 * step is checked. The voucher + checkout rows only appear when the route
 * carries a voucher.
 *
 * A single "do this next" bubble tracks the first unfinished row and moves
 * down as rows get ticked off, leaving once the route is complete. It reads
 * this component's own `checked` state rather than keeping a parallel copy,
 * so it can never point at something already done.
 */
export default function Journey({ rec }) {
  const v = rec.voucher || null;
  const sellerLink = rec.sellers?.[0]?.link;
  const [checked, setChecked] = useState({ store: false, voucher: false });
  const [pending, setPending] = useState({ store: false, voucher: false });
  // "Hide" silences the bubbles for this visit only; the sidebar switch is the
  // durable off. Two different intentions, so two separate controls.
  const [dismissed, setDismissed] = useState(false);
  const hintsEnabled = useUiStore((s) => s.hintsEnabled);

  // A brief "pending" beat before the checkmark lands — an instant flip is
  // easy to miss; this makes the confirmation a moment you actually notice.
  const check = (key) => () => {
    setPending((p) => ({ ...p, [key]: true }));
    setTimeout(() => {
      setPending((p) => ({ ...p, [key]: false }));
      setChecked((c) => ({ ...c, [key]: true }));
    }, 550);
  };

  // First unfinished row, in the order they're numbered on screen. Null once
  // there's nothing left to prompt — the bubble should leave, not linger.
  const nextStep = (() => {
    if (!checked.store) return 'store';
    if (!v) return null;
    if (!checked.voucher) return 'voucher';
    return 'pay';
  })();

  const paid = v ? paidForVoucher(v) : null;
  const HINT_TEXT = {
    // On a direct buy there is no second step, so "don't pay yet" would be
    // actively wrong — paying is the whole thing. Only a voucher route gets
    // told to hold off.
    store: v
      ? `Open ${rec.merchant} and put your item in the basket. Don't pay yet — the voucher comes next.`
      : `Open ${rec.merchant} and buy it there — this is already the cheapest way we found.`,
    voucher: `Buy the gift voucher now. You pay ${fmt(paid)} for ${fmt(v?.upi?.voucher_amount)} of ${rec.merchant} credit.`,
    pay: v?.upi?.remainder
      ? `Use the voucher at checkout, then pay the last ${fmt(v.upi.remainder)} any way you like.`
      : 'Use the voucher at checkout — it covers the whole order.',
  };

  const activeHint = hintsEnabled && !dismissed && nextStep ? nextStep : null;
  const hintFor = (step) => (
    <AnimatePresence mode="wait" initial={false}>
      {activeHint === step && (
        <StepHint key={step} text={HINT_TEXT[step]} onHide={() => setDismissed(true)} />
      )}
    </AnimatePresence>
  );

  return (
    <Flex direction="column" mb="4px">
      <Box>
        <JourneyStep
          tone="brand"
          icon={I.store}
          label={`1. Buy at ${rec.merchant}`}
          detail={`Listed at ${fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}`}
          link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined}
          checked={checked.store}
          pending={pending.store}
          hinted={activeHint === 'store'}
          onCheck={check('store')}
        />
        {hintFor('store')}
      </Box>

      {v && (
        <>
          <JourneyConnector />
          <Box>
            <JourneyStep
              tone="voucher"
              icon={I.ticket}
              label="2. Buy a Gift Voucher"
              detail={`${v.upi?.purchase_breakdown || fmt(v.upi?.voucher_amount)} — ${v.upi?.pct}% off`}
              link={v.voucher_url ? { href: v.voucher_url, label: 'Get voucher' } : undefined}
              checked={checked.voucher}
              pending={pending.voucher}
              hinted={activeHint === 'voucher'}
              onCheck={check('voucher')}
            />
            {hintFor('voucher')}
          </Box>
          <JourneyConnector />
          <Box>
            <JourneyStep
              tone="checkout"
              icon={I.checkCircle}
              label="3. Pay & done"
              detail={
                v.upi?.remainder ? `Pay ${fmt(v.upi.remainder)} remaining` : 'Full order covered'
              }
              ready={checked.voucher}
            />
            {hintFor('pay')}
          </Box>
        </>
      )}
    </Flex>
  );
}
