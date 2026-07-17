import { useState } from 'react';
import { Flex } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { fmt, affiliateUrl } from '@/utils/format';
import JourneyStep, { JourneyConnector } from './JourneyStep';

/**
 * The recommended-route checklist, vertical:
 *   buy at the merchant → [buy a Gift Voucher] → pay & done.
 * Each action button opens the real link in a new tab and checks itself off
 * — a to-do list, not a locked sequence (either can be done first). The
 * final "pay" row has no button; it just reflects ready once the voucher
 * step is checked. The voucher + checkout rows only appear when the route
 * carries a voucher.
 */
export default function Journey({ rec }) {
  const v = rec.voucher || null;
  const sellerLink = rec.sellers?.[0]?.link;
  const [checked, setChecked] = useState({ store: false, voucher: false });

  const check = (key) => () => setChecked((c) => ({ ...c, [key]: true }));

  return (
    <Flex direction="column" mb="4px">
      <JourneyStep
        tone="brand"
        icon={I.store}
        label={`1. Buy at ${rec.merchant}`}
        detail={`Listed at ${fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}`}
        link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store' } : undefined}
        checked={checked.store}
        onCheck={check('store')}
      />

      {v && (
        <>
          <JourneyConnector />
          <JourneyStep
            tone="voucher"
            icon={I.ticket}
            label="2. Buy a Gift Voucher"
            detail={`${v.upi?.purchase_breakdown || fmt(v.upi?.voucher_amount)} — ${v.upi?.pct}% off`}
            link={v.voucher_url ? { href: v.voucher_url, label: 'Get voucher' } : undefined}
            checked={checked.voucher}
            onCheck={check('voucher')}
          />
          <JourneyConnector />
          <JourneyStep
            tone="checkout"
            icon={I.checkCircle}
            label="3. Pay & done"
            detail={
              v.upi?.remainder ? `Pay ${fmt(v.upi.remainder)} remaining` : 'Full order covered'
            }
            ready={checked.voucher}
          />
        </>
      )}
    </Flex>
  );
}
