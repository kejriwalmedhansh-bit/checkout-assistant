import { useState } from 'react';
import { Box, Button, Flex, Text } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import { I } from '@/components/common/icons';
import { cardOptionsApi } from '@/api/cardOptions.api';
import { fmt } from '@/utils/format';

/**
 * Replaces the old auto-picked "best card" nudge (CardFomo). Nothing shows
 * until the shopper opts in: "Have a credit card?" -> pick their own card
 * from a dropdown -> see that card's real voucher discount + cashback for
 * this order. Never a comparison against UPI, never an auto-picked "best"
 * card — the shopper's choice, the shopper's numbers.
 */
export default function CreditCardPrompt({ route }) {
  const [stage, setStage] = useState('prompt'); // prompt | declined | picking | selected
  const [options, setOptions] = useState(null); // null = not fetched yet
  const [loadError, setLoadError] = useState(false);
  const [selectedCard, setSelectedCard] = useState('');

  const openPicker = async () => {
    setStage('picking');
    if (options !== null) return; // already fetched
    setLoadError(false);
    try {
      const data = await cardOptionsApi.forRoute(route);
      setOptions(data.options || []);
    } catch {
      setLoadError(true);
    }
  };

  const decline = () => setStage('declined');

  const pickCard = (cardName) => {
    setSelectedCard(cardName);
    setStage('selected');
  };

  const changeCard = () => {
    setSelectedCard('');
    setStage('picking');
  };

  const quote = options?.find((o) => o.card_name === selectedCard) || null;

  return (
    <Card p="16px 18px" bg="surface2">
      <Text fontSize="11px" color="text3" fontWeight={500} letterSpacing=".06em" textTransform="uppercase" mb="10px">
        Paying by card?
      </Text>

      {stage === 'prompt' && (
        <Flex align="center" justify="space-between" gap="12px">
          <Flex align="center" gap="8px">
            <Box color="text2">
              <I.pay size={18} />
            </Box>
            <Text fontSize="15px" fontWeight={600} color="text">
              Have a credit card?
            </Text>
          </Flex>
          <Flex gap="8px" flex="0 0 auto">
            <Button size="sm" variant="outline" onClick={decline}>
              No
            </Button>
            <Button size="sm" bg="brand" color="onBrand" _hover={{ bg: 'brandHover' }} onClick={openPicker}>
              Yes
            </Button>
          </Flex>
        </Flex>
      )}

      {stage === 'declined' && (
        <Flex align="center" justify="space-between" gap="10px">
          <Flex align="center" gap="8px" color="text2">
            <I.checkCircle size={14} />
            <Text fontSize="13px">Sticking with UPI</Text>
          </Flex>
          <Box as="button" type="button" onClick={openPicker} fontSize="13px" fontWeight={600} color="brand">
            Have a card?
          </Box>
        </Flex>
      )}

      {stage === 'picking' && (
        <Box>
          {options === null && !loadError && (
            <Text fontSize="13px" color="text2">
              Checking your card options…
            </Text>
          )}
          {loadError && (
            <Flex align="center" justify="space-between" gap="10px">
              <Text fontSize="13px" color="text2">
                Couldn&apos;t load card options.
              </Text>
              <Box as="button" type="button" onClick={openPicker} fontSize="13px" fontWeight={600} color="brand">
                Retry
              </Box>
            </Flex>
          )}
          {options !== null && !loadError && options.length === 0 && (
            <Flex align="center" justify="space-between" gap="10px">
              <Text fontSize="13px" color="text2">
                No card offers apply to this order.
              </Text>
              <Box as="button" type="button" onClick={() => setStage('prompt')} fontSize="13px" fontWeight={600} color="brand">
                Back
              </Box>
            </Flex>
          )}
          {options !== null && !loadError && options.length > 0 && (
            <Flex direction="column" gap="10px">
              <Flex align="center" gap="8px">
                <Box color="text2">
                  <I.pay size={16} />
                </Box>
                <Text fontSize="14px" fontWeight={600} color="text">
                  Choose your card
                </Text>
              </Flex>
              <Box position="relative">
                <Box
                  as="select"
                  value=""
                  onChange={(e) => pickCard(e.target.value)}
                  w="100%"
                  appearance="none"
                  fontSize="14px"
                  fontWeight={600}
                  color="text"
                  bg="surface"
                  border="1.5px solid"
                  borderColor="border"
                  borderRadius="10px"
                  p="12px 36px 12px 14px"
                  cursor="pointer"
                  _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
                >
                  <option value="" disabled>
                    Select your card
                  </option>
                  {options.map((o) => (
                    <option key={o.card_name} value={o.card_name}>
                      {o.card_name}
                    </option>
                  ))}
                </Box>
                <Box position="absolute" right="12px" top="50%" transform="translateY(-50%)" color="text3" pointerEvents="none">
                  <I.chevDown size={14} />
                </Box>
              </Box>
              <Box as="button" type="button" onClick={() => setStage('prompt')} fontSize="13px" fontWeight={600} color="brand" alignSelf="flex-start">
                Cancel
              </Box>
            </Flex>
          )}
        </Box>
      )}

      {stage === 'selected' && quote && (
        <Flex direction="column" gap="12px">
          <Flex align="center" justify="space-between">
            <Flex align="center" gap="8px" color="text2">
              <I.pay size={14} />
              <Text fontSize="13px" fontWeight={700}>
                {quote.card_name}
              </Text>
            </Flex>
            <Box as="button" type="button" onClick={changeCard} fontSize="13px" fontWeight={600} color="brand">
              Change
            </Box>
          </Flex>
          <Flex gap="10px">
            {quote.voucher_discount != null && (
              <Card flex="1" p="14px" bg="surface" gap="8px" display="flex" flexDirection="column">
                <Box w="26px" h="26px" borderRadius="8px" bg="brandSoft" color="brand" display="flex" alignItems="center" justifyContent="center">
                  <I.ticket size={14} />
                </Box>
                <Text fontSize="18px" fontWeight={800} color="text">
                  {fmt(quote.voucher_discount)}
                </Text>
                <Text fontSize="11px" color="text2" lineHeight="1.3">
                  Voucher discount on this order
                </Text>
              </Card>
            )}
            <Card flex="1" p="14px" bg="surface" gap="8px" display="flex" flexDirection="column">
              <Box w="26px" h="26px" borderRadius="8px" bg="greenSoft" color="green" display="flex" alignItems="center" justifyContent="center">
                <I.check size={14} />
              </Box>
              <Text fontSize="18px" fontWeight={800} color="text">
                {fmt(quote.cashback)}
              </Text>
              <Text fontSize="11px" color="text2" lineHeight="1.3">
                Cashback on this order
              </Text>
            </Card>
          </Flex>
          {quote.apply_url && (
            <Box
              as="a"
              href={quote.apply_url}
              target="_blank"
              rel="noreferrer"
              alignSelf="flex-start"
              fontSize="12px"
              fontWeight={600}
              color="brandText"
              bg="brandSoft"
              border="1px solid"
              borderColor="brand"
              borderRadius="6px"
              px="10px"
              py="6px"
            >
              Apply →
            </Box>
          )}
        </Flex>
      )}
    </Card>
  );
}
