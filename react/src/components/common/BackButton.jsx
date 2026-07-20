import { Box, Button } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';

import { I } from './icons';

/**
 * "← Back" for the multi-step flow.
 *
 * Goes back through real browser history (`navigate(-1)`) rather than pushing a
 * hardcoded route, so this button and the phone's own back button always agree
 * — pressing either one lands in the same place, and neither leaves a stale
 * forward entry behind.
 *
 * The `fallback` route covers the one case where history can't help: a direct
 * arrival on a deep page (a shared link, a bookmark, a reopened tab). There is
 * no earlier in-app entry then, so `navigate(-1)` would eject the user out of
 * Dealo entirely into whatever they were browsing before. React Router records
 * its position in `window.history.state.idx`; index 0 (or a missing state, as
 * on a cold load) means nothing of ours is behind us, so we navigate to
 * `fallback` instead.
 */
export default function BackButton({ fallback, label = 'Back', ...props }) {
  const navigate = useNavigate();

  const goBack = () => {
    const idx = window.history.state?.idx;
    if (typeof idx === 'number' && idx > 0) {
      navigate(-1);
    } else {
      navigate(fallback, { replace: true });
    }
  };

  return (
    <Button
      variant="iconSubtle"
      onClick={goBack}
      aria-label={label}
      h="32px"
      px="10px"
      fontSize="13px"
      fontWeight={600}
      gap="6px"
      {...props}
    >
      <Box as="span" display="inline-flex" transform="rotate(180deg)">
        <I.chevRight size={16} />
      </Box>
      {label}
    </Button>
  );
}
