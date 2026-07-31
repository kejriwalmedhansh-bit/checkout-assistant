import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import InfoNote from '@/components/common/InfoNote';
import { fmt, affiliateUrl, paidForVoucher } from '@/utils/format';
import { useUiStore } from '@/store/uiStore';
import { track } from '@/utils/analytics';
import JourneyRow from './JourneyRow';
import JourneyChips from './JourneyChips';
import JourneyPanels from './JourneyPanels';

/**
 * The recommended-route checklist: [buy a Gift Voucher] → buy at the
 * merchant → pay & done. The voucher comes first, not last — it's the step
 * that actually matters (where the money is saved) and the one most at risk
 * of being skipped if it's buried behind an easier warm-up step; putting it
 * first means there's no earlier "easy" step for someone to finish and wander
 * off before reaching the one that counts.
 *
 * Layout: a numbered, arrow-linked JourneyChips strip stays visible above a
 * single JourneyPanels viewport showing one step's full detail at a time —
 * a long vertical stack of all three fully-expanded steps measurably cost
 * scroll-driven drop-off, so only the step being viewed renders at full
 * size; nothing about the sequence itself is hidden, since the chip strip
 * alone already shows all three steps, their order, and which are done.
 * Completing a step (currentStep changing) carries the view forward on its
 * own; tapping a chip or dragging the panel lets you browse freely without
 * losing progress.
 */
export default function Journey({ rec }) {
  const v = rec.voucher || null;
  const sourceLabel = v?.voucher_source === 'maximize' ? 'Maximize' : 'Gyftr';
  const sellerLink = rec.sellers?.[0]?.link;
  const [checked, setChecked] = useState({ store: false, voucher: false });
  const [pending, setPending] = useState({ store: false, voucher: false });
  // "Hide" silences a hint for this visit only; the sidebar switch is the
  // durable off. Two different intentions, so two separate controls. Kept
  // per-step (not one shared flag) — hiding the store hint shouldn't also
  // silence the pay hint, since they're about different actions the user
  // hasn't seen yet. The voucher step has no dismissible hint of its own —
  // its "why this helps" explanation lives behind the discount line's own
  // InfoNote instead (see HINT_DETAIL below), since it's tied to a specific
  // number rather than a general nudge.
  const [dismissed, setDismissed] = useState({ store: false, pay: false });
  const hintsEnabled = useUiStore((s) => s.hintsEnabled);

  // A brief "pending" beat before the checkmark lands — an instant flip is
  // easy to miss; this makes the confirmation a moment you actually notice.
  const check = (key) => () => {
    track('Clicked Buy Link', { step: key, merchant: rec.merchant, has_voucher: Boolean(v) });
    setPending((p) => ({ ...p, [key]: true }));
    setTimeout(() => {
      setPending((p) => ({ ...p, [key]: false }));
      setChecked((c) => ({ ...c, [key]: true }));
    }, 550);
  };

  const paid = v ? paidForVoucher(v) : null;
  // Short line shown by default; DETAIL is the original full sentence, one
  // tap away behind the row's own InfoNote toggle — same content as before,
  // just not all of it on screen at once.
  const HINT_TEXT = {
    store: v ? 'Pay with the voucher code next.' : 'This is the cheapest price we found.',
    pay: v?.upi?.remainder ? `Enter the code, then pay ${fmt(v.upi.remainder)} the usual way.` : 'Enter the code at checkout.',
  };
  const HINT_DETAIL = {
    store: v
      ? `You've got the voucher — now open ${rec.merchant} and add your item to the basket. You'll pay with the code next.`
      : `Open ${rec.merchant} and buy it there — this is already the cheapest way we found.`,
    pay: `Apply your voucher code at ${rec.merchant}'s checkout${
      v?.upi?.remainder ? `, then pay the last ${fmt(v.upi.remainder)} any way you like` : ' — it covers your whole order'
    }.`,
  };

  // All three hints show at once, each under its own step — not just
  // whichever step is next. Matches the row itself: nothing about a step is
  // hidden just because you haven't reached it yet.
  const hintVisible = (step) => hintsEnabled && !dismissed[step];
  const hideHint = (step) => () => setDismissed((d) => ({ ...d, [step]: true }));

  // Which step is next — moves forward as steps are checked off, so the
  // glow travels through the flow instead of sitting on one fixed step.
  const currentStep = checked.store ? 'pay' : checked.voucher ? 'store' : 'voucher';
  const STEP_INDEX = { voucher: 0, store: 1, pay: 2 };

  // Which step's full detail is on screen right now (see JourneyPanels).
  // Tapping a chip or swiping sets this directly for browsing; completing a
  // step (currentStep changing) carries the view forward automatically, so
  // finishing an action moves you on without a separate "next" tap.
  const [viewIndex, setViewIndex] = useState(0);
  useEffect(() => {
    setViewIndex(STEP_INDEX[currentStep]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep]);

  // Direct-buy route (no voucher available): one row, no rail, no framing
  // line, no numbering — mirrors the old single-row behaviour exactly.
  if (!v) {
    return (
      <JourneyRow
        tone="brand"
        icon={I.store}
        label={`Buy at ${rec.merchant}`}
        facts={
          <Text fontSize="11.5px" color="text2" fontFamily="mono">
            Listed at {fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
          </Text>
        }
        link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined}
        checked={checked.store}
        pending={pending.store}
        current
        onCheck={check('store')}
        hintText={HINT_TEXT.store}
        hintDetail={HINT_DETAIL.store}
        hintVisible={hintVisible('store')}
        onHideHint={hideHint('store')}
      />
    );
  }

  const breakdown = v.upi?.denomination_breakdown || [];
  const singleVoucher = breakdown.length <= 1;

  return (
    <Box>
      <Text fontSize="11px" color="text2" mb="9px">
        Two stops: buy a discounted {sourceLabel} voucher first, then use it to pay at {rec.merchant}.
      </Text>

      <JourneyChips
        steps={[
          { key: 'voucher', icon: I.ticket, label: 'Voucher', done: checked.voucher },
          { key: 'store', icon: I.cart, label: 'Cart', done: checked.store },
          { key: 'pay', icon: I.pay, label: 'Pay', done: false },
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
          label="Buy a Gift Voucher"
          badge={`via ${sourceLabel} · saves ${fmt((v.upi?.voucher_amount ?? 0) - (paid ?? 0))}`}
          emphasized
          current={currentStep === 'voucher'}
          facts={
            <>
              {singleVoucher ? (
                <Text fontSize="11.5px" color="text2" fontFamily="mono">
                  {fmt(v.upi?.voucher_amount)} Gift Voucher
                </Text>
              ) : (
                <>
                  <Flex wrap="wrap" align="center" gap="6px">
                    {breakdown.map((b, i) => (
                      <Flex key={i} align="center" gap="6px">
                        <Box
                          fontFamily="mono"
                          fontSize="12.5px"
                          fontWeight={700}
                          bg="surface3"
                          border="1px solid"
                          borderColor="border"
                          color="text"
                          px="9px"
                          py="4px"
                          borderRadius="pill"
                          whiteSpace="nowrap"
                        >
                          {b.count} × {fmt(b.denom)}
                        </Box>
                        {i < breakdown.length - 1 && (
                          <Text color="text3" fontSize="12px" fontWeight={700}>
                            +
                          </Text>
                        )}
                      </Flex>
                    ))}
                    <Text color="text3" fontSize="12px" fontWeight={700}>
                      =
                    </Text>
                    <Box
                      fontFamily="mono"
                      fontSize="12.5px"
                      fontWeight={700}
                      bg="amberSoft"
                      border="1px solid"
                      borderColor="amber"
                      color="amber"
                      px="9px"
                      py="4px"
                      borderRadius="pill"
                      whiteSpace="nowrap"
                    >
                      {fmt(v.upi?.voucher_amount)}
                    </Box>
                  </Flex>
                  <InfoNote
                    short={
                      v.upi?.txns_needed > 1
                        ? `${v.upi.txns_needed} separate purchases, totaling ${fmt(v.upi?.voucher_amount)}.`
                        : `Add up to your total of ${fmt(v.upi?.voucher_amount)}.`
                    }
                    full={`${sourceLabel} sells fixed sizes — these add up to your total${
                      v.upi?.txns_needed > 1 ? `, in ${v.upi.txns_needed} separate purchases` : ''
                    }.`}
                    fontSize="10.5px"
                    mt="4px"
                  />
                </>
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
          key="store"
          tone="brand"
          icon={I.store}
          label={`Buy at ${rec.merchant}`}
          facts={
            <>
              <Text fontSize="11.5px" color="text2" fontFamily="mono">
                Listed at {fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
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
          checked={checked.store}
          pending={pending.store}
          current={currentStep === 'store'}
          onCheck={check('store')}
          hintText={HINT_TEXT.store}
          hintDetail={HINT_DETAIL.store}
          hintVisible={hintVisible('store')}
          onHideHint={hideHint('store')}
        />,
        <JourneyRow
          key="pay"
          tone="checkout"
          icon={I.pay}
          label="Pay & done"
          facts={
            <Text fontSize="11.5px" color="text2" fontFamily="mono">
              {v.upi?.remainder ? `Pay ${fmt(v.upi.remainder)} remaining` : 'Full order covered'}
            </Text>
          }
          ready={checked.store}
          current={currentStep === 'pay'}
          hintText={HINT_TEXT.pay}
          hintDetail={HINT_DETAIL.pay}
          hintVisible={hintVisible('pay')}
          onHideHint={hideHint('pay')}
        />,
        ]}
      </JourneyPanels>
    </Box>
  );
}
