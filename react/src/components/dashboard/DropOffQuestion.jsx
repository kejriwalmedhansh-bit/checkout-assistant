import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Box,
  Button,
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerOverlay,
  Flex,
  SimpleGrid,
  Text,
  Textarea,
} from '@chakra-ui/react';
import { useBlocker } from 'react-router-dom';

import { I } from '@/components/common/icons';
import { useUiStore } from '@/store/uiStore';
import { track } from '@/utils/analytics';
import { isGranted } from '@/utils/consent';

/**
 * "What stopped you?" — one tap, asked of people who saw the buying steps
 * and are leaving without tapping either Buy button.
 *
 * It opens at two moments:
 *  - leaving: Back (browser or in-app) or any link off this page, caught by
 *    the router so the question shows before the page goes; on a laptop,
 *    also the mouse heading up out of the window toward the tab's close button.
 *  - returning: they switched to another tab or app for a while and came
 *    back, still without having tapped Buy.
 * Never on a timer: someone reading the steps slowly isn't leaving.
 *
 * Ground rules: asked once per browser, ever; only after the steps have been
 * on screen a few seconds; only for people who allowed recording, since
 * otherwise the answer goes nowhere. Closing the tab outright on a phone
 * can't be caught; nothing on a web page runs in time for that.
 *
 * Answers go to Mixpanel as 'Drop-off Question Answered'. Shown-but-not-
 * answered is simply Shown minus Answered, so there is no separate
 * dismissed event.
 */

const ASKED_KEY = 'dealo-dropoff-asked';
// Steps must be on screen this long before leaving counts as a drop-off —
// bouncing off in the first seconds is a different problem this can't explain.
const ARM_AFTER_MS = 5000;
// An away-and-back shorter than this is a glance at another tab, not leaving.
const AWAY_MIN_MS = 10000;
// Mixpanel keeps the first 255 characters of a text property.
const NOTE_MAX = 250;

const REASONS = [
  { id: 'vouchers_confusing', label: 'Vouchers are confusing', icon: I.help },
  { id: 'not_sure_safe', label: "Not sure it's safe", icon: I.shield },
  { id: 'too_many_steps', label: 'Too many steps', icon: I.list },
  { id: 'found_cheaper', label: 'Found it cheaper', icon: I.arrowLeft },
  { id: 'just_checking', label: 'Just checking prices', icon: I.search },
  { id: 'something_else', label: 'Something else', icon: I.message },
];

function alreadyAsked() {
  try {
    return window.localStorage.getItem(ASKED_KEY) !== null;
  } catch {
    // Unreadable storage can't promise "only once", so don't ask at all.
    return true;
  }
}

function rememberAsked() {
  try {
    window.localStorage.setItem(ASKED_KEY, new Date().toISOString());
  } catch {
    // Nothing to do — see alreadyAsked.
  }
}

export default function DropOffQuestion({ merchant, hasVoucher }) {
  const buyLinkClicked = useUiStore((s) => s.buyLinkClicked);
  const tourActive = useUiStore((s) => s.tourActive);

  const [armed, setArmed] = useState(false);
  const [trigger, setTrigger] = useState(null);
  const [reason, setReason] = useState(null);
  const [note, setNote] = useState('');
  const [sent, setSent] = useState(false);

  // Decided once per page visit: after that, the question either showed
  // (and won't again) or this person is never asked.
  const eligible = useRef(null);
  if (eligible.current === null) eligible.current = isGranted() && !alreadyAsked();

  useEffect(() => {
    if (!eligible.current) return undefined;
    const t = setTimeout(() => setArmed(true), ARM_AFTER_MS);
    return () => clearTimeout(t);
  }, []);

  const canAsk = armed && eligible.current && !buyLinkClicked && !tourActive && trigger === null;
  const canAskRef = useRef(canAsk);
  const showingRef = useRef(false);
  canAskRef.current = canAsk;

  const open = useCallback((how) => {
    if (!canAskRef.current) return;
    canAskRef.current = false;
    showingRef.current = true;
    eligible.current = false;
    rememberAsked();
    setTrigger(how);
    track('Drop-off Question Shown', { trigger: how, merchant, has_voucher: hasVoucher });
  }, [merchant, hasVoucher]);

  // Leaving within the site (Back, the page's own back arrow, the logo…):
  // hold the navigation, ask, then let it continue however they answer.
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) => canAskRef.current && currentLocation.pathname !== nextLocation.pathname,
  );
  useEffect(() => {
    // Already showing (this effect can run twice for one block): the
    // question's own close lets the navigation through.
    if (blocker.state !== 'blocked' || showingRef.current) return;
    // Never leave someone stuck on the page: if asking is no longer
    // possible, just let the navigation through.
    if (canAskRef.current) open('leaving');
    else blocker.proceed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocker.state, open]);

  // Laptop only: the mouse leaving through the top edge is heading for the
  // tab strip or address bar. Touch screens have no equivalent.
  useEffect(() => {
    if (!window.matchMedia?.('(pointer: fine)').matches) return undefined;
    const onOut = (e) => {
      if (!e.relatedTarget && e.clientY <= 0) open('leaving');
    };
    document.addEventListener('mouseout', onOut);
    return () => document.removeEventListener('mouseout', onOut);
  }, [open]);

  // Away for a while, then back — still no Buy tap.
  useEffect(() => {
    let hiddenAt = null;
    const onVis = () => {
      if (document.visibilityState === 'hidden') {
        hiddenAt = Date.now();
      } else if (hiddenAt !== null) {
        if (Date.now() - hiddenAt >= AWAY_MIN_MS) open('returned');
        hiddenAt = null;
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [open]);

  const close = () => {
    showingRef.current = false;
    setTrigger(null);
    if (blocker.state === 'blocked') blocker.proceed();
  };

  const submit = () => {
    const trimmed = note.trim().slice(0, NOTE_MAX);
    track('Drop-off Question Answered', {
      // Typing without tapping a reason still counts as an answer.
      reason: reason || 'something_else',
      note: trimmed || undefined,
      trigger,
      merchant,
      has_voucher: hasVoucher,
    });
    setSent(true);
    setTimeout(close, 1400);
  };

  return (
    <Drawer isOpen={trigger !== null} placement="bottom" onClose={close}>
      <DrawerOverlay bg="blackAlpha.500" />
      <DrawerContent
        // Chakra stretches a bottom drawer edge to edge; on a laptop that's
        // a very wide strip for six small buttons.
        sx={{ maxWidth: '480px !important', marginInline: 'auto' }}
        bg="surface"
        borderTopRadius="20px"
        pb="env(safe-area-inset-bottom, 0px)"
      >
        <DrawerBody px="16px" pt="10px" pb="18px">
          <Box w="36px" h="4px" borderRadius="4px" bg="borderStrong" mx="auto" mb="12px" />
          {sent ? (
            <Flex direction="column" align="center" textAlign="center" py="22px" gap="4px">
              <Flex w="44px" h="44px" borderRadius="50%" bg="greenSoft" color="green" align="center" justify="center" mb="4px">
                <I.check size={22} />
              </Flex>
              <Text fontWeight={800}>Thanks — that helps.</Text>
              {blocker.state !== 'blocked' && (
                <Text fontSize="13px" color="text2">
                  Your deal is still here if you need it.
                </Text>
              )}
            </Flex>
          ) : (
            <>
              <Text fontSize="17px" fontWeight={800} m={0}>
                What stopped you?
              </Text>
              <Text fontSize="12.5px" color="text3" m="2px 0 12px">
                One tap. Helps us fix it.
              </Text>
              <SimpleGrid columns={2} spacing="8px" mb="10px" role="radiogroup" aria-label="What stopped you?">
                {REASONS.map((r) => {
                  const selected = reason === r.id;
                  return (
                    <Box
                      key={r.id}
                      as="button"
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => setReason(r.id)}
                      display="flex"
                      flexDirection="column"
                      alignItems="flex-start"
                      gap="4px"
                      textAlign="left"
                      p="10px"
                      borderRadius="12px"
                      border="1.5px solid"
                      borderColor={selected ? 'brand' : 'border'}
                      bg={selected ? 'surface3' : 'surface'}
                      color="text"
                      fontSize="13px"
                      fontWeight={600}
                      lineHeight={1.25}
                      transition="border-color .15s ease, background .15s ease"
                      _hover={{ borderColor: selected ? 'brand' : 'borderStrong' }}
                      _active={{ transform: 'scale(.98)' }}
                      _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
                    >
                      <Box color="text2">
                        <r.icon size={19} />
                      </Box>
                      {r.label}
                    </Box>
                  );
                })}
              </SimpleGrid>
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={NOTE_MAX}
                placeholder="Anything else? (optional)"
                aria-label="Anything else"
                rows={2}
                resize="none"
                fontSize="14px"
              />
              <Flex gap="8px" mt="10px">
                <Button variant="ghost" onClick={close} color="text3">
                  No thanks
                </Button>
                <Button flex={1} onClick={submit} isDisabled={!reason && !note.trim()}>
                  Send
                </Button>
              </Flex>
            </>
          )}
        </DrawerBody>
      </DrawerContent>
    </Drawer>
  );
}
