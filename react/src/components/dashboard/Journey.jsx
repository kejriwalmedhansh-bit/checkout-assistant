import { useEffect, useRef, useState } from 'react';
import { Box, Flex, Text, useToast } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import InfoNote from '@/components/common/InfoNote';
import { fmt, affiliateUrl, paidForVoucher } from '@/utils/format';
import { useUiStore } from '@/store/uiStore';
import { track } from '@/utils/analytics';
import JourneyRow from './JourneyRow';
import JourneyChips from './JourneyChips';
import JourneyPanels from './JourneyPanels';

/**
 * The recommended-route checklist: [buy a Gift Voucher] → checkout at the
 * merchant. The voucher comes first, not last — it's the step that actually
 * matters (where the money is saved) and the one most at risk of being
 * skipped if it's buried behind an easier warm-up step; putting it first
 * means there's no earlier "easy" step for someone to finish and wander off
 * before reaching the one that counts.
 *
 * Only two steps, not three: "add to cart" and "pay" used to be separate
 * steps, but Dealo can't observe either happening on the merchant's own
 * site — the user does both in one continuous visit and never comes back to
 * Dealo in between. Splitting them was artificial UI sequencing, not a real
 * signal, so they're now one instruction block: add to cart, apply the
 * code, pay whatever's left.
 *
 * Layout: a numbered, arrow-linked JourneyChips strip stays visible above a
 * single JourneyPanels viewport showing one step's full detail at a time —
 * a long vertical stack of fully-expanded steps measurably cost
 * scroll-driven drop-off, so only the step being viewed renders at full
 * size; nothing about the sequence itself is hidden, since the chip strip
 * alone already shows both steps, their order, and which are done.
 * Completing a step (currentStep changing) carries the view forward on its
 * own; tapping a chip or dragging the panel lets you browse freely without
 * losing progress.
 */
export default function Journey({ rec }) {
  const v = rec.voucher || null;
  const sourceLabel = v?.voucher_source === 'maximize' ? 'Maximize' : 'Gyftr';
  const sellerLink = rec.sellers?.[0]?.link;
  const [checked, setChecked] = useState({ voucher: false, checkout: false });
  const [pending, setPending] = useState({ voucher: false, checkout: false });
  // "Hide" silences a hint for this visit only; the sidebar switch is the
  // durable off. The voucher step has no dismissible hint of its own — its
  // "why this helps" explanation lives behind the discount line's own
  // InfoNote instead (see HINT_DETAIL below), since it's tied to a specific
  // number rather than a general nudge.
  const [dismissed, setDismissed] = useState({ checkout: false });
  const hintsEnabled = useUiStore((s) => s.hintsEnabled);
  const tourActive = useUiStore((s) => s.tourActive);
  const tourStep = useUiStore((s) => s.tourStep);
  const advanceTour = useUiStore((s) => s.advanceTour);
  const toast = useToast();
  // Tour steps 2 and 3 (see tourSteps.js) target this component's own
  // voucher-buy and checkout-open buttons — advancing here, at the same
  // click that already checks the step off, keeps the tour tied to the
  // real action instead of a separate "next" tap.
  const TOUR_STEP_FOR_KEY = { voucher: 2, checkout: 3 };

  // A brief "pending" beat before the checkmark lands — an instant flip is
  // easy to miss; this makes the confirmation a moment you actually notice.
  const check = (key) => () => {
    track('Clicked Buy Link', { step: key, merchant: rec.merchant, has_voucher: Boolean(v) });
    if (tourActive && tourStep === TOUR_STEP_FOR_KEY[key]) advanceTour();
    if (key === 'voucher' && v) {
      toast({
        title: `Opened ${sourceLabel} in a new tab`,
        description: `Come back here once you've got the voucher — you'll pay the rest at ${rec.merchant}.`,
        status: 'info',
        duration: 6000,
        isClosable: true,
        position: 'bottom',
      });
    }
    setPending((p) => ({ ...p, [key]: true }));
    setTimeout(() => {
      setPending((p) => ({ ...p, [key]: false }));
      setChecked((c) => ({ ...c, [key]: true }));
    }, 550);
  };

  // "Welcome back" nudge: fires once, the first time the tab regains focus
  // after the voucher was bought but before checkout is done — the same
  // return-detection Spotlight.jsx uses, for the same reason (Gyftr opens
  // in a new tab and backgrounds this one). Applies to every user, not just
  // those mid-tour, since the "come back here" gap is universal. Guarded by
  // a ref (not state) so it can't itself trigger a re-render loop, and
  // reset whenever the voucher gets checked again (a fresh alternate route,
  // for instance) so it's armed for the next return.
  const welcomedBackRef = useRef(false);
  useEffect(() => {
    welcomedBackRef.current = false;
  }, [checked.voucher]);
  useEffect(() => {
    if (!v) return undefined;
    const onReturn = () => {
      if (document.visibilityState !== 'visible') return;
      if (checked.voucher && !checked.checkout && !welcomedBackRef.current) {
        welcomedBackRef.current = true;
        toast({
          title: 'Welcome back',
          description: `Continue to Step 2 — pay at ${rec.merchant}.`,
          status: 'info',
          duration: 5000,
          isClosable: true,
          position: 'bottom',
        });
      }
    };
    window.addEventListener('focus', onReturn);
    document.addEventListener('visibilitychange', onReturn);
    return () => {
      window.removeEventListener('focus', onReturn);
      document.removeEventListener('visibilitychange', onReturn);
    };
  }, [v, checked.voucher, checked.checkout, rec.merchant, toast]);

  const paid = v ? paidForVoucher(v) : null;
  // Short line shown by default; DETAIL is the original full sentence, one
  // tap away behind the row's own InfoNote toggle — same content as before,
  // just not all of it on screen at once.
  const HINT_TEXT = {
    checkout: v?.upi?.remainder
      ? `Add to cart, apply the code, then pay ${fmt(v.upi.remainder)}.`
      : v
        ? 'Add to cart and apply the code — it covers your order.'
        : 'This is the cheapest price we found.',
  };
  const HINT_DETAIL = {
    checkout: v
      ? `Open ${rec.merchant}, add your item to the basket, and apply your voucher code at checkout${
          v.upi?.remainder ? `, then pay the last ${fmt(v.upi.remainder)} any way you like` : ' — it covers your whole order'
        }.`
      : `Open ${rec.merchant} and buy it there — this is already the cheapest way we found.`,
  };

  // Both hints show at once, each under its own step — not just whichever
  // step is next. Matches the row itself: nothing about a step is hidden
  // just because you haven't reached it yet.
  const hintVisible = (step) => hintsEnabled && !dismissed[step];
  const hideHint = (step) => () => setDismissed((d) => ({ ...d, [step]: true }));

  // Which step is next — moves forward as steps are checked off, so the
  // glow travels through the flow instead of sitting on one fixed step.
  const currentStep = checked.voucher ? 'checkout' : 'voucher';
  const STEP_INDEX = { voucher: 0, checkout: 1 };

  // Which step's full detail is on screen right now (see JourneyPanels).
  // Tapping a chip or swiping sets this directly for browsing; completing a
  // step (currentStep changing) carries the view forward automatically, so
  // finishing an action moves you on without a separate "next" tap.
  const [viewIndex, setViewIndex] = useState(0);
  useEffect(() => {
    setViewIndex(STEP_INDEX[currentStep]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep]);

  // A route with no voucher has nothing for the tour's "buy the voucher"
  // step (2) to point at — without this it would sit polling forever for an
  // element that never appears. Skip straight to step 3, whose target
  // (checkout-open) the direct-buy row below still provides.
  useEffect(() => {
    if (!v && tourActive && tourStep === 2) advanceTour();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v, tourActive, tourStep]);

  // Direct-buy route (no voucher available): one row, no rail, no framing
  // line, no numbering — mirrors the old single-row behaviour exactly.
  if (!v) {
    return (
      <JourneyRow
        tone="brand"
        icon={I.store}
        tourId="checkout-open"
        label={`Buy at ${rec.merchant}`}
        facts={
          <Text fontSize="11.5px" color="text2" fontFamily="mono">
            Listed at {fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
          </Text>
        }
        link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined}
        checked={checked.checkout}
        pending={pending.checkout}
        current
        onCheck={check('checkout')}
        hintText={HINT_TEXT.checkout}
        hintDetail={HINT_DETAIL.checkout}
        hintVisible={hintVisible('checkout')}
        onHideHint={hideHint('checkout')}
      />
    );
  }

  const breakdown = v.upi?.denomination_breakdown || [];
  const singleVoucher = breakdown.length <= 1;
  // The literal instruction, stated as a plain sentence rather than left to
  // be inferred from a row of number pills — this is the exact detail user
  // testing showed people missing ("how many denominations do I even buy?").
  const denominationSentence = `Buy a ${fmt(v.upi?.voucher_amount)} Gift Voucher`;

  return (
    <Box>
      <JourneyChips
        steps={[
          { key: 'voucher', icon: I.ticket, label: 'Voucher', done: checked.voucher },
          { key: 'checkout', icon: I.cart, label: 'Checkout', done: checked.checkout },
        ]}
        activeIndex={viewIndex}
        onSelect={setViewIndex}
      />

      <JourneyPanels activeIndex={viewIndex} onChangeIndex={setViewIndex}>
        {[
        <JourneyRow
          key="voucher"
          tone="voucher"
          icon={I.ticket}
          tourId="voucher-buy"
          label="Buy a Gift Voucher"
          badge={`via ${sourceLabel} · saves ${fmt((v.upi?.voucher_amount ?? 0) - (paid ?? 0))}`}
          current={currentStep === 'voucher'}
          stepNumber={1}
          totalSteps={2}
          nextLabel={`Step 2 — Checkout at ${rec.merchant}`}
          preCheck={sellerLink ? { href: affiliateUrl(sellerLink), merchantName: rec.merchant } : undefined}
          facts={
            <>
              {singleVoucher ? (
                <Text fontSize="17px" color="text" fontWeight={800} fontFamily="mono">
                  {denominationSentence}
                </Text>
              ) : (
                <Box maxW="240px" mx="auto">
                  {breakdown.map((b, i) => (
                    <Flex
                      key={i}
                      justify="space-between"
                      fontFamily="mono"
                      fontSize="14px"
                      fontWeight={700}
                      color="text"
                      py="5px"
                      borderBottom="1px dashed"
                      borderColor="border"
                    >
                      <Text>{b.count} ×</Text>
                      <Text>{fmt(b.denom)} voucher</Text>
                    </Flex>
                  ))}
                  <Flex justify="space-between" fontFamily="mono" fontSize="15px" fontWeight={800} color="amber" pt="6px">
                    <Text>Total</Text>
                    <Text>{fmt(v.upi?.voucher_amount)}</Text>
                  </Flex>
                  <InfoNote
                    short="No need for separate purchases — one cart."
                    full={`Add all ${breakdown.length} vouchers to your ${sourceLabel} cart and check out once — you don't need to buy them one at a time.`}
                    fontSize="10.5px"
                    mt="6px"
                  />
                </Box>
              )}
              <InfoNote
                short={`${v.upi?.pct}% off — you pay ${fmt(paid)}`}
                full={`This is the step that actually saves you money — you pay ${fmt(paid)} for ${fmt(v.upi?.voucher_amount)} of ${rec.merchant} credit.`}
                fontSize="11.5px"
                color="amber"
                fontWeight={700}
                mt="8px"
              />
            </>
          }
          caption={`Opens ${sourceLabel}.`}
          link={v.voucher_url ? { href: v.voucher_url, label: `Buy on ${sourceLabel}` } : undefined}
          checked={checked.voucher}
          pending={pending.voucher}
          onCheck={check('voucher')}
        />,
        <JourneyRow
          key="checkout"
          tone="checkout"
          icon={I.cart}
          tourId="checkout-open"
          label={`Checkout at ${rec.merchant}`}
          facts={
            <>
              <Text fontSize="11.5px" color="text2" fontFamily="mono">
                Listed at {fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
              </Text>
              <Text fontSize="17px" color="text" fontWeight={800} fontFamily="mono" mt="8px">
                {v.upi?.remainder ? `Apply code, pay ${fmt(v.upi.remainder)} remaining` : 'Apply code — covers your order'}
              </Text>
              {v.offline_only && (
                <Flex gap="6px" align="flex-start" mt="8px" bg="amberSoft" border="1px solid" borderColor="amber" borderRadius="xs" px="10px" py="8px">
                  <Flex color="amber" flex="0 0 auto" mt="1px">
                    <I.alert size={13} />
                  </Flex>
                  <Text fontSize="11px" color="text" lineHeight={1.4}>
                    <Text as="span" fontWeight={700}>
                      In-store only
                    </Text>{' '}
                    — accepted at listed {rec.merchant.replace(/\s*\(in-store\)\s*$/i, '')} outlets, not
                    online.{v.how_to_redeem_short ? ` ${v.how_to_redeem_short}` : ''}
                  </Text>
                </Flex>
              )}
            </>
          }
          link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined}
          checked={checked.checkout}
          pending={pending.checkout}
          current={currentStep === 'checkout'}
          stepNumber={2}
          totalSteps={2}
          onCheck={check('checkout')}
          hintText={HINT_TEXT.checkout}
          hintDetail={HINT_DETAIL.checkout}
          hintVisible={hintVisible('checkout')}
          onHideHint={hideHint('checkout')}
        />,
        ]}
      </JourneyPanels>
    </Box>
  );
}
