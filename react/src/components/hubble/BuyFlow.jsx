import { useEffect, useRef, useState } from 'react';
import { Box, Button, Checkbox, Flex, Input, InputGroup, InputLeftAddon, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { SELLER_FRAME_HOSTS, SELLER_NAMES, soldApi } from '@/api/sold.api';
import { confirmCode, currentUser, idToken, sendCode } from '@/lib/firebase';
import { track } from '@/utils/analytics';
import { fmt } from '@/utils/format';

const NAME_KEY = 'dealo_buyer_name';
const readName = () => {
  try {
    return localStorage.getItem(NAME_KEY) || '';
  } catch {
    return '';
  }
};
const saveName = (n) => {
  try {
    localStorage.setItem(NAME_KEY, n);
  } catch {
    /* private mode: the name is only a convenience */
  }
};

// Web pages open in a new tab; app links (upi://, phonepe://, myntra://) are
// handed to the phone, which opens the app.
const openHubbleLink = (link) => {
  if (typeof link !== 'string' || !link || /^(javascript|data):/i.test(link)) return;
  if (/^https?:/i.test(link)) window.open(link, '_blank', 'noopener');
  else window.location.href = link;
};

/**
 * Buying the voucher without leaving Dealo:
 *   details (name, mobile, deals tick) → SMS code → the seller's payment
 *   screen inside Dealo (Hubble or Maximize, per offer.seller) → voucher ready.
 * A shopper already logged in on this browser skips straight to payment.
 * Maximize shows the voucher code on its own thank-you screen inside the
 * frame, so that frame stays open after payment until the shopper closes it.
 */
export default function BuyFlow({ offer, merchant, price, shopLink, onClose, onBought }) {
  const seller = offer.seller || 'hubble';
  const sellerName = SELLER_NAMES[seller] || 'Hubble';
  const frameHost = SELLER_FRAME_HOSTS[seller] || SELLER_FRAME_HOSTS.hubble;
  const [step, setStep] = useState('loading');
  const [name, setName] = useState(readName);
  const [phone, setPhone] = useState('');
  const [optin, setOptin] = useState(false);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [storeUrl, setStoreUrl] = useState('');
  const [order, setOrder] = useState(null);
  const confirmation = useRef(null);
  const paid = useRef(false);

  const openStore = async (token) => {
    setBusy(true);
    try {
      const { url } = await soldApi.session(seller, {
        id_token: token,
        name: name.trim() || readName(),
        marketing_optin: optin,
        merchant,
        price,
        in_store: Boolean(offer.in_store),
      });
      track('Hubble Store Opened', { merchant, amount: offer.voucher_total, seller });
      setStoreUrl(url);
      setStep('store');
    } catch {
      setError('Something went wrong. Please try again.');
      setStep('details');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    let live = true;
    (async () => {
      const user = await currentUser();
      if (!live) return;
      if (user && readName()) openStore(await user.getIdToken());
      else setStep('details');
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The seller's screen reports payment and its own close button by postMessage.
  useEffect(() => {
    if (step !== 'store') return undefined;
    const onMessage = (e) => {
      if (!frameHost.test(new URL(e.origin).hostname)) return;
      let msg = e.data;
      if (typeof msg === 'string') {
        try {
          msg = JSON.parse(msg);
        } catch {
          return;
        }
      }
      const kind = msg?.event || msg?.action || msg?.type;
      // Inside a frame Hubble can't open apps itself: it asks us to open the
      // UPI app (upi://, phonepe://…) or the brand's app/site for it.
      if (kind === 'launch_link') openHubbleLink(msg.properties?.link);
      if (kind === 'payment_success') {
        paid.current = true;
        track('Hubble Payment Success', { merchant, amount: offer.voucher_total });
      }
      if (kind === 'payment_fail') track('Hubble Payment Failed', { merchant, amount: offer.voucher_total });
      // Paid, but Hubble couldn't make the card: Hubble refunds the payment
      // itself (5–7 working days per Yash, 27 Oct 2026). Say so plainly
      // rather than leaving the shopper on a blank "generating" screen.
      if (kind === 'voucher_generation_fail') {
        track('Hubble Voucher Failed', { merchant, amount: offer.voucher_total });
        setStep('failed');
      }
      // Hubble's screen itself failed to load (bad keys, network, login).
      if (kind === 'error' && msg?.type === 'action') {
        setError("Couldn't open the payment screen. Please try again.");
        setStep('details');
      }
      // The card exists: Dealo's own "voucher ready" screen takes over
      // straight away, instead of waiting for the shopper to close Hubble's.
      if (kind === 'voucher_generation_success') {
        paid.current = true;
        setStep('done');
      }
      // Maximize (sdk events, legacy and sdkBridge forms): the code is shown
      // inside its frame, so a paid shopper keeps the frame until they close it.
      if (kind === 'purchase_complete') {
        paid.current = true;
        track('Hubble Payment Success', { merchant, amount: offer.voucher_total, seller });
      }
      if (kind === 'session_expired' || kind === 'sdk_error') {
        setError("Couldn't open the payment screen. Please try again.");
        setStep('details');
      }
      if (kind === 'close' || kind === 'sdk_close') (paid.current ? setStep('done') : onClose());
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [step, merchant, offer.voucher_total, onClose, seller, frameHost]);

  // The voucher code reaches Dealo through the seller's order webhook a moment
  // after payment; ask a few times before falling back to the seller's own copy.
  useEffect(() => {
    if (step !== 'done') return undefined;
    onBought?.();
    let tries = 0;
    let timer;
    const poll = async () => {
      const token = await idToken();
      const res = token ? await soldApi.latestOrder(seller, token).catch(() => null) : null;
      if (res?.found) setOrder(res);
      else if (++tries < 10) timer = setTimeout(poll, 2000);
    };
    poll();
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  const phoneOk = /^[6-9]\d{9}$/.test(phone);
  const getCode = async () => {
    setError('');
    setBusy(true);
    try {
      saveName(name.trim());
      confirmation.current = await sendCode(phone, 'dealo-get-code');
      track('Login Code Sent', { merchant });
      setStep('code');
    } catch (err) {
      console.error('[login] send code failed', err?.code, err?.message);
      setError("Couldn't send the code. Check the number and try again.");
    } finally {
      setBusy(false);
    }
  };

  const onCode = async (value) => {
    const digits = value.replace(/\D/g, '').slice(0, 6);
    setCode(digits);
    if (digits.length !== 6) return;
    setError('');
    setBusy(true);
    try {
      const token = await confirmCode(confirmation.current, digits);
      await openStore(token);
    } catch {
      setError('That code didn’t match. Try again.');
      setCode('');
      setBusy(false);
    }
  };

  const voucher = order?.vouchers?.[0];
  const copy = (text) => navigator.clipboard?.writeText(text).catch(() => {});

  if (step === 'store') {
    return (
      <Box position="fixed" inset={0} zIndex={1400} bg="rgba(22,32,43,.6)">
        <Flex direction="column" position="absolute" top="24px" left={0} right={0} bottom={0} bg="surface" borderTopRadius="24px" overflow="hidden">
          <Flex h="52px" align="center" justify="space-between" px="14px" borderBottom="1px solid" borderColor="border">
            <Flex align="center" gap="8px" fontSize="13px" fontWeight={700} color="text2">
              <Box color="green">
                <I.check size={14} />
              </Box>
              Secure payment · {sellerName}
            </Flex>
            <Button aria-label="Close" variant="ghost" size="sm" onClick={() => (paid.current ? setStep('done') : onClose())}>
              <I.x size={18} />
            </Button>
          </Flex>
          <Box as="iframe" title={`${sellerName} payment`} src={storeUrl} allow="payment; clipboard-write" flex="1" w="100%" border={0} />
        </Flex>
      </Box>
    );
  }

  return (
    <Box position="fixed" inset={0} zIndex={1400} bg="rgba(22,32,43,.55)" onClick={step === 'done' || step === 'failed' ? undefined : onClose}>
      <Box
        position="absolute"
        left={0}
        right={0}
        bottom={0}
        mx="auto"
        maxW="480px"
        bg="surface"
        borderTopRadius="28px"
        px="20px"
        pt="10px"
        pb="28px"
        onClick={(e) => e.stopPropagation()}
      >
        <Box w="38px" h="5px" borderRadius="3px" bg="borderStrong" mx="auto" mb="14px" />

        {step === 'loading' && (
          <Text textAlign="center" py="40px" color="text2" fontWeight={600}>
            Opening…
          </Text>
        )}

        {step === 'details' && (
          <Flex direction="column" gap="16px">
            <Flex justify="space-between" align="center">
              <Text fontSize="24px" fontWeight={800} letterSpacing="-.02em">
                Almost there
              </Text>
              <Text fontFamily="mono" fontWeight={700} fontSize="13px" bg="surface2" border="1px solid" borderColor="border" borderRadius="pill" px="10px" py="4px">
                {offer.brand_name} · {fmt(Math.round(offer.you_pay))}
              </Text>
            </Flex>
            <Box as="label">
              <Text fontSize="13px" fontWeight={700} color="text2" mb="6px">
                Your name
              </Text>
              <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" h="54px" borderRadius="14px" fontSize="17px" fontWeight={600} />
            </Box>
            <Box as="label">
              <Text fontSize="13px" fontWeight={700} color="text2" mb="6px">
                Mobile number
              </Text>
              <InputGroup h="54px">
                <InputLeftAddon h="54px" fontFamily="mono" fontWeight={600} borderLeftRadius="14px" bg="surface2" border="1px solid" borderColor="border" color="text2">
                  +91
                </InputLeftAddon>
                <Input
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel-national"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(-10))}
                  h="54px"
                  borderRightRadius="14px"
                  fontFamily="mono"
                  fontSize="17px"
                  fontWeight={600}
                />
              </InputGroup>
            </Box>
            <Checkbox isChecked={optin} onChange={(e) => setOptin(e.target.checked)} size="lg" colorScheme="blue">
              <Text fontSize="13px" fontWeight={600}>
                Send me deals and updates on WhatsApp
              </Text>
            </Checkbox>
            {error && (
              <Text fontSize="13px" color="danger" fontWeight={600}>
                {error}
              </Text>
            )}
            <Button
              id="dealo-get-code"
              onClick={getCode}
              isDisabled={!name.trim() || !phoneOk}
              isLoading={busy}
              h="56px"
              borderRadius="pill"
              bg="amber"
              color="white"
              fontSize="17px"
              fontWeight={800}
              rightIcon={<I.arrowRight size={18} />}
              _hover={{ bg: 'amber' }}
            >
              Get code by SMS
            </Button>
            <Text fontSize="13px" color="text2" textAlign="center">
              Only for your login and voucher · <a href="/privacy">Privacy</a>
            </Text>
          </Flex>
        )}

        {step === 'code' && (
          <Flex direction="column" gap="16px">
            <Flex justify="space-between" align="center">
              <Box>
                <Text fontSize="24px" fontWeight={800} letterSpacing="-.02em">
                  Enter the code
                </Text>
                <Text fontFamily="mono" fontSize="13px" color="text2">
                  Sent by SMS to +91 {phone}
                </Text>
              </Box>
              <Button variant="link" size="sm" onClick={() => setStep('details')}>
                Change
              </Button>
            </Flex>
            <Input
              autoFocus
              value={code}
              onChange={(e) => onCode(e.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="••••••"
              textAlign="center"
              letterSpacing=".5em"
              fontFamily="mono"
              fontSize="26px"
              fontWeight={700}
              h="64px"
              borderRadius="14px"
              isDisabled={busy}
            />
            {error && (
              <Text fontSize="13px" color="danger" fontWeight={600}>
                {error}
              </Text>
            )}
            {busy && (
              <Text textAlign="center" fontSize="14px" fontWeight={700} color="brand">
                Opening payment…
              </Text>
            )}
          </Flex>
        )}

        {step === 'failed' && (
          <Flex direction="column" gap="14px" py="8px">
            <Text fontSize="22px" fontWeight={800}>
              Voucher couldn’t be made
            </Text>
            <Text fontSize="14px" color="text2">
              {offer.brand_name} didn’t issue the voucher this time. If your payment went through, {sellerName} refunds it
              to the same account automatically within 5–7 working days. You don’t need to do anything.
            </Text>
            <Button onClick={onClose} h="52px" borderRadius="pill" bg="text" color="white" fontWeight={800} _hover={{ bg: 'text' }}>
              OK
            </Button>
          </Flex>
        )}

        {step === 'done' && (
          <Flex direction="column" gap="14px">
            <Flex direction="column" align="center" gap="6px">
              <Flex w="48px" h="48px" borderRadius="50%" bg="brass" color="white" align="center" justify="center">
                <I.check size={22} />
              </Flex>
              <Text fontSize="22px" fontWeight={800}>
                Voucher ready
              </Text>
              <Text fontFamily="mono" fontWeight={700} color="green">
                {fmt(Math.round(offer.you_save))} saved
              </Text>
            </Flex>
            {voucher ? (
              <Box borderRadius="18px" bg="text" color="onBrand" p="16px">
                <Text fontSize="11px" letterSpacing=".12em" opacity={0.6}>
                  CODE
                </Text>
                <Text fontFamily="mono" fontWeight={600} fontSize="17px">
                  {voucher.code}
                </Text>
                {voucher.pin && (
                  <>
                    <Text fontSize="11px" letterSpacing=".12em" opacity={0.6} mt="8px">
                      PIN
                    </Text>
                    <Text fontFamily="mono" fontWeight={600} fontSize="17px">
                      {voucher.pin}
                    </Text>
                  </>
                )}
              </Box>
            ) : (
              <Text fontSize="13px" color="text2" textAlign="center">
                {seller === 'maximize' ? `Your code was shown on the ${sellerName} screen; it will appear here too in a moment.` : 'Fetching your code…'}
              </Text>
            )}
            {offer.in_store ? (
              <Text fontSize="14px" fontWeight={700} textAlign="center">
                Show this code and PIN at the {offer.brand_name} counter when you pay.
              </Text>
            ) : (
              <Button
                as="a"
                href={offer.add_voucher_url || shopLink || undefined}
                target="_blank"
                rel="noopener"
                onClick={() => voucher && copy(voucher.code)}
                h="56px"
                borderRadius="pill"
                bg="text"
                color="white"
                fontSize="17px"
                fontWeight={800}
                rightIcon={<I.external size={16} />}
                _hover={{ bg: 'text' }}
              >
                {offer.add_voucher_url ? `Add to ${offer.brand_name} wallet` : `Open ${offer.brand_name}`}
              </Button>
            )}
            {!offer.in_store && voucher && (
              <Text fontSize="12px" color="text2" textAlign="center">
                Code copied · paste it there
              </Text>
            )}
            <Button variant="ghost" onClick={onClose}>
              Done
            </Button>
          </Flex>
        )}
      </Box>
    </Box>
  );
}
