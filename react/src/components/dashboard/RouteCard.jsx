import { Flex } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import Eyebrow from '@/components/common/Eyebrow';
import Journey from './Journey';
import HowToSteps from './HowToSteps';
import FinalPriceRow from './FinalPriceRow';
import { finalPrice as calcFinal, originalPrice as calcOriginal, saving as calcSaving } from '@/utils/format';

/**
 * The Recommended Route card: eyebrow → journey → how-to steps → final price row.
 * There is only ever ONE recommended route (lowest final cost, card-free).
 */
export default function RouteCard({ result, rec }) {
  const finalPrice = calcFinal(rec);
  const originalPrice = calcOriginal(result, rec);
  const saving = calcSaving(result, rec);

  return (
    <Card p={{ base: '18px', md: '22px' }}>
      <Eyebrow color="orangeText" mb="18px" display="block">
        ★ Recommended route
      </Eyebrow>
      <Flex direction="column" gap="18px">
        <Journey rec={rec} />
        <HowToSteps rec={rec} />
        <FinalPriceRow finalPrice={finalPrice} originalPrice={originalPrice} saving={saving} />
      </Flex>
    </Card>
  );
}
