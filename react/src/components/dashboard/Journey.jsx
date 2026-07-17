import { Flex } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { fmt, affiliateUrl } from '@/utils/format';
import JourneyStep, { JourneyConnector } from './JourneyStep';

/**
 * The recommended-route journey visualization:
 *   merchant (listed price + open store) → [voucher] → checkout.
 * The voucher + checkout nodes only appear when the route carries a voucher.
 */
export default function Journey({ rec }) {
  const v = rec.voucher || null;
  const sellerLink = rec.sellers?.[0]?.link;

  return (
    <Flex
      align="flex-start"
      justify="center"
      flexWrap="wrap"
      gap={{ base: '2px', md: '4px' }}
      mb="4px"
    >
      <JourneyStep
        tone="brand"
        icon={I.store}
        label={rec.merchant}
        detail="Listed at"
        price={fmt(rec.listed_price ? Math.round(rec.listed_price) : null)}
        link={sellerLink ? { href: affiliateUrl(sellerLink), label: 'Open store →' } : undefined}
      />

      {v && (
        <>
          <JourneyConnector />
          <JourneyStep
            tone="voucher"
            icon={I.ticket}
            label="Gyftr voucher"
            detail={`Buy ${v.upi?.purchase_breakdown || fmt(v.upi?.voucher_amount)} via UPI`}
            price={`${v.upi?.pct}% off`}
            link={v.voucher_url ? { href: v.voucher_url, label: 'Buy voucher →' } : undefined}
          />
          <JourneyConnector />
          <JourneyStep
            tone="checkout"
            icon={I.checkCircle}
            label="Checkout"
            detail={
              v.upi?.remainder ? `Pay ${fmt(v.upi.remainder)} remaining` : 'Full order covered'
            }
            price="Done"
          />
        </>
      )}
    </Flex>
  );
}
