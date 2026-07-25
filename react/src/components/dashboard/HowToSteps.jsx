import { Text } from '@chakra-ui/react';

/**
 * A voucher route was already checked against Gyftr's stacking, denomination
 * and category-redemption rules before it was ever recommended (see
 * voucher_lookup.py / category_classifier.py) — so this isn't a second copy
 * of Journey's own steps, and it isn't a dump of every restriction either
 * (Gyftr shows those in full right before payment). Just a nudge to actually
 * read them there. Renders nothing when the route has no voucher.
 */
export default function HowToSteps({ rec }) {
  const v = rec.voucher || null;
  if (!v) return null;

  return (
    <Text fontSize="12.5px" color="text3" lineHeight={1.5}>
      We've already checked this voucher works for your order. Worth a quick skim of Gyftr's own
      terms before you pay — takes a few seconds.
    </Text>
  );
}
