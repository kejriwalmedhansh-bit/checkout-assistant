import { Box, Flex, Link, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { fmt } from '@/utils/format';

/**
 * A generic illustrated card graphic (not a scan of any real bank's card —
 * avoids reproducing bank/network trademarks) so the nudge has a visual
 * anchor instead of just a generic icon. The bank name is shown as text
 * alongside it, not baked into the graphic.
 */
function CardVisual() {
  return (
    <Box
      w="58px"
      h="38px"
      flex="0 0 auto"
      borderRadius="7px"
      bgGradient="linear(to-br, brand, brandHover)"
      position="relative"
      overflow="hidden"
      boxShadow="0 3px 8px -2px rgba(10,107,65,.45)"
    >
      <Box position="absolute" top="8px" left="7px" w="12px" h="9px" borderRadius="2px" bg="brassSoft" opacity={0.9} />
      <Flex position="absolute" bottom="7px" left="7px" gap="2.5px">
        {[0, 1, 2].map((i) => (
          <Box key={i} w="3px" h="3px" borderRadius="50%" bg="whiteAlpha.700" />
        ))}
      </Flex>
    </Box>
  );
}

/**
 * Optional card-savings nudge, shown on whichever route is currently active
 * (recommended, or a picked alternative) and only when the backend supplies
 * `card_fomo` (it gates the display threshold — we never re-derive it).
 * Card savings never affect ranking.
 */
export default function CardFomo({ cardFomo }) {
  if (!cardFomo?.card_name) return null;

  return (
    <Card p="16px 18px" bg="surface2">
      <Text fontSize="11px" color="text3" fontWeight={500} letterSpacing=".06em" textTransform="uppercase" mb="10px">
        Save more with a card
      </Text>
      <Flex align="center" gap="14px">
        <CardVisual />
        <Box flex="1" minW={0}>
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
        {cardFomo.apply_url && (
          <Link
            href={cardFomo.apply_url}
            isExternal
            flex="0 0 auto"
            fontSize="12px"
            fontWeight={600}
            color="brandText"
            bg="brandSoft"
            border="1px solid"
            borderColor="brand"
            borderRadius="6px"
            px="10px"
            py="6px"
            _hover={{ textDecoration: 'none', bg: 'brandSoft2' }}
          >
            Apply →
          </Link>
        )}
      </Flex>
    </Card>
  );
}
