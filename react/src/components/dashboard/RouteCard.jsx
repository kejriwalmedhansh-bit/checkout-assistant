import { Button, Flex, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import Journey from './Journey';
import HowToSteps from './HowToSteps';
import FinalPriceRow from './FinalPriceRow';
import { finalPrice as calcFinal, originalPrice as calcOriginal, saving as calcSaving } from '@/utils/format';

/**
 * The primary route card: heading → journey → how-to steps → final price row.
 * The heading is a real title, not the small uppercase Eyebrow label used
 * elsewhere — this line anchors the whole step flow below it, so it needs
 * the visual weight to actually draw the eye down into the steps.
 * Shows the recommended route by default, or a picked alternative (promoted
 * here in full, same detail level) when isAlt is true — onBack returns to
 * the recommended route.
 */
export default function RouteCard({ result, rec, isAlt = false, onBack }) {
  const finalPrice = calcFinal(rec);
  const originalPrice = calcOriginal(result, rec);
  const saving = calcSaving(result, rec);

  return (
    <Card p={{ base: '18px', md: '22px' }}>
      <Flex align="center" justify="space-between" mb="18px">
        <Text fontSize="20px" fontWeight={800} color="text" letterSpacing="-.01em">
          {isAlt ? `Selected: ${rec.merchant}` : 'Best way to buy this'}
        </Text>
        {isAlt && (
          <Button
            variant="ghost"
            size="xs"
            onClick={onBack}
            color="text2"
            fontWeight={500}
          >
            ← Back to recommended
          </Button>
        )}
      </Flex>
      <Flex direction="column" gap="18px">
        <Journey rec={rec} />
        <HowToSteps rec={rec} />
        <FinalPriceRow finalPrice={finalPrice} originalPrice={originalPrice} saving={saving} />
      </Flex>
    </Card>
  );
}
