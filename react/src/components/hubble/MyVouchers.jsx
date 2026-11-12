import { useEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Portal, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { hubbleApi } from '@/api/hubble.api';
import { idToken, signOut } from '@/lib/firebase';
import {
  clearPending,
  forgetVoucher,
  pendingPurchase,
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
import PhoneLogin from './PhoneLogin';

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
// never on Dealo's server: "Show code" opens the card on Hubble's own page,
// which works on any phone or laptop the shopper logs in on.
function Savings({ account, onShowCode }) {
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
              <Flex align="center" gap="12px" flexShrink={0}>
                <Box textAlign="right">
                  <Text fontFamily="mono" fontWeight={700} fontSize="15px">
                    {fmt(p.amount)}
                  </Text>
                  <Text fontFamily="mono" fontSize="12px" color="green">
                    saved {fmt(p.saved)}
                  </Text>
                </Box>
                <Button size="sm" h="36px" borderRadius="pill" variant="outline" fontWeight={800} onClick={() => onShowCode(p.ref || null, p.brand)}>
                  Show code
                </Button>
              </Flex>
            </Flex>
          ))}
        </Flex>
      )}
    </Box>
  );
}

// Hubble's own page for a gift card the shopper bought (card number, PIN,
// Redeem), inside Dealo like the payment screen. Hubble's back arrow and
// Dealo's ✕ both close it.
function HubbleCard({ url, onClose }) {
  useEffect(() => {
    const onMessage = (e) => {
      let host = '';
      try {
        host = new URL(e.origin).hostname;
      } catch {
        return;
      }
      if (!/myhubble\.money$/.test(host)) return;
      let msg = e.data;
      if (typeof msg === 'string') {
        try {
          msg = JSON.parse(msg);
        } catch {
          return;
        }
      }
      const kind = msg?.event || msg?.action || msg?.type;
      // "Redeem now" asks the host to open the shop's site or app.
      if (kind === 'launch_link') openLink(msg.properties?.link);
      if (kind === 'close') onClose();
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [onClose]);
  return (
    <Portal>
      <Box position="fixed" inset={0} zIndex={1600} bg="rgba(22,32,43,.6)">
        <Flex direction="column" position="absolute" top="24px" left={0} right={0} bottom={0} mx="auto" maxW="480px" bg="surface" borderTopRadius="24px" overflow="hidden">
          <Flex h="52px" align="center" justify="space-between" px="14px" borderBottom="1px solid" borderColor="border">
            <Text fontSize="13px" fontWeight={700} color="text2">
              Your gift card · Hubble
            </Text>
            <Button aria-label="Close" variant="ghost" size="sm" onClick={onClose}>
              <I.x size={18} />
            </Button>
          </Flex>
          <Box as="iframe" title="Your gift card" src={url} allow="clipboard-write" flex="1" w="100%" border={0} />
        </Flex>
      </Box>
    </Portal>
  );
}

const openLink = (link) => {
  if (typeof link !== 'string' || !link || /^(javascript|data):/i.test(link)) return;
  if (/^https?:/i.test(link)) window.open(link, '_blank', 'noopener');
  else window.location.href = link;
};

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
  // Hubble's page for one card (or all of them) while it's open.
  const [cardUrl, setCardUrl] = useState(null);
  const [cardError, setCardError] = useState('');

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
  const showCode = async (ref, brand) => {
    setCardError('');
    track('Code Opened On Hubble', { brand: brand || null, all: !ref });
    try {
      const token = await idToken();
      const { url } = await hubbleApi.card(token, ref);
      setCardUrl(url);
    } catch {
      setCardError('Couldn’t open your code right now. Please try again.');
    }
  };
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
            {account.status === 'out' ? 'Log in or sign up' : 'Your account'}
          </Text>
          <Button aria-label="Close" variant="ghost" size="sm" onClick={close}>
            <I.x size={18} />
          </Button>
        </Flex>

        {account.status === 'out' ? (
          <Box mb="20px">
            <PhoneLogin
              place="account"
              intro={
                <Text fontSize="14px" color="text2">
                  See every voucher you’ve bought, with its code, on any phone.
                </Text>
              }
              onDone={() => setLoads((n) => n + 1)}
            />
          </Box>
        ) : (
          <Savings account={account} onShowCode={showCode} />
        )}
        {cardError && (
          <Text fontSize="13px" color="danger" fontWeight={600} mb="14px">
            {cardError}
          </Text>
        )}
        {cardUrl && <HubbleCard url={cardUrl} onClose={() => setCardUrl(null)} />}

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
