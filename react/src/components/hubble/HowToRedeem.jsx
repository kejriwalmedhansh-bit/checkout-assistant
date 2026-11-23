import { useEffect, useState } from 'react';
import { Box, Button, Flex, Portal, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import { hubbleApi } from '@/api/hubble.api';
import { track } from '@/utils/analytics';

/**
 * "How to redeem": a button that opens the shop's own steps, word for word
 * from Hubble (hubble_service.card_details -> card.ways / card.steps),
 * numbered, with the words to look for at checkout highlighted.
 *
 * Shown on every Dealo voucher: the card before buying (L1 journey + L2 shop
 * card), the "Voucher ready" screen, and Your account. Owner call 23 Nov 2026:
 * the shop's own words explain it better than icons. Started from a buyer who
 * typed his Domino's code in the right box at 1am and still got stuck.
 *
 * Pass `card` when the caller has it; otherwise pass `brandName` and the
 * steps are fetched when the button is tapped (Your account only knows the
 * brand name).
 */

const LABEL = { online: 'Online', store: 'In store' };

// The one step to look at hardest: where the voucher goes at checkout, else
// where the code is typed, else (in a shop) the cashier.
const KEY = [
  /(gift ?card ?\/ ?e-?voucher|e-?gift ?cards?|gift ?cards?|e-?vouchers?|gift vouchers?|\begv\b|e-?pay|prepaid code|voucher (?:tab|option|section|field))/i,
  /(16[- ]digit[^,.]*|card number[^,.]*pin|\bcode\b|\bpin\b)/i,
  /(cashier|cash desk|counter|manager)/i,
];

const tidy = (t) =>
  String(t)
    .replace(/https?:\/\/(?:www\.)?([^/\s]+)\S*/g, '$1')
    .replace(/\bwww\./g, '')
    .replace(/^\s*[-•]\s*/, '')
    .trim();

function redeemSteps(raw) {
  const list = (raw || []).map(tidy).filter((t) => t && !/^terms\s*(?:&|and)\s*conditions apply\.?$/i.test(t));
  for (const re of KEY) {
    const at = list.findIndex((t) => re.test(t));
    if (at >= 0) return list.map((text, i) => ({ text, mark: i === at ? re : null }));
  }
  return list.map((text) => ({ text, mark: null }));
}

function Marked({ text, re }) {
  const m = re && text.match(re);
  if (!m) return text;
  const at = m.index;
  return (
    <>
      {text.slice(0, at)}
      <Box as="mark" bg="amberSoft" color="text" fontWeight={800} borderRadius="4px" px="3px">
        {m[0]}
      </Box>
      {text.slice(at + m[0].length)}
    </>
  );
}

// { online: [...], store: [...] } from a card, keeping only ways with steps.
function waysOf(card, inStore) {
  const ways = { ...(card?.ways || {}) };
  if (!Object.keys(ways).length && card?.steps?.length) ways[inStore ? 'store' : 'online'] = card.steps;
  return Object.fromEntries(Object.entries(ways).filter(([, v]) => v?.length));
}

function Sheet({ brandName, ways, start, onClose }) {
  const modes = ['online', 'store'].filter((m) => ways[m]);
  const [mode, setMode] = useState(modes.includes(start) ? start : modes[0]);
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const steps = redeemSteps(ways[mode]);
  return (
    <Portal>
      <Box position="fixed" inset={0} zIndex={1700} bg="rgba(22,32,43,.45)" onClick={onClose}>
        <Box
          role="dialog"
          aria-label={`How to redeem ${brandName}`}
          position="absolute"
          left={0}
          right={0}
          bottom={0}
          maxW="520px"
          mx="auto"
          maxH="82vh"
          overflowY="auto"
          bg="surface"
          color="text"
          borderTopRadius="22px"
          px="16px"
          pt="10px"
          pb="calc(18px + env(safe-area-inset-bottom, 0px))"
          textAlign="left"
          onClick={(e) => e.stopPropagation()}
        >
          <Box w="36px" h="4px" borderRadius="2px" bg="surface3" mx="auto" mb="12px" />
          <Flex justify="space-between" align="center" mb="12px" gap="10px">
            <Text fontSize="17px" fontWeight={800} minW={0}>
              How to redeem {brandName}
            </Text>
            <Button size="sm" w="30px" h="30px" minW="30px" p={0} borderRadius="50%" bg="surface3" onClick={onClose} aria-label="Close">
              <I.x size={14} />
            </Button>
          </Flex>
          {modes.length > 1 && (
            <Flex gap="6px" mb="14px">
              {modes.map((m) => (
                <Button
                  key={m}
                  size="sm"
                  h="32px"
                  borderRadius="pill"
                  border="1.5px solid"
                  borderColor={m === mode ? 'text' : 'border'}
                  bg={m === mode ? 'text' : 'surface2'}
                  color={m === mode ? 'onBrand' : 'text2'}
                  fontWeight={700}
                  aria-pressed={m === mode}
                  onClick={() => setMode(m)}
                  _hover={{}}
                >
                  {LABEL[m]}
                </Button>
              ))}
            </Flex>
          )}
          <Box as="ol" listStyleType="none" m={0} p={0} display="flex" flexDirection="column" gap="10px">
            {steps.map((s, i) => (
              <Flex as="li" key={`${i}-${s.text}`} gap="10px" align="flex-start">
                <Flex
                  w="24px"
                  h="24px"
                  flex="0 0 auto"
                  borderRadius="50%"
                  bg={s.mark ? 'amber' : 'surface3'}
                  color={s.mark ? 'white' : 'text'}
                  fontSize="12px"
                  fontWeight={800}
                  align="center"
                  justify="center"
                >
                  {i + 1}
                </Flex>
                <Text fontSize="14.5px" lineHeight={1.45} minW={0} overflowWrap="anywhere" pt="1px">
                  <Marked text={s.text} re={s.mark} />
                </Text>
              </Flex>
            ))}
          </Box>
          <Text fontSize="11.5px" color="text3" mt="14px">
            Word for word from {brandName}.
          </Text>
          <Button onClick={onClose} w="100%" h="48px" mt="12px" borderRadius="pill" bg="text" color="onBrand" fontWeight={800} _hover={{ bg: 'text' }}>
            Got it
          </Button>
        </Box>
      </Box>
    </Portal>
  );
}

/**
 * look: 'row' (a full-width row inside a box), 'pill' (a button on its own),
 * 'onDark' (inside the dark code card), 'link' (small text link).
 */
export default function HowToRedeem({ card, brandName, inStore = false, placement, look = 'pill' }) {
  const [open, setOpen] = useState(false);
  const [fetched, setFetched] = useState(null); // ways fetched by brand name
  const [state, setState] = useState('idle'); // idle | loading | none
  const given = waysOf(card, inStore);
  const ways = Object.keys(given).length ? given : fetched;

  // With a card in hand and no steps in it, there is nothing to show.
  if (card && !Object.keys(given).length) return null;
  if (!card && !brandName) return null;

  const tap = async () => {
    track('How To Redeem Opened', { brand: brandName, placement });
    if (ways) return setOpen(true);
    setState('loading');
    try {
      const res = await hubbleApi.brand(brandName, null, { inStore });
      const w = waysOf(res?.brand?.card, inStore);
      if (Object.keys(w).length) {
        setFetched(w);
        setState('idle');
        setOpen(true);
      } else setState('none');
    } catch {
      setState('none');
    }
  };

  const label = state === 'loading' ? 'Loading…' : 'How to redeem';
  const looks = {
    row: { w: '100%', minH: '44px', px: '14px', justify: 'space-between', bg: 'surface', color: 'brand', fontSize: '13px', borderTop: '1px solid', borderColor: 'border', _hover: { bg: 'brandSoft2' } },
    pill: { w: '100%', h: '48px', justify: 'center', gap: '8px', borderRadius: 'pill', border: '1.5px solid', borderColor: 'border', bg: 'surface', color: 'text', fontSize: '15px' },
    onDark: { w: '100%', h: '40px', mt: '10px', justify: 'center', gap: '6px', borderRadius: 'pill', border: '1px solid', borderColor: 'whiteAlpha.400', bg: 'transparent', color: 'onBrand', fontSize: '13.5px' },
    link: { color: 'brand', fontSize: '12px', textDecoration: 'underline', gap: '4px' },
  };

  return (
    <>
      <Flex
        as="button"
        type="button"
        onClick={tap}
        align="center"
        fontWeight={700}
        textAlign="left"
        _focusVisible={{ outline: '2px solid', outlineColor: 'brass', outlineOffset: '2px' }}
        {...looks[look]}
      >
        {look === 'pill' && <I.ticket size={16} />}
        {label}
        {look === 'row' && <I.chevRight size={16} />}
      </Flex>
      {state === 'none' && (
        <Text fontSize="12px" color={look === 'onDark' ? 'onBrand' : 'text2'} opacity={look === 'onDark' ? 0.7 : 1} mt="4px">
          Steps not available right now. Use the code at {brandName} checkout.
        </Text>
      )}
      {open && ways && <Sheet brandName={brandName} ways={ways} start={inStore ? 'store' : 'online'} onClose={() => setOpen(false)} />}
    </>
  );
}
