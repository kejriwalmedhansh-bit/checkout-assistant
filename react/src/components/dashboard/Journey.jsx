import { useState } from 'react';
import { Flex, Text } from '@chakra-ui/react';

import { fmt, affiliateUrl, paidForVoucher } from '@/utils/format';
import { useUiStore } from '@/store/uiStore';
import JourneyStepper from './JourneyStepper';
import JourneySpotlight, { JourneyDoneRow } from './JourneySpotlight';

const STEP_META = {
  store: { label: 'Buy at store', tone: 'brand' },
  voucher: { label: 'Gift voucher', tone: 'voucher' },
  pay: { label: 'Pay & done', tone: 'checkout' },
};

/**
 * The recommended-route checklist: buy at the merchant → [buy a Gift
 * Voucher] → pay & done. Rather than three rows all visible and clickable at
 * once (which read as "click anywhere" — no sense of a single connected
 * flow), a horizontal step header shows the whole journey at a glance while
 * only the current step is expanded into a focused card; finished steps
 * collapse into a one-line confirmation. The voucher + checkout steps only
 * exist when the route carries a voucher — a direct-buy route is a single
 * step and skips the stepper header entirely.
 */
export default function Journey({ rec }) {
  const v = rec.voucher || null;
  const sellerLink = rec.sellers?.[0]?.link;
  const [checked, setChecked] = useState({ store: false, voucher: false });
  const [pending, setPending] = useState({ store: false, voucher: false });
  // "Hide" silences hints for this visit only; the sidebar switch is the
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

  const nextStep = (() => {
    if (!checked.store) return 'store';
    if (!v) return null;
    if (!checked.voucher) return 'voucher';
    return 'pay';
  })();

  const paid = v ? paidForVoucher(v) : null;
  const HINT_TEXT = {
    store: v
      ? `Open ${rec.merchant} and put your item in the basket. Don't pay yet — the voucher comes next.`
      : `Open ${rec.merchant} and buy it there — this is already the cheapest way we found.`,
    voucher: `Buy the gift voucher now. You pay ${fmt(paid)} for ${fmt(v?.upi?.voucher_amount)} of ${rec.merchant} credit.`,
    pay: v?.upi?.remainder
      ? `Use the voucher at checkout, then pay the last ${fmt(v.upi.remainder)} any way you like.`
      : 'Use the voucher at checkout — it covers the whole order.',
  };

  const hintVisible = (step) => hintsEnabled && !dismissed && nextStep === step;
  const hideHint = () => setDismissed(true);

  // Direct-buy route: one step, no stepper, no collapsing — mirrors the old
  // single-row behaviour exactly (stays visible, just flips to done).
  if (!v) {
    return (
      <JourneySpotlight
        tone="brand"
        totalSteps={1}
        title={`Buy at ${rec.merchant}`}
        facts={
          <Text fontSize="12px" color="text2" fontFamily="mono">
            Listed at {fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
          </Text>
        }
        link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined}
        checked={checked.store}
        pending={pending.store}
        onCheck={check('store')}
        hintText={HINT_TEXT.store}
        hintVisible={hintVisible('store')}
        onHideHint={hideHint}
      />
    );
  }

  const breakdown = v.upi?.denomination_breakdown || [];
  const singleVoucher = breakdown.length <= 1;
  const steps = ['store', 'voucher', 'pay'].map((key) => ({ key, ...STEP_META[key] }));

  const SPOTLIGHT = {
    store: {
      tone: 'brand',
      stepNumber: 1,
      title: `Buy at ${rec.merchant}`,
      facts: (
        <Text fontSize="12px" color="text2" fontFamily="mono">
          Listed at {fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
        </Text>
      ),
      link: sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined,
      checked: checked.store,
      pending: pending.store,
      onCheck: check('store'),
    },
    voucher: {
      tone: 'voucher',
      stepNumber: 2,
      title: 'Buy a Gift Voucher',
      facts: (
        <>
          {singleVoucher ? (
            <Text fontSize="12px" color="text2" fontFamily="mono">
              {fmt(v.upi?.voucher_amount)} Gift Voucher
            </Text>
          ) : (
            <Flex direction="column" gap="4px" mb="2px">
              {breakdown.map((b, i) => (
                <Flex key={i} justify="space-between" fontSize="12px" fontFamily="mono" color="text2">
                  <Text as="span">{b.count} × {fmt(b.denom)}</Text>
                </Flex>
              ))}
            </Flex>
          )}
          <Text fontSize="12px" color="amber" fontWeight={700} mt="6px">
            {v.upi?.pct}% off — you pay {fmt(paid)}
          </Text>
        </>
      ),
      link: v.voucher_url ? { href: v.voucher_url, label: 'Get voucher' } : undefined,
      checked: checked.voucher,
      pending: pending.voucher,
      onCheck: check('voucher'),
    },
    pay: {
      tone: 'checkout',
      stepNumber: 3,
      title: 'Pay & done',
      facts: (
        <Text fontSize="12px" color="text2" fontFamily="mono">
          {v.upi?.remainder ? `Pay ${fmt(v.upi.remainder)} remaining` : 'Full order covered'}
        </Text>
      ),
      ready: checked.voucher,
    },
  };

  const current = SPOTLIGHT[nextStep];

  return (
    <>
      <JourneyStepper steps={steps} currentKey={nextStep} />

      {checked.store && nextStep !== 'store' && <JourneyDoneRow label={`Bought at ${rec.merchant}`} />}
      {checked.voucher && nextStep !== 'voucher' && <JourneyDoneRow label="Gift Voucher purchased" />}

      <JourneySpotlight
        {...current}
        totalSteps={3}
        hintText={HINT_TEXT[nextStep]}
        hintVisible={hintVisible(nextStep)}
        onHideHint={hideHint}
      />
    </>
  );
}
