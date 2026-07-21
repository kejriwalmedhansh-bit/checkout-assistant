import { useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { fmt, affiliateUrl, paidForVoucher } from '@/utils/format';
import { useUiStore } from '@/store/uiStore';
import JourneyRow, { JourneyConnector } from './JourneyRow';

/**
 * The recommended-route checklist: buy at the merchant → [buy a Gift
 * Voucher] → pay & done. Every row is always fully visible — no dropdown
 * hides anything, since the amounts, the action button, and the hint all
 * matter regardless of which step is next — joined by a connecting line
 * that fills in as steps complete, so the three actions read as one
 * connected path rather than independent buttons. Either step can be done
 * first; only the dismissible hint follows whichever step is next.
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

  const nextStep = (() => {
    if (!checked.store) return 'store';
    if (!v) return null;
    if (!checked.voucher) return 'voucher';
    return 'pay';
  })();

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
    store: v
      ? `Open ${rec.merchant} and put your item in the basket. Don't pay yet — the voucher comes next.`
      : `Open ${rec.merchant} and buy it there — this is already the cheapest way we found.`,
    voucher: `Buy the gift voucher now on our voucher partner's site. You pay ${fmt(paid)} for ${fmt(v?.upi?.voucher_amount)} of ${rec.merchant} credit.`,
    pay: `Once you've bought the voucher, apply its code at ${rec.merchant}'s checkout${
      v?.upi?.remainder ? `, then pay the last ${fmt(v.upi.remainder)} any way you like` : ' — it covers your whole order'
    }.`,
  };

  const hintVisible = (step) => hintsEnabled && !dismissed && nextStep === step;
  const hideHint = () => setDismissed(true);

  const storeRow = (
    <JourneyRow
      tone="brand"
      icon={I.store}
      label={`1. Buy at ${rec.merchant}`}
      facts={
        <Text fontSize="11.5px" color="text2" fontFamily="mono">
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

  // Direct-buy route: one row, no rail, no framing line — mirrors the old
  // single-row behaviour exactly (stays visible, just flips to done).
  if (!v) return storeRow;

  const breakdown = v.upi?.denomination_breakdown || [];
  const singleVoucher = breakdown.length <= 1;

  return (
    <Box>
      <Text fontSize="12px" color="text2" mb="14px">
        Two stops: a discounted Gift Voucher from our voucher partner, then pay with it at{' '}
        {rec.merchant}.
      </Text>

      <Box>
        {storeRow}

        <JourneyConnector done={checked.store} />

        <JourneyRow
          tone="voucher"
          icon={I.ticket}
          label="2. Buy a Gift Voucher"
          facts={
            <>
              {singleVoucher ? (
                <Text fontSize="11.5px" color="text2" fontFamily="mono">
                  {fmt(v.upi?.voucher_amount)} Gift Voucher
                </Text>
              ) : (
                <Flex wrap="wrap" gap="6px">
                  {breakdown.map((b, i) => (
                    <Box
                      key={i}
                      fontFamily="mono"
                      fontSize="11.5px"
                      fontWeight={600}
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
                  ))}
                </Flex>
              )}
              <Text fontSize="11.5px" color="amber" fontWeight={700} mt="8px">
                {v.upi?.pct}% off — you pay {fmt(paid)}
              </Text>
            </>
          }
          caption={`Opens our voucher partner's site — not ${rec.merchant}.`}
          link={v.voucher_url ? { href: v.voucher_url, label: 'Get voucher' } : undefined}
          checked={checked.voucher}
          pending={pending.voucher}
          onCheck={check('voucher')}
          hintText={HINT_TEXT.voucher}
          hintVisible={hintVisible('voucher')}
          onHideHint={hideHint}
        />

        <JourneyConnector done={checked.voucher} />

        <JourneyRow
          tone="checkout"
          icon={I.checkCircle}
          label="3. Pay & done"
          facts={
            <Text fontSize="11.5px" color="text2" fontFamily="mono">
              {v.upi?.remainder ? `Pay ${fmt(v.upi.remainder)} remaining` : 'Full order covered'}
            </Text>
          }
          ready={checked.voucher}
          hintText={HINT_TEXT.pay}
          hintVisible={hintVisible('pay')}
          onHideHint={hideHint}
        />
      </Box>
    </Box>
  );
}
