import { useEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Input, InputGroup, InputLeftAddon, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { hubbleApi } from '@/api/hubble.api';
import { confirmCode, idToken, sendCode, signOut } from '@/lib/firebase';
import {
  clearPending,
  forgetVoucher,
  pendingPurchase,
  readBuyerName,
  saveBuyerName,
  saveOrder,
  setSignedIn,
  setVouchersOpen,
  useSavedVouchers,
  useVouchersOpen,
} from '@/lib/myVouchers';
import { track } from '@/utils/analytics';
import { fmt } from '@/utils/format';

import CodeRow from './CodeRow';

const copyText = (text) => navigator.clipboard?.writeText(text).catch(() => {});

function VoucherCard({ v }) {
  const [copied, setCopied] = useState(null);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copyField = (field, text) => {
    copyText(text);
    setCopied(field);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(null), 600);
  };
  const link = v.add_voucher_url || v.shop_link;
  const bought = new Date(v.saved_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

  return (
    <Box borderRadius="18px" bg="text" color="onBrand" p="16px">
      <Flex justify="space-between" align="baseline" mb="10px" gap="8px">
        <Text fontWeight={800} fontSize="16px">
          {v.brand}
          {v.amount ? ` · ${fmt(v.amount)}` : ''}
        </Text>
        <Text fontSize="12px" opacity={0.6} flexShrink={0}>
          {bought}
        </Text>
      </Flex>
      <CodeRow label="CODE" value={v.code} copied={copied === 'code'} onCopy={() => copyField('code', v.code)} />
      {v.pin && (
        <Box mt="8px">
          <CodeRow label="PIN" value={v.pin} copied={copied === 'pin'} onCopy={() => copyField('pin', v.pin)} />
        </Box>
      )}
      {v.valid_till && (
        <Text fontSize="12px" opacity={0.6} mt="8px">
          Valid till {String(v.valid_till).slice(0, 10)}
        </Text>
      )}
      {!v.in_store && link && (
        <Button
          as="a"
          href={link}
          target="_blank"
          rel="noopener"
          onClick={() => copyField('code', v.code)}
          mt="12px"
          w="100%"
          h="44px"
          borderRadius="pill"
          bg="onBrand"
          color="text"
          fontWeight={800}
          rightIcon={<I.external size={14} />}
          _hover={{ bg: 'onBrand' }}
        >
          Open {v.brand}
        </Button>
      )}
    </Box>
  );
}

const shortDate = (iso) => new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

// Total saved + every purchase, from Dealo's server (any device). Codes are
// not part of it: those stay on the phone they were bought on.
function Savings({ account }) {
  if (account.status === 'loading') {
    return (
      <Text fontSize="13px" color="text2" mb="18px">
        Loading…
      </Text>
    );
  }
  if (account.status === 'error') {
    return (
      <Text fontSize="13px" color="text2" mb="18px">
        Couldn’t load your savings right now. Please try again in a bit.
      </Text>
    );
  }
  if (account.status !== 'ready') return null;
  const { total_saved: saved, total_bought: bought, purchases } = account.data;
  return (
    <Box mb="20px">
      <Box borderRadius="18px" bg="surface2" border="1px solid" borderColor="border" p="16px" textAlign="center">
        <Text fontSize="13px" color="text2" fontWeight={700}>
          You’ve saved
        </Text>
        <Text fontFamily="mono" fontSize="34px" fontWeight={800} color="green" lineHeight="1.15">
          {fmt(saved)}
        </Text>
        <Text fontSize="13px" color="text2">
          {purchases.length} {purchases.length === 1 ? 'voucher' : 'vouchers'} · {fmt(bought)} bought
        </Text>
      </Box>
      {purchases.length > 0 && (
        <Flex direction="column" mt="10px">
          {purchases.map((p, i) => (
            <Flex key={`${p.at}-${i}`} justify="space-between" align="center" py="10px" borderBottom="1px solid" borderColor="border" gap="10px">
              <Box minW={0}>
                <Text fontWeight={700} fontSize="15px">
                  {p.brand}
                </Text>
                <Text fontSize="12px" color="text3">
                  {shortDate(p.at)}
                </Text>
              </Box>
              <Box textAlign="right" flexShrink={0}>
                <Text fontFamily="mono" fontWeight={700} fontSize="15px">
                  {fmt(p.amount)}
                </Text>
                <Text fontFamily="mono" fontSize="12px" color="green">
                  saved {fmt(p.saved)}
                </Text>
              </Box>
            </Flex>
          ))}
        </Flex>
      )}
    </Box>
  );
}

const label = (text) => (
  <Text fontSize="13px" fontWeight={700} color="text2" mb="6px">
    {text}
  </Text>
);

/**
 * Logged out: name, mobile, optional email → SMS code. The same phone login
 * as the buy flow, so someone who bought on another phone sees those
 * purchases here as soon as the code goes in.
 */
function LoginForm({ onDone }) {
  const [step, setStep] = useState('details');
  const [name, setName] = useState(readBuyerName);
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const confirmation = useRef(null);
  const phoneOk = /^[6-9]\d{9}$/.test(phone);
  const emailOk = !email.trim() || /^\S+@\S+\.\S+$/.test(email.trim());

  const getCode = async () => {
    setError('');
    setBusy(true);
    try {
      confirmation.current = await sendCode(phone, 'dealo-account-code');
      track('Login Code Sent', { placement: 'account' });
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
    let token;
    try {
      token = await confirmCode(confirmation.current, digits);
    } catch {
      setError('That code didn’t match. Try again.');
      setCode('');
      setBusy(false);
      return;
    }
    saveBuyerName(name.trim());
    setSignedIn(true);
    track('Logged In', { placement: 'account' });
    // Saving the name is a nicety: the login works even if this fails.
    await hubbleApi.account({ id_token: token, name: name.trim(), email: email.trim() || null }).catch(() => {});
    onDone();
  };

  if (step === 'code') {
    return (
      <Flex direction="column" gap="14px" mb="20px">
        <Flex justify="space-between" align="center">
          <Text fontFamily="mono" fontSize="13px" color="text2">
            Code sent by SMS to +91 {phone}
          </Text>
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
            Logging in…
          </Text>
        )}
      </Flex>
    );
  }

  return (
    <Flex direction="column" gap="14px" mb="20px">
      <Text fontSize="14px" color="text2">
        Log in or sign up to see every voucher you’ve bought, on any phone.
      </Text>
      <Box as="label">
        {label('Your name')}
        <Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" h="54px" borderRadius="14px" fontSize="17px" fontWeight={600} />
      </Box>
      <Box as="label">
        {label('Mobile number')}
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
      <Box as="label">
        {label('Email (optional)')}
        <Input
          type="email"
          inputMode="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          h="54px"
          borderRadius="14px"
          fontSize="17px"
          fontWeight={600}
          isInvalid={!emailOk}
        />
      </Box>
      {error && (
        <Text fontSize="13px" color="danger" fontWeight={600}>
          {error}
        </Text>
      )}
      <Button
        id="dealo-account-code"
        onClick={getCode}
        isDisabled={!name.trim() || !phoneOk || !emailOk}
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
        Only for your login · <a href="/privacy">Privacy</a>
      </Text>
    </Flex>
  );
}

/**
 * "Your account": total saved and every purchase (from the server, any
 * device), plus the codes bought on this phone (kept only here). Opened from
 * the top bar or the menu. Mounted once in AppLayout.
 *
 * Also catches the buyer who paid and left before the code showed (an app
 * link from Hubble's screen took the whole page away): on the next page
 * load, within 30 minutes, it fetches the code and opens itself.
 */
export default function MyVouchers() {
  const vouchers = useSavedVouchers();
  const open = useVouchersOpen();
  // Removing is the only copy going away, so it takes a second tap.
  const [removing, setRemoving] = useState(null);
  // { status: 'loading' | 'ready' | 'error' | 'out', data?, phone? }
  const [account, setAccount] = useState({ status: 'loading' });

  useEffect(() => {
    const pending = pendingPurchase();
    if (!pending) return undefined;
    let tries = 0;
    let timer;
    let live = true;
    const poll = async () => {
      const token = await idToken().catch(() => null);
      if (!live) return;
      if (!token) return;
      const res = await hubbleApi.latestOrder(token).catch(() => null);
      if (!live) return;
      if (res?.found) {
        saveOrder(res, pending);
        track('Voucher Recovered After Reload', { brand: res.brand });
        setVouchersOpen(true);
      } else if (++tries < 10) timer = setTimeout(poll, 3000);
      else clearPending();
    };
    poll();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, []);

  // Fresh numbers every time the sheet opens (a purchase may have just
  // landed), and again right after logging in here.
  const [loads, setLoads] = useState(0);
  useEffect(() => {
    if (!open) return undefined;
    let live = true;
    setAccount({ status: 'loading' });
    (async () => {
      const token = await idToken().catch(() => null);
      if (!live) return;
      if (!token) {
        setAccount({ status: 'out' });
        return;
      }
      try {
        const data = await hubbleApi.me(token);
        if (live) setAccount({ status: 'ready', data });
      } catch {
        if (live) setAccount({ status: 'error' });
      }
    })();
    return () => {
      live = false;
    };
  }, [open, loads]);

  if (!open) return null;
  const close = () => {
    setRemoving(null);
    setVouchersOpen(false);
  };
  const logOut = async () => {
    track('Logged Out');
    await signOut().catch(() => {});
    saveBuyerName('');
    setSignedIn(false);
    setAccount({ status: 'out' });
  };
  const phone = account.data?.phone;

  return (
    <Box position="fixed" inset={0} zIndex={1500} bg="rgba(22,32,43,.55)" onClick={close}>
      <Box
        position="absolute"
        left={0}
        right={0}
        bottom={0}
        mx="auto"
        maxW="480px"
        maxH="88dvh"
        overflowY="auto"
        bg="surface"
        borderTopRadius="24px"
        p="20px 16px 28px"
        onClick={(e) => e.stopPropagation()}
      >
        <Flex justify="space-between" align="center" mb="14px">
          <Text fontSize="20px" fontWeight={800}>
            Your account
          </Text>
          <Button aria-label="Close" variant="ghost" size="sm" onClick={close}>
            <I.x size={18} />
          </Button>
        </Flex>

        {account.status === 'out' ? <LoginForm onDone={() => setLoads((n) => n + 1)} /> : <Savings account={account} />}

        {/* Logged out with nothing saved here: the login is all there is. */}
        {(account.status !== 'out' || vouchers.length > 0) && (
          <Text fontSize="13px" fontWeight={800} color="text2" letterSpacing=".04em" mb="10px">
            CODES ON THIS PHONE
          </Text>
        )}
        {account.status === 'out' && vouchers.length === 0 ? null : vouchers.length === 0 ? (
          <Text fontSize="14px" color="text2">
            Codes you buy on this phone show up here.
          </Text>
        ) : (
          <Flex direction="column" gap="12px">
            {vouchers.map((v) => (
              <Box key={v.code}>
                <VoucherCard v={v} />
                <Button
                  variant="link"
                  size="xs"
                  mt="6px"
                  color={removing === v.code ? 'danger' : 'text3'}
                  onClick={() => {
                    if (removing !== v.code) {
                      setRemoving(v.code);
                      return;
                    }
                    track('Voucher Removed', { brand: v.brand });
                    forgetVoucher(v.code);
                    setRemoving(null);
                  }}
                >
                  {removing === v.code ? 'Tap again to remove this code for good' : 'Used it? Remove'}
                </Button>
              </Box>
            ))}
          </Flex>
        )}

        {(account.status === 'ready' || account.status === 'error') && (
          <Flex justify="center" align="center" gap="6px" mt="22px" fontSize="12px" color="text3">
            {phone && <Text>Logged in as {phone}</Text>}
            {phone && <Text>·</Text>}
            <Box as="button" type="button" textDecoration="underline" onClick={logOut}>
              Log out
            </Box>
          </Flex>
        )}
      </Box>
    </Box>
  );
}
