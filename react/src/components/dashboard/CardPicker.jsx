import { useState } from 'react';
import { Box, Button, Flex, Grid, Text } from '@chakra-ui/react';

import BrandAvatar from '@/components/common/BrandAvatar';
import { I } from '@/components/common/icons';
import { CARD_CHOICES } from '@/utils/myCards';
import { shopLogos } from '@/utils/priceList';

function BankTile({ choice, on, onToggle }) {
  const [failed, setFailed] = useState(false);
  return (
    <Flex
      as="button"
      type="button"
      aria-pressed={on}
      onClick={onToggle}
      direction="column"
      align="center"
      gap="6px"
      py="10px"
      px="4px"
      borderRadius="12px"
      border={on ? '1.5px solid' : '1px solid'}
      borderColor={on ? 'brand' : 'border'}
      bg={on ? 'brandSoft' : 'surface'}
      position="relative"
      _focusVisible={{ boxShadow: 'ring', outline: 'none' }}
    >
      {on && (
        <Flex position="absolute" top="5px" right="5px" w="16px" h="16px" borderRadius="full" bg="brand" color="white" align="center" justify="center">
          <I.check size={11} />
        </Flex>
      )}
      <Flex w="36px" h="36px" borderRadius="full" bg="white" border="1px solid" borderColor="border" overflow="hidden" align="center" justify="center">
        {failed ? (
          <BrandAvatar name={choice.label} size={36} radius="999px" />
        ) : (
          <Box as="img" src={shopLogos(`https://${choice.site}`)[0]} alt="" w="100%" h="100%" objectFit="cover" onError={() => setFailed(true)} />
        )}
      </Flex>
      <Text fontSize="12px" fontWeight={600} color="text" lineHeight="1.2" textAlign="center">
        {choice.label}
      </Text>
    </Flex>
  );
}

/**
 * "Which bank's credit card do you have?", asked once above the price list
 * when a shop has a card offer worth having (see worthAsking). Same grid of
 * bank logos as the UPI apps' "Select your bank". The answer stays on this
 * device; "None" is an answer too, so it is not asked again.
 */
export default function CardPicker({ initial = [], topSaving, onDone }) {
  const [picked, setPicked] = useState(initial);
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  return (
    <Box bg="surface" border="1px solid" borderColor="border" borderRadius="16px" px="14px" py="14px">
      <Text fontSize="16px" fontWeight={700} color="text">
        Which bank&apos;s credit card do you have?
      </Text>
      <Text fontSize="13px" color="text2" mt="2px">
        {topSaving ? `Card offers here take up to ${topSaving} off. ` : ''}We&apos;ll add yours to the prices.
      </Text>
      <Grid templateColumns="repeat(4, minmax(0, 1fr))" gap="8px" mt="12px">
        {CARD_CHOICES.map((c) => (
          <BankTile key={c.id} choice={c} on={picked.includes(c.id)} onToggle={() => toggle(c.id)} />
        ))}
      </Grid>
      <Flex gap="8px" mt="12px">
        <Button flex="1" variant="outline" h="44px" borderRadius="12px" fontWeight={600} onClick={() => onDone([])}>
          None
        </Button>
        <Button
          flex="2"
          h="44px"
          borderRadius="12px"
          bg="brand"
          color="white"
          fontWeight={700}
          isDisabled={!picked.length}
          _hover={{ opacity: 0.92 }}
          onClick={() => onDone(picked)}
        >
          Show my prices
        </Button>
      </Flex>
      <Text fontSize="11.5px" color="text3" mt="8px" textAlign="center">
        Saved on this phone only. No login.
      </Text>
    </Box>
  );
}
