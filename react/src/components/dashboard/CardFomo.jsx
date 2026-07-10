import { Box, Flex, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { fmt } from '@/utils/format';

/**
 * Optional card-savings nudge, shown ONLY on the recommended route and ONLY when
 * the backend supplies `card_fomo` (it gates the display threshold — we never
 * re-derive it). Card savings never affect ranking.
 */
export default function CardFomo({ cardFomo }) {
  if (!cardFomo?.card_name) return null;

  return (
    <Card p="16px 18px" bg="surface2">
      <Text fontSize="11px" color="text3" fontWeight={500} letterSpacing=".06em" textTransform="uppercase" mb="10px">
        Save more with a card
      </Text>
      <Flex align="center" gap="14px">
        <Flex
          w="40px"
          h="40px"
          borderRadius="10px"
          bg="greenSoft"
          color="green"
          align="center"
          justify="center"
          flex="0 0 auto"
        >
          <I.zap size={20} />
        </Flex>
        <Box>
          <Text fontSize="15px" fontWeight={700} color="green">
            Save {fmt(cardFomo.actual_saving)} more
          </Text>
          <Text fontSize="13px" color="text2">
            {cardFomo.card_name}
          </Text>
          <Text fontSize="12px" color="text3">
            Final price: {fmt(cardFomo.final_cost_with_card)}
          </Text>
        </Box>
      </Flex>
    </Card>
  );
}
