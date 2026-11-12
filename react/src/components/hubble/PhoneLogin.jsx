import { useEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Input, Text } from '@chakra-ui/react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';

import { I } from '@/components/common/icons';
import { hubbleApi } from '@/api/hubble.api';
import { confirmCode, sendCode } from '@/lib/firebase';
import { readBuyerName, saveBuyerName, setSignedIn } from '@/lib/myVouchers';
import { EASE_OUT } from '@/theme/motion';
import { track } from '@/utils/analytics';

import ResendCode from './ResendCode';

const MotionBox = motion.create(Box);
const phoneOk = (p) => /^[6-9]\d{9}$/.test(p);
// "98765 43210": easier to check at a glance than ten digits in a row.
// Typed, pasted or autofilled ("+91 98765 43210", "098765…"): the last ten
// digits when a country code or 0 leads, otherwise the first ten typed.
const tenDigits = (v) => {
  const d = v.replace(/\D/g, '');
  return d.length > 10 && /^(91|0)/.test(d) ? d.slice(-10) : d.slice(0, 10);
};
const spaced = (p) => (p.length > 5 ? `${p.slice(0, 5)} ${p.slice(5)}` : p);

function Field({ label, hint, htmlFor, children }) {
  return (
    <Box>
      <Text as="label" htmlFor={htmlFor} display="block" fontSize="13px" fontWeight={700} color="text2" mb="6px">
        {label}
      </Text>
      {/* Hints sit above the box, so the keyboard and autofill bar never cover them. */}
      {hint}
      {children}
    </Box>
  );
}

function PrimaryButton({ children, isLoading, isDisabled }) {
  return (
    <Button
      type="submit"
      isLoading={isLoading}
      isDisabled={isDisabled}
      h="56px"
      w="100%"
      borderRadius="pill"
      bg="amber"
      color="white"
      fontSize="17px"
      fontWeight={800}
      rightIcon={<I.arrowRight size={18} />}
      _hover={{ bg: 'amber', _disabled: { bg: 'amber' } }}
      _active={{ transform: 'scale(0.97)' }}
    >
      {children}
    </Button>
  );
}

const ERROR_TEXT = { fontSize: '13px', color: 'danger', fontWeight: 600, role: 'alert' };

/**
 * Phone-first SMS login, the way Swiggy, Amazon and Flipkart do it:
 *   mobile number → 6-digit code → (new numbers only) name + optional email.
 * A returning shopper types their number and the code, nothing else.
 *
 * Used by "Your account" and by the buy flow. `onDone({ token, name, isNew })`
 * fires once the shopper is logged in and we know what to call them.
 *
 * The code box follows Google's SMS form guide: one field (never six boxes),
 * numeric keypad, autocomplete="one-time-code" (iPhone suggests the code
 * above the keyboard), and Android Chrome's WebOTP when the SMS allows it.
 */
export default function PhoneLogin({ intro, phoneExtra, place, trackProps, onDone }) {
  const reduce = useReducedMotion();
  const [step, setStep] = useState('phone');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [name, setName] = useState(readBuyerName);
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(false);
  const [wrong, setWrong] = useState(0);
  const holder = useRef(null);
  const confirmation = useRef(null);
  const token = useRef(null);
  const codeForm = useRef(null);
  const props = { placement: place, ...trackProps };

  const getCode = async () => {
    setError('');
    setBusy(true);
    try {
      confirmation.current = await sendCode(phone, holder.current);
      track('Login Code Sent', props);
      setCode('');
      setStep('code');
      return true;
    } catch (err) {
      console.error('[login] send code failed', err?.code, err?.message);
      setError(err?.code === 'auth/too-many-requests' ? 'Too many tries. Please wait a few minutes.' : "Couldn't send the code. Check the number and try again.");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const finish = (nm, isNew) => {
    saveBuyerName(nm);
    setSignedIn(true);
    track('Logged In', { ...props, new: isNew });
    onDone({ token: token.current, name: nm, isNew });
  };

  const verify = async (digits) => {
    if (checking || digits.length !== 6) return;
    setError('');
    setChecking(true);
    try {
      token.current = await confirmCode(confirmation.current, digits);
    } catch {
      setError('That code didn’t match. Try again.');
      setWrong((n) => n + 1);
      setCode('');
      setChecking(false);
      return;
    }
    // Server down: fall back to the name kept on this browser, if any.
    const known = await hubbleApi.login(token.current).catch(() => ({ name: readBuyerName() || null }));
    if (known?.name) {
      finish(known.name, false);
      return;
    }
    setChecking(false);
    setStep('profile');
  };

  // Android Chrome reads the code straight from the SMS when its last line is
  // "@getdealo.in #123456" (WebOTP). Elsewhere this quietly does nothing.
  useEffect(() => {
    if (step !== 'code' || !('OTPCredential' in window)) return undefined;
    const ac = new AbortController();
    navigator.credentials
      .get({ otp: { transport: ['sms'] }, signal: ac.signal })
      .then((otp) => {
        if (!otp?.code) return;
        setCode(otp.code);
        verify(otp.code);
      })
      .catch(() => {});
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, confirmation.current]);

  const saveProfile = async () => {
    const nm = name.trim();
    setBusy(true);
    // Saving is a nicety: the login works even if this fails.
    await hubbleApi.account({ id_token: token.current, name: nm, email: email.trim() || null }).catch(() => {});
    setBusy(false);
    finish(nm, true);
  };

  const emailOk = !email.trim() || /^\S+@\S+\.\S+$/.test(email.trim());
  const badStart = phone.length === 10 && !phoneOk(phone);
  const slide = reduce
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } }
    : { initial: { opacity: 0, transform: 'translateX(12px)' }, animate: { opacity: 1, transform: 'translateX(0px)' }, exit: { opacity: 0, transform: 'translateX(-12px)' } };

  return (
    <Box>
      {/* Firebase's invisible robot check: one hidden spot for the whole login. */}
      <div ref={holder} />
      <AnimatePresence mode="wait" initial={false}>
        <MotionBox key={step} {...slide} transition={{ duration: 0.2, ease: EASE_OUT }}>
          {step === 'phone' && (
            <Flex
              as="form"
              direction="column"
              gap="16px"
              onSubmit={(e) => {
                e.preventDefault();
                if (phoneOk(phone) && !busy) getCode();
              }}
            >
              {intro}
              <Field label="Mobile number" htmlFor="login-phone">
                <Flex
                  align="center"
                  h="58px"
                  borderRadius="14px"
                  border="1px solid"
                  borderColor={badStart ? 'danger' : 'border'}
                  bg="surface"
                  transition="border-color .15s, box-shadow .15s"
                  _hover={{ borderColor: badStart ? 'danger' : 'borderStrong' }}
                  _focusWithin={{ borderColor: badStart ? 'danger' : 'brand', boxShadow: 'ring' }}
                >
                  <Text px="14px" fontFamily="mono" fontSize="17px" fontWeight={600} color="text2" borderRight="1px solid" borderColor="border" h="60%" display="flex" alignItems="center">
                    +91
                  </Text>
                  <Input
                    id="login-phone"
                    variant="unstyled"
                    autoFocus
                    type="tel"
                    inputMode="numeric"
                    autoComplete="tel-national"
                    placeholder="98765 43210"
                    value={spaced(phone)}
                    onChange={(e) => setPhone(tenDigits(e.target.value))}
                    aria-invalid={badStart}
                    aria-describedby="login-phone-note"
                    h="100%"
                    px="14px"
                    fontFamily="mono"
                    fontSize="19px"
                    fontWeight={600}
                    letterSpacing=".02em"
                    _placeholder={{ color: 'text3', fontWeight: 500 }}
                  />
                </Flex>
                <Text id="login-phone-note" fontSize="12.5px" mt="6px" color={badStart ? 'danger' : 'text3'}>
                  {badStart ? 'Indian mobile numbers start with 6, 7, 8 or 9' : 'We’ll text you a 6-digit code'}
                </Text>
              </Field>
              {phoneExtra}
              {error && <Text {...ERROR_TEXT}>{error}</Text>}
              <PrimaryButton isLoading={busy} isDisabled={!phoneOk(phone)}>
                Get code
              </PrimaryButton>
              <Text fontSize="12.5px" color="text3" textAlign="center">
                New here? The same step signs you up · <a href="/privacy">Privacy</a>
              </Text>
            </Flex>
          )}

          {step === 'code' && (
            <Flex
              as="form"
              ref={codeForm}
              direction="column"
              gap="14px"
              onSubmit={(e) => {
                e.preventDefault();
                verify(code);
              }}
            >
              <Field
                label="Enter the 6-digit code"
                htmlFor="login-code"
                hint={
                  <Flex id="login-code-hint" align="center" justify="space-between" mb="8px" gap="8px">
                    <Text fontSize="13px" color="text2">
                      Sent to <Text as="span" fontFamily="mono" fontWeight={600} color="text">+91 {spaced(phone)}</Text>
                    </Text>
                    <Button variant="link" size="sm" color="brand" onClick={() => setStep('phone')}>
                      Change
                    </Button>
                  </Flex>
                }
              >
                <MotionBox
                  key={wrong}
                  animate={wrong && !reduce ? { transform: ['translateX(0px)', 'translateX(-6px)', 'translateX(6px)', 'translateX(-3px)', 'translateX(0px)'] } : undefined}
                  transition={{ duration: 0.28, ease: 'easeOut' }}
                >
                  <Input
                    id="login-code"
                    name="otp"
                    autoFocus
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="\d{6}"
                    maxLength={6}
                    aria-describedby="login-code-hint"
                    aria-invalid={Boolean(error)}
                    value={code}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, '').slice(0, 6);
                      setCode(digits);
                      if (digits.length === 6) verify(digits);
                    }}
                    placeholder="••••••"
                    textAlign="center"
                    letterSpacing=".5em"
                    fontFamily="mono"
                    fontSize="26px"
                    fontWeight={700}
                    h="64px"
                    borderRadius="14px"
                    borderColor={error ? 'danger' : 'border'}
                    isDisabled={checking}
                  />
                </MotionBox>
              </Field>
              {error && <Text {...ERROR_TEXT}>{error}</Text>}
              {checking ? (
                <Flex align="center" justify="center" gap="8px" fontSize="14px" fontWeight={700} color="brand">
                  <Box className="dealo-spin" w="14px" h="14px" borderRadius="50%" border="2px solid" borderColor="brand" borderTopColor="transparent" />
                  Checking…
                </Flex>
              ) : (
                <ResendCode onResend={getCode} />
              )}
            </Flex>
          )}

          {step === 'profile' && (
            <Flex
              as="form"
              direction="column"
              gap="16px"
              onSubmit={(e) => {
                e.preventDefault();
                if (name.trim() && emailOk && !busy) saveProfile();
              }}
            >
              <Flex align="center" gap="10px" bg="brandSoft" color="brand" borderRadius="12px" px="12px" py="10px">
                <I.check size={16} />
                <Text fontSize="14px" fontWeight={700}>
                  Number verified. One last thing, just this once:
                </Text>
              </Flex>
              <Field label="Your name" htmlFor="login-name">
                <Input id="login-name" autoFocus value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" autoCapitalize="words" enterKeyHint="next" h="54px" borderRadius="14px" fontSize="17px" fontWeight={600} />
              </Field>
              <Field label="Email (optional)" htmlFor="login-email">
                <Input
                  id="login-email"
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  enterKeyHint="done"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  aria-invalid={!emailOk}
                  aria-describedby="login-email-note"
                  h="54px"
                  borderRadius="14px"
                  fontSize="17px"
                  fontWeight={600}
                  borderColor={emailOk ? 'border' : 'danger'}
                />
                <Text id="login-email-note" fontSize="12.5px" mt="6px" color={emailOk ? 'text3' : 'danger'}>
                  {emailOk ? 'For receipts. Never shared.' : 'That email doesn’t look right'}
                </Text>
              </Field>
              <PrimaryButton isLoading={busy} isDisabled={!name.trim() || !emailOk}>
                Continue
              </PrimaryButton>
            </Flex>
          )}
        </MotionBox>
      </AnimatePresence>
    </Box>
  );
}
