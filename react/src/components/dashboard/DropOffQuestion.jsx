import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Flex, Input, Text } from '@chakra-ui/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useBlocker } from 'react-router-dom';

import { I } from '@/components/common/icons';
import { useUiStore } from '@/store/uiStore';
import { track } from '@/utils/analytics';
import { isGranted } from '@/utils/consent';

/**
 * "Not buying? Tell us why" — a small pill for people who saw the buying
 * steps and are leaving without tapping either Buy button.
 *
 * Deliberately small, never a panel over the page: most visitors are on a
 * phone, and a sheet covering the screen read as a wall (user feedback
 * 2026-09-19). It pops in as a round button, stretches into the question a
 * beat later, and only grows into the answers if tapped. It's the same shape
 * all the way through, never a new window.
 *
 * It appears at two moments:
 *  - leaving: Back (browser or in-app) or any link off this page, caught by
 *    the router and held while the pill shows; pressing Back again (or ✕, or
 *    answering) lets it through. On a laptop, also the mouse heading up out
 *    of the window toward the tab's close button.
 *  - returning: they switched to another tab or app for a while and came
 *    back, still without having tapped Buy.
 * Never on a timer: someone reading the steps slowly isn't leaving.
 *
 * Ground rules: asked once per browser, ever; only after the steps have been
 * on screen a few seconds; only for people who allowed recording, since
 * otherwise the answer goes nowhere. Closing the tab outright on a phone
 * can't be caught; nothing on a web page runs in time for that.
 */

const ASKED_KEY = 'dealo-dropoff-asked';
// Steps must be on screen this long before leaving counts as a drop-off —
// bouncing off in the first seconds is a different problem this can't explain.
const ARM_AFTER_MS = 5000;
// An away-and-back shorter than this is a glance at another tab, not leaving.
const AWAY_MIN_MS = 10000;
// The round button holds this long before stretching into the question.
const STRETCH_AFTER_MS = 500;
// Left untouched this long, the pill quietly goes away.
const IDLE_HIDE_MS = 20000;
// After answering, the thank-you stays this long unless they start typing.
const THANKS_HIDE_MS = 6000;
// Mixpanel keeps the first 255 characters of a text property.
const NOTE_MAX = 250;

const REASONS = [
  { id: 'vouchers_confusing', label: 'Vouchers confuse me' },
  { id: 'not_sure_safe', label: 'Not sure it’s safe' },
  { id: 'too_many_steps', label: 'Too many steps' },
  { id: 'found_cheaper', label: 'Found it cheaper' },
  { id: 'just_checking', label: 'Just browsing' },
  { id: 'something_else', label: 'Something else' },
];

// Pill colours are the page's ink and paper swapped, so it's dark on the light
// theme and light on the dark one — always distinct, and never the Buy
// button's gold. Lines inside it are the pill's own text colour, faded.
const faint = (pct) => `color-mix(in srgb, currentColor ${pct}%, transparent)`;
const EASE_OUT = [0.22, 1, 0.36, 1];

const MotionBox = motion(Box);

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

function CloseButton({ onClick, label }) {
  return (
    <Box
      as="button"
      type="button"
      onClick={onClick}
      aria-label={label}
      display="grid"
      placeItems="center"
      w="36px"
      h="44px"
      flex="0 0 auto"
      color={faint(60)}
      _hover={{ color: 'currentColor' }}
      _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '-4px', borderRadius: '10px' }}
    >
      <I.x size={13} sw={2.2} />
    </Box>
  );
}

export default function DropOffQuestion({ merchant, hasVoucher }) {
  const reduceMotion = useReducedMotion();
  const buyLinkClicked = useUiStore((s) => s.buyLinkClicked);
  const tourActive = useUiStore((s) => s.tourActive);

  const [armed, setArmed] = useState(false);
  // hidden → dot (round button pops in) → pill (stretched, with the question)
  // → card (answers) → thanks (optional comment) → hidden.
  const [stage, setStage] = useState('hidden');
  const [trigger, setTrigger] = useState(null);
  const [reason, setReason] = useState(null);
  const [note, setNote] = useState('');

  // Decided once per page visit: after that, the pill either showed (and
  // won't again) or this person is never asked.
  const eligible = useRef(null);
  if (eligible.current === null) eligible.current = isGranted() && !alreadyAsked();

  useEffect(() => {
    if (!eligible.current) return undefined;
    const t = setTimeout(() => setArmed(true), ARM_AFTER_MS);
    return () => clearTimeout(t);
  }, []);

  const canAsk = armed && eligible.current && !buyLinkClicked && !tourActive;
  const canAskRef = useRef(canAsk);
  canAskRef.current = canAsk;
  const showingRef = useRef(false);

  const open = useCallback(
    (how) => {
      if (!canAskRef.current) return;
      canAskRef.current = false;
      showingRef.current = true;
      eligible.current = false;
      rememberAsked();
      setTrigger(how);
      setStage('dot');
      track('Drop-off Question Shown', { trigger: how, merchant, has_voucher: hasVoucher });
    },
    [merchant, hasVoucher],
  );

  // Leaving within the site (Back, the page's own back arrow, the logo…):
  // hold the navigation while the pill shows. Nothing is blocked after that —
  // a second Back, ✕, or answering all let them go.
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) => canAskRef.current && currentLocation.pathname !== nextLocation.pathname,
  );
  const blockerRef = useRef(blocker);
  blockerRef.current = blocker;
  useEffect(() => {
    // Already showing (this effect can run twice for one block): closing the
    // pill lets the navigation through.
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

  // `leave`: they pressed Back and have now answered or dismissed, so let
  // that Back through. An ignored pill fading on its own must not: a page
  // jumping back 20 seconds after they last touched Back would be a surprise,
  // so the held Back is dropped and they stay put.
  const close = useCallback((leave = true) => {
    showingRef.current = false;
    setStage('hidden');
    const b = blockerRef.current;
    if (b.state === 'blocked') {
      if (leave) b.proceed();
      else b.reset();
    }
  }, []);
  const closeButton = useCallback(() => close(true), [close]);

  // Tapped Buy while the pill was up: they're not leaving after all, so the
  // pill goes and any held Back is dropped.
  useEffect(() => {
    if (buyLinkClicked && showingRef.current) close(false);
  }, [buyLinkClicked, close]);

  // The round button holds a beat, then stretches into the question.
  useEffect(() => {
    if (stage !== 'dot') return undefined;
    const t = setTimeout(() => setStage('pill'), reduceMotion ? 0 : STRETCH_AFTER_MS);
    return () => clearTimeout(t);
  }, [stage, reduceMotion]);

  // Ignored pill, or a thank-you nobody is typing into, goes away on its own.
  useEffect(() => {
    if (stage === 'pill') {
      const t = setTimeout(() => close(false), IDLE_HIDE_MS);
      return () => clearTimeout(t);
    }
    if (stage === 'thanks' && !note) {
      const t = setTimeout(() => close(true), THANKS_HIDE_MS);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [stage, note, close]);

  const expand = () => {
    track('Drop-off Question Opened', { trigger, merchant, has_voucher: hasVoucher });
    setStage('card');
  };

  const answer = (id) => {
    setReason(id);
    setStage('thanks');
    track('Drop-off Question Answered', { reason: id, trigger, merchant, has_voucher: hasVoucher });
  };

  const sendNote = () => {
    const trimmed = note.trim().slice(0, NOTE_MAX);
    if (trimmed) {
      track('Drop-off Comment Sent', { reason, note: trimmed, trigger, merchant, has_voucher: hasVoucher });
    }
    close(true);
  };

  const wide = stage === 'card' || stage === 'thanks';
  const fade = {
    initial: { opacity: 0, filter: reduceMotion ? 'none' : 'blur(3px)' },
    animate: { opacity: 1, filter: 'blur(0px)', transition: { duration: 0.25, delay: reduceMotion ? 0 : 0.12 } },
    exit: { opacity: 0, transition: { duration: 0.1 } },
  };

  return (
    <Box
      position="fixed"
      left={{ base: '16px', md: '28px' }}
      bottom={{ base: '24px', md: '32px' }}
      zIndex={20}
      // Room for the WhatsApp button on the right while collapsed; the open
      // card may cover it, since it's what they're looking at then.
      maxW={wide ? 'min(360px, calc(100vw - 32px))' : 'calc(100vw - 104px)'}
    >
      <AnimatePresence>
        {stage !== 'hidden' && (
          <MotionBox
            key="dropoff"
            layout
            role={wide ? 'dialog' : undefined}
            aria-label={wide ? 'Why you’re not buying' : undefined}
            initial={{ scale: reduceMotion ? 1 : 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.85, opacity: 0, transition: { duration: 0.18 } }}
            transition={{
              // A small spring on the pop only; the stretch and grow ease out.
              scale: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 520, damping: 24 },
              opacity: { duration: 0.15 },
              layout: reduceMotion ? { duration: 0 } : { duration: 0.45, ease: EASE_OUT },
            }}
            style={{ borderRadius: wide ? 20 : 22, originX: 0, originY: 1 }}
            bg="text"
            color="surface"
            overflow="hidden"
            boxShadow="0 1px 2px rgba(10,12,10,.14), 0 12px 30px -12px rgba(10,12,10,.5)"
            w={wide ? 'min(360px, calc(100vw - 32px))' : undefined}
          >
            <AnimatePresence mode="popLayout" initial={false}>
              {(stage === 'dot' || stage === 'pill') && (
                <motion.div key="pill" layout="position" {...fade}>
                  <Flex align="center" h="44px" whiteSpace="nowrap">
                    <Box
                      as="button"
                      type="button"
                      onClick={expand}
                      display="flex"
                      alignItems="center"
                      h="44px"
                      minW="44px"
                      pr={stage === 'pill' ? '2px' : 0}
                      aria-label="Not buying? Tell us why"
                      _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '-4px', borderRadius: '22px' }}
                    >
                      <Flex w="44px" h="44px" align="center" justify="center" flex="0 0 44px">
                        <I.feedback size={19} sw={1.9} />
                      </Flex>
                      {stage === 'pill' && (
                        <motion.span {...fade}>
                          <Text as="span" fontSize="13.5px" fontWeight={600} letterSpacing="-.005em">
                            Not buying? Tell us why
                          </Text>
                        </motion.span>
                      )}
                    </Box>
                    {stage === 'pill' && (
                      <motion.div {...fade}>
                        <CloseButton onClick={closeButton} label="Dismiss" />
                      </motion.div>
                    )}
                  </Flex>
                </motion.div>
              )}

              {stage === 'card' && (
                <motion.div key="card" layout="position" {...fade}>
                  <Box pl="16px" pr="4px" pb="14px">
                    <Flex align="center" justify="space-between">
                      <Text fontSize="14.5px" fontWeight={700} letterSpacing="-.01em">
                        What stopped you?
                      </Text>
                      <CloseButton onClick={closeButton} label="Close" />
                    </Flex>
                    <Flex wrap="wrap" gap="6px" pr="12px">
                      {REASONS.map((r) => (
                        <Box
                          key={r.id}
                          as="button"
                          type="button"
                          onClick={() => answer(r.id)}
                          border="1px solid"
                          borderColor={faint(18)}
                          borderRadius="full"
                          px="12px"
                          py="8px"
                          fontSize="13px"
                          fontWeight={600}
                          lineHeight={1.2}
                          transition="background .15s ease, transform .1s ease"
                          _hover={{ bg: faint(8) }}
                          _active={{ transform: 'scale(.96)' }}
                          _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
                        >
                          {r.label}
                        </Box>
                      ))}
                    </Flex>
                  </Box>
                </motion.div>
              )}

              {stage === 'thanks' && (
                <motion.div key="thanks" layout="position" {...fade}>
                  <Box pl="16px" pr="4px" pb="14px">
                    <Flex align="center" justify="space-between">
                      <Flex align="center" gap="10px" fontSize="14px" fontWeight={600}>
                        <Box color="green">
                          <I.check size={18} sw={2.4} />
                        </Box>
                        Thanks — that helps us fix it.
                      </Flex>
                      <CloseButton onClick={closeButton} label="Close" />
                    </Flex>
                    <Flex gap="6px" pr="12px">
                      <Input
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && sendNote()}
                        maxLength={NOTE_MAX}
                        placeholder="Say more? (optional)"
                        aria-label="Say more"
                        h="40px"
                        // 16px keeps iPhones from zooming into the box on tap.
                        fontSize="16px"
                        color="inherit"
                        bg="transparent"
                        borderColor={faint(22)}
                        _placeholder={{ color: faint(55) }}
                        _hover={{ borderColor: faint(35) }}
                      />
                      <Box
                        as="button"
                        type="button"
                        onClick={sendNote}
                        flex="0 0 auto"
                        px="14px"
                        h="40px"
                        borderRadius="10px"
                        bg="surface"
                        color="text"
                        fontSize="13.5px"
                        fontWeight={700}
                        _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
                      >
                        Send
                      </Box>
                    </Flex>
                  </Box>
                </motion.div>
              )}
            </AnimatePresence>
          </MotionBox>
        )}
      </AnimatePresence>
    </Box>
  );
}
