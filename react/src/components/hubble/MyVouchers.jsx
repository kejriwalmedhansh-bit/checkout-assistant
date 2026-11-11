import { useEffect, useRef, useState } from 'react';
import { Box, Button, Flex, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { hubbleApi } from '@/api/hubble.api';
import { idToken } from '@/lib/firebase';
import {
  clearPending,
  forgetVoucher,
  pendingPurchase,
  saveOrder,
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

/**
 * "Your vouchers": every code bought through Dealo on this phone, reopened
 * from the top bar or the menu. Mounted once in AppLayout.
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

  if (!open) return null;
  const close = () => {
    setRemoving(null);
    setVouchersOpen(false);
  };

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
            Your vouchers
          </Text>
          <Button aria-label="Close" variant="ghost" size="sm" onClick={close}>
            <I.x size={18} />
          </Button>
        </Flex>
        {vouchers.length === 0 ? (
          <Text fontSize="14px" color="text2">
            Vouchers you buy on Dealo show up here.
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
        <Text fontSize="12px" color="text3" mt="16px" textAlign="center">
          Saved on this phone only.
        </Text>
      </Box>
    </Box>
  );
}
