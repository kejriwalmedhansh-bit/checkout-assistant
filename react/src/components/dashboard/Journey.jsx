import { useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { fmt, affiliateUrl, paidForVoucher } from '@/utils/format';
import { useUiStore } from '@/store/uiStore';
import JourneyRow, { JourneyConnector } from './JourneyRow';

/**
 * The recommended-route checklist: [buy a Gift Voucher] → buy at the
 * merchant → pay & done. The voucher comes first, not last — it's the step
 * that actually matters (where the money is saved) and the one most at risk
 * of being skipped if it's buried behind an easier warm-up step; putting it
 * first means there's no earlier "easy" step for someone to finish and wander
 * off before reaching the one that counts. Every row stays fully visible
 * regardless of progress — no dropdown hides anything — joined by a
 * connecting line that fills in as steps complete, so the three actions read
 * as one connected path rather than independent buttons.
 */
export default function Journey({ rec }) {
  const v = rec.voucher || null;
  const sellerLink = rec.sellers?.[0]?.link;
  const [checked, setChecked] = useState({ store: false, voucher: false });
  const [pending, setPending] = useState({ store: false, voucher: false });
  // "Hide" silences hints for this visit only; the sidebar switch is the
  // durable off. Two different intentions, so two separate controls. Kept
  // per-step (not one shared flag) — hiding the voucher hint shouldn't also
  // silence the store and pay hints, since they're about different actions
  // the user hasn't seen yet.
  const [dismissed, setDismissed] = useState({ store: false, voucher: false, pay: false });
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

  const paid = v ? paidForVoucher(v) : null;
  const HINT_TEXT = {
    voucher: `Buy the voucher now on Gyftr — this is the step that actually saves you money. You pay ${fmt(paid)} for ${fmt(v?.upi?.voucher_amount)} of ${rec.merchant} credit.`,
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
        hintVisible={hintVisible('store')}
        onHideHint={hideHint('store')}
      />
    );
  }

  const breakdown = v.upi?.denomination_breakdown || [];
  const singleVoucher = breakdown.length <= 1;

  return (
    <Box>
      <Text fontSize="12px" color="text2" mb="14px">
        Two stops: buy a discounted Gyftr voucher first, then use it to pay at {rec.merchant}.
      </Text>

      <Box>
        <JourneyRow
          tone="voucher"
          icon={I.ticket}
          label="1. Buy a Gift Voucher"
          badge={`This is where you save ${fmt((v.upi?.voucher_amount ?? 0) - (paid ?? 0))}`}
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
                  <Text fontSize="10.5px" color="text3" mt="4px">
                    Gyftr sells fixed sizes — these add up to your total
                    {v.upi?.txns_needed > 1 ? `, in ${v.upi.txns_needed} separate purchases` : ''}.
                  </Text>
                </>
              )}
              <Text fontSize="11.5px" color="amber" fontWeight={700} mt="8px">
                {v.upi?.pct}% off — you pay {fmt(paid)}
              </Text>
            </>
          }
          caption="Opens Gyftr in a new tab."
          link={v.voucher_url ? { href: v.voucher_url, label: 'Buy on Gyftr' } : undefined}
          checked={checked.voucher}
          pending={pending.voucher}
          onCheck={check('voucher')}
          hintText={HINT_TEXT.voucher}
          hintVisible={hintVisible('voucher')}
          onHideHint={hideHint('voucher')}
        />

        <JourneyConnector done={checked.voucher} />

        <JourneyRow
          tone="brand"
          icon={I.store}
          label={`2. Buy at ${rec.merchant}`}
          facts={
            <Text fontSize="11.5px" color="text2" fontFamily="mono">
              Listed at {fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
            </Text>
          }
          link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined}
          checked={checked.store}
          pending={pending.store}
          current={currentStep === 'store'}
          onCheck={check('store')}
          hintText={HINT_TEXT.store}
          hintVisible={hintVisible('store')}
          onHideHint={hideHint('store')}
        />

        <JourneyConnector done={checked.store} />

        <JourneyRow
          tone="checkout"
          icon={I.checkCircle}
          label="3. Pay & done"
          facts={
            <Text fontSize="11.5px" color="text2" fontFamily="mono">
              {v.upi?.remainder ? `Pay ${fmt(v.upi.remainder)} remaining` : 'Full order covered'}
            </Text>
          }
          ready={checked.store}
          current={currentStep === 'pay'}
          hintText={HINT_TEXT.pay}
          hintVisible={hintVisible('pay')}
          onHideHint={hideHint('pay')}
        />
      </Box>
    </Box>
  );
}
