import { Button, Flex, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import Journey from './Journey';
import HowToSteps from './HowToSteps';
import FinalPriceRow from './FinalPriceRow';
import { finalPrice as calcFinal, originalPrice as calcOriginal, saving as calcSaving } from '@/utils/format';

/**
 * The primary route card: [heading →] journey → how-to steps → final price
 * row. The heading only renders when viewing a picked alternative (its
 * "Selected: {merchant}" + back control are load-bearing there) — the
 * default recommended-route view skips it entirely. It used to always show
 * a generic "Best way to buy this" label, but each step card now states its
 * own "STEP X OF 3 / action" directly, making the outer label redundant
 * weight above the fold (removed after live mobile testing showed the CTA
 * needed to fit on screen without scrolling).
 */
export default function RouteCard({ result, rec, isAlt = false, onBack, payingByCard = false }) {
  const finalPrice = calcFinal(rec, payingByCard);
  const originalPrice = calcOriginal(result, rec);
  const saving = calcSaving(result, rec, payingByCard);

  return (
    <Card p={{ base: '14px', md: '18px' }}>
      {isAlt && (
        <Flex align="center" justify="space-between" mb="12px">
          <Text fontSize="18px" fontWeight={800} color="text" letterSpacing="-.01em">
            Selected: {rec.merchant}
          </Text>
          <Button
            variant="ghost"
            size="xs"
            onClick={onBack}
            color="text2"
            fontWeight={500}
          >
            ← Back to recommended
          </Button>
        </Flex>
      )}
      <Flex direction="column" gap="12px">
        <Journey rec={rec} payingByCard={payingByCard} />
        <HowToSteps rec={rec} />
        <FinalPriceRow finalPrice={finalPrice} originalPrice={originalPrice} saving={saving} />
      </Flex>
    </Card>
  );
}
