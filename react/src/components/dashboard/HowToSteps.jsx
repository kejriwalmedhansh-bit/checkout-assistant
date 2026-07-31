import { Flex } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import InfoNote from '@/components/common/InfoNote';

/**
 * A voucher route was already checked against Gyftr's stacking, denomination
 * and category-redemption rules before it was ever recommended (see
 * voucher_lookup.py / category_classifier.py) — so this isn't a second copy
 * of Journey's own steps, and it isn't a dump of every restriction either
 * (Gyftr shows those in full right before payment). Just a nudge to actually
 * read them there. Kept as a plain, unboxed line (not a full banner) — the
 * card was measurably too tall on a phone with every step given its own
 * bordered box; this one is real but secondary, so it doesn't need the same
 * visual weight as the voucher/cart/pay steps above it. Renders nothing when
 * the route has no voucher.
 */
export default function HowToSteps({ rec }) {
  const v = rec.voucher || null;
  if (!v) return null;

  return (
    <Flex gap="6px" align="baseline">
      <Flex color="amber" flex="0 0 auto" mt="1px">
        <I.alert size={12} />
      </Flex>
      <InfoNote
        short="Verified for your order — worth a quick skim of Gyftr's terms."
        full="We've already checked this voucher works for your order. It's still worth a quick skim of Gyftr's own terms before you pay — takes a few seconds."
        fontSize="11px"
        color="text3"
        mt="0"
      />
    </Flex>
  );
}
