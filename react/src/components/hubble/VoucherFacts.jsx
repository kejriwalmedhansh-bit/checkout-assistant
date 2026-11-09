import { Box, Button, Flex, Grid, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';

import { I } from '@/components/common/icons';
import { track } from '@/utils/analytics';

/**
 * What a Dealo (Hubble) voucher is good for, before the shopper pays: four
 * icons with two words each, and one tappable box for what it can't pay for
 * (or "Good to know" when nothing is hand-picked for that shop). The box
 * opens a sheet with those items as pictures, and the shop's full terms
 * folded away. Everything comes from Hubble's own terms via the server
 * (hubble_service.card_details). Designed in rounds 1–4, 9 Nov 2026.
 */

const PATHS = {
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
  store: <><path d="M3 9l1.5-5h15L21 9" /><path d="M4 9v11h16V9" /><path d="M3 9h18" /><path d="M10 20v-6h4v6" /></>,
  repeat: <><path d="M17 2l3 3-3 3" /><path d="M4 11V9a4 4 0 0 1 4-4h12" /><path d="M7 22l-3-3 3-3" /><path d="M20 13v2a4 4 0 0 1-4 4H4" /></>,
  tag: <><path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z" /><circle cx="7.5" cy="7.5" r="1.5" /></>,
  cal: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
  undo: <><path d="M9 14L4 9l5-5" /><path d="M4 9h11a5 5 0 0 1 0 10h-3" /></>,
  ring: <><circle cx="12" cy="15" r="6" /><path d="M9 5l3-3 3 3-3 4z" /></>,
  coins: <><ellipse cx="9" cy="7" rx="6" ry="3" /><path d="M3 7v4c0 1.7 2.7 3 6 3s6-1.3 6-3V7" /><path d="M9 14v3c0 1.7 2.7 3 6 3s6-1.3 6-3v-4c0-1.7-2.7-3-6-3" /></>,
  cash: <><rect x="2" y="6" width="20" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /></>,
  plane: <path d="M10.5 13.5L3 11l1-2 8 1 5-5c1-1 3-1.5 3.5-1S20 6 19 7l-5 5 1 8-2 1-2.5-7.5L7 17v3l-1.5 1L4 17.5 1 16l1-1.5h3z" />,
  bus: <><rect x="4" y="3" width="16" height="15" rx="2" /><path d="M4 11h16M8 21v-3M16 21v-3" /><circle cx="8" cy="14.5" r=".8" /><circle cx="16" cy="14.5" r=".8" /></>,
  home: <><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /></>,
  truck: <><path d="M1 6h13v10H1zM14 10h4l3 3v3h-7" /><circle cx="5.5" cy="18" r="2" /><circle cx="17.5" cy="18" r="2" /></>,
  gift: <><rect x="3" y="8" width="18" height="13" rx="1" /><path d="M3 12h18M12 8v13" /><path d="M12 8S10 3 7.5 4.5 9 8 12 8zM12 8s2-5 4.5-3.5S15 8 12 8z" /></>,
  receipt: <><path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2z" /><path d="M9 8h6M9 12h6" /></>,
  film: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4" /></>,
  phone: <><rect x="6" y="2" width="12" height="20" rx="2" /><path d="M11 18h2" /></>,
  pill: <><rect x="2" y="8" width="20" height="8" rx="4" transform="rotate(-35 12 12)" /><path d="M9 8.5l6 7" /></>,
  check: <path d="M5 12l5 5L20 7" />,
};

function Glyph({ name, size = 18, stroke = 2.1 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name] || PATHS.check}
    </svg>
  );
}

const TONE = {
  yes: { bg: 'greenSoft', color: 'green', text: 'text' },
  no: { bg: 'dangerSoft', color: 'danger', text: 'danger' },
  info: { bg: 'surface3', color: 'text', text: 'text' },
};

function Sheet({ card, brandName, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const cant = card.cant || [];
  return (
    <Box position="fixed" inset={0} zIndex={1400} bg="rgba(22,32,43,.45)" onClick={onClose}>
      <Box
        role="dialog"
        aria-label={`${brandName} voucher`}
        position="absolute"
        left={0}
        right={0}
        bottom={0}
        maxW="520px"
        mx="auto"
        maxH="82vh"
        overflowY="auto"
        bg="surface"
        borderTopRadius="22px"
        px="16px"
        pt="10px"
        pb="calc(18px + env(safe-area-inset-bottom, 0px))"
        onClick={(e) => e.stopPropagation()}
      >
        <Box w="36px" h="4px" borderRadius="2px" bg="surface3" mx="auto" mb="12px" />
        <Flex justify="space-between" align="center" mb="12px">
          <Text fontSize="17px" fontWeight={800}>
            {cant.length ? 'Can’t pay for' : 'Good to know'}
          </Text>
          <Button size="sm" w="30px" h="30px" minW="30px" p={0} borderRadius="50%" bg="surface3" onClick={onClose} aria-label="Close">
            <I.x size={14} />
          </Button>
        </Flex>
        {cant.length > 0 && (
          <Grid templateColumns={`repeat(${Math.min(cant.length, 3)}, 1fr)`} gap="8px">
            {cant.map((c) => (
              <Flex key={c.label} direction="column" align="center" gap="7px" textAlign="center" py="12px" px="4px" borderRadius="14px" bg="dangerSoft">
                <Flex position="relative" w="42px" h="42px" borderRadius="50%" bg="surface" color="danger" align="center" justify="center">
                  <Glyph name={c.icon} size={20} />
                  <Box position="absolute" inset="6px" borderRadius="50%" bgGradient="linear(135deg, transparent 47%, danger 47%, danger 53%, transparent 53%)" />
                </Flex>
                <Text fontSize="12.5px" fontWeight={800} color="danger" lineHeight={1.2}>
                  {c.label}
                </Text>
              </Flex>
            ))}
          </Grid>
        )}
        {card.terms?.length > 0 && (
          <Box as="details" mt="14px" borderTop="1px solid" borderColor="border" pt="10px">
            <Box as="summary" fontSize="12.5px" fontWeight={700} color="text3" cursor="pointer" listStyleType="none">
              {brandName}’s full terms ›
            </Box>
            <Box as="ol" mt="8px" pl="18px" fontSize="12.5px" lineHeight={1.45} color="text2">
              {card.terms.map((t) => (
                <Box as="li" key={t} mt="4px">
                  {t}
                </Box>
              ))}
            </Box>
          </Box>
        )}
        <Button onClick={onClose} w="100%" h="48px" mt="16px" borderRadius="pill" bg="text" color="onBrand" fontWeight={800} _hover={{ bg: 'text' }}>
          Got it
        </Button>
      </Box>
    </Box>
  );
}

export default function VoucherFacts({ card, brandName, placement }) {
  const [open, setOpen] = useState(false);
  const facts = card?.facts || [];
  const cant = card?.cant || [];
  if (!facts.length) return null;
  const openSheet = () => {
    setOpen(true);
    track('Voucher Terms Opened', { brand: brandName, placement, cant_count: cant.length });
  };

  return (
    <Box>
      <Grid templateColumns={`repeat(${facts.length}, 1fr)`} gap="4px" py="12px" px="2px" borderTop="1px dashed" borderBottom="1px dashed" borderColor="border">
        {facts.map((f) => {
          const t = TONE[f.tone] || TONE.info;
          return (
            <Flex key={f.title} direction="column" align="center" textAlign="center" gap="6px" minW={0}>
              <Flex w="36px" h="36px" borderRadius="12px" bg={t.bg} color={t.color} align="center" justify="center">
                <Glyph name={f.icon} />
              </Flex>
              <Text fontSize="12px" fontWeight={700} lineHeight={1.2} color={t.text}>
                {f.title}
                <Text as="span" display="block" fontWeight={500} fontSize="11px" color="text3" mt="1px">
                  {f.sub}
                </Text>
              </Text>
            </Flex>
          );
        })}
      </Grid>

      <Flex
        as="button"
        type="button"
        onClick={openSheet}
        w="100%"
        mt="10px"
        px="12px"
        py="10px"
        align="center"
        gap="10px"
        borderRadius="12px"
        border="1.5px solid"
        borderColor={cant.length ? 'dangerLine' : 'border'}
        bg={cant.length ? 'dangerSoft' : 'surface2'}
        color={cant.length ? 'danger' : 'text'}
        textAlign="left"
        _focusVisible={{ outline: '2px solid', outlineColor: 'brass', outlineOffset: '2px' }}
      >
        <Flex w="26px" h="26px" borderRadius="50%" flex="0 0 auto" align="center" justify="center" bg={cant.length ? 'danger' : 'surface3'} color={cant.length ? 'white' : 'text'} fontFamily="mono" fontWeight={800} fontSize="13px">
          {cant.length ? cant.length : <Glyph name="check" size={13} stroke={3} />}
        </Flex>
        <Text flex="1" fontSize="13.5px" fontWeight={800}>
          {cant.length ? 'Things it can’t pay for' : 'Good to know'}
        </Text>
        <I.chevRight size={16} />
      </Flex>

      {open && <Sheet card={card} brandName={brandName} onClose={() => setOpen(false)} />}
    </Box>
  );
}

/**
 * After buying, when the shop has no direct "add voucher" link: Hubble's
 * steps one at a time with back / next, so the screen stays short.
 */
export function VoucherSteps({ steps }) {
  const [i, setI] = useState(0);
  if (!steps?.length) return null;
  const n = steps.length;
  return (
    <Box bg="surface" border="1px solid" borderColor="border" borderRadius="14px" p="12px" textAlign="left">
      <Flex justify="space-between" align="center" mb="8px">
        <Flex gap="4px">
          {steps.map((s, k) => (
            <Box key={s} w="6px" h="6px" borderRadius="50%" bg={k === i ? 'text' : 'surface3'} />
          ))}
        </Flex>
        <Text fontFamily="mono" fontWeight={700} fontSize="11px" color="text3">
          {i + 1} / {n}
        </Text>
      </Flex>
      <Text fontSize="14.5px" fontWeight={700} lineHeight={1.35} minH="58px" color="text">
        {steps[i]}
      </Text>
      <Flex gap="6px" mt="8px">
        <Button flex="1" h="36px" borderRadius="10px" border="1.5px solid" borderColor="border" bg="surface2" isDisabled={i === 0} onClick={() => setI(i - 1)} aria-label="Previous step">
          <I.arrowLeft size={16} />
        </Button>
        <Button flex="1" h="36px" borderRadius="10px" border="1.5px solid" borderColor="border" bg="surface2" isDisabled={i === n - 1} onClick={() => setI(i + 1)} aria-label="Next step">
          <I.arrowRight size={16} />
        </Button>
      </Flex>
    </Box>
  );
}
