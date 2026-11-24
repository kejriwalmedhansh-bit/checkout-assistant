import { useState } from 'react';
import { Button, Flex, Text } from '@chakra-ui/react';

import { hubbleApi } from '@/api/hubble.api';
import { idToken } from '@/lib/firebase';
import { track } from '@/utils/analytics';

// Same values as HEARD_FROM_CHOICES in src/services/buyer_service.py.
const CHOICES = [
  ['google', 'Google'],
  ['chatgpt', 'ChatGPT'],
  ['instagram', 'Instagram'],
  ['friend', 'A friend'],
  ['other', 'Other'],
];

/**
 * "How did you hear about Dealo?" on the voucher-ready screen: one tap, asked
 * once per buyer (the server says when, see ask_heard_from on /hubble/session).
 * The link a visitor arrived by is already recorded; this catches what no
 * link can, a friend's recommendation, and checks the rest. Asked only after
 * the voucher is theirs, so it never stands between a shopper and a purchase.
 */
export default function HeardFrom({ ev }) {
  const [answered, setAnswered] = useState(false);

  const answer = async (choice) => {
    setAnswered(true);
    track('Heard From Answered', { ...ev, choice });
    try {
      await hubbleApi.heardFrom(await idToken(), choice);
    } catch {
      // The Mixpanel event above still has the answer.
    }
  };

  if (answered) {
    return (
      <Text fontSize="13px" color="text2" textAlign="center">
        Thanks, that helps.
      </Text>
    );
  }
  return (
    <Flex direction="column" align="center" gap="8px">
      <Text fontSize="13px" fontWeight={700}>
        How did you hear about Dealo?
      </Text>
      <Flex wrap="wrap" justify="center" gap="6px">
        {CHOICES.map(([value, label]) => (
          <Button key={value} size="sm" minH="36px" variant="outline" borderRadius="pill" fontWeight={600} onClick={() => answer(value)}>
            {label}
          </Button>
        ))}
      </Flex>
    </Flex>
  );
}
