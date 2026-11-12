import { useEffect, useState } from 'react';
import { Button, Text } from '@chakra-ui/react';

const WAIT = 30;
const MAX_SENDS = 3;

/**
 * Under the SMS code box: "Resend code in 0:30", then a Resend link — what
 * every phone login (Swiggy, Flipkart, Amazon, Gyftr) has, so a late or lost
 * SMS never leaves the shopper stuck. Three sends in all, then it asks them
 * to check the number instead.
 */
export default function ResendCode({ onResend }) {
  const [left, setLeft] = useState(WAIT);
  const [sends, setSends] = useState(1);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (left <= 0) return undefined;
    const t = setTimeout(() => setLeft((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);

  if (sends >= MAX_SENDS && left <= 0) {
    return (
      <Text fontSize="13px" color="text2" textAlign="center">
        Still no code? Check the number above and tap Change.
      </Text>
    );
  }
  if (left > 0) {
    return (
      <Text fontSize="13px" color="text3" textAlign="center" fontFamily="mono">
        Resend code in 0:{String(left).padStart(2, '0')}
      </Text>
    );
  }
  return (
    <Button
      variant="link"
      size="sm"
      alignSelf="center"
      isLoading={busy}
      onClick={async () => {
        setBusy(true);
        const ok = await onResend();
        setBusy(false);
        if (ok) {
          setSends((n) => n + 1);
          setLeft(WAIT);
        }
      }}
    >
      Resend code
    </Button>
  );
}
