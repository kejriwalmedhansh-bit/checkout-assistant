import { useState } from 'react';
import { Box, Flex, Grid, Text } from '@chakra-ui/react';

import BrandVoucherCard from '@/components/dashboard/BrandVoucherCard';
import { voucherTypeIcon } from '@/components/dashboard/voucherTypeIcons';
import { I } from '@/components/common/icons';
import { shopLogos } from '@/utils/priceList';
import { track } from '@/utils/analytics';

// "MakeMyTrip" from "MakeMyTrip Hotel e-Pay", "MakeMyTrip Cab"... — the first
// word every card name shares, spelled as in the shortest name. Same rule as
// the WhatsApp bot's _shop_name.
function shopName(choices) {
  const firsts = choices.map((c) => (c.brand_name || '').trim().split(/[\s-]+/)[0]);
  if (firsts[0] && new Set(firsts.map((f) => f.toLowerCase())).size === 1) {
    const shortest = choices.reduce((a, c, i) => ((c.brand_name || '').length < (choices[a].brand_name || '').length ? i : a), 0);
    return firsts[shortest];
  }
  return choices[0].brand_name || '';
}

const pct = (c) => (c.best_discount_pct != null ? `${+Number(c.best_discount_pct).toFixed(2)}% off` : null);

/** The shop's logo, shown once beside the question: Brandfetch, then the
 * site's favicon (same sources as the price list); a plain shop icon if both
 * fail — never a letter tile. */
function ShopLogo({ website, name }) {
  const sources = website ? shopLogos(`https://${website}`) : [];
  const [tries, setTries] = useState(0);
  const src = sources[tries];
  return (
    <Flex w="48px" h="48px" flexShrink={0} borderRadius="12px" bg="white" border="1px solid" borderColor="border" align="center" justify="center" overflow="hidden" color="text3">
      {src ? (
        <Box as="img" src={src} alt={`${name} logo`} decoding="async" w={tries === 0 ? '100%' : '28px'} h={tries === 0 ? '100%' : '28px'} objectFit={tries === 0 ? 'cover' : 'contain'} onError={() => setTries((t) => t + 1)} />
      ) : (
        <I.store size={22} />
      )}
    </Flex>
  );
}

function TypeIcon({ label }) {
  const Icon = voucherTypeIcon(label);
  return (
    <Flex w="40px" h="40px" flexShrink={0} borderRadius="10px" bg="brandSoft" color="brand" align="center" justify="center">
      <Icon size={22} />
    </Flex>
  );
}

function RateBadge({ text, bg = 'brandSoft' }) {
  if (!text) return null;
  return (
    <Text as="span" fontFamily="mono" fontSize="13px" fontWeight={600} color="brand" bg={bg} borderRadius="6px" px="7px" py="3px" whiteSpace="nowrap">
      {text}
    </Text>
  );
}

/**
 * Shops like MakeMyTrip sell a different voucher for hotels, cabs, flights…
 * The shopper says what they're buying before any voucher is shown, the same
 * question the extension asks — nothing is pre-picked, so nobody booking a
 * flight lands on the hotels-only card by default. Choices come best rate
 * first from POST /search (`voucher_choices`).
 *
 * Owner's design, 2026-11-12: the shop's logo once beside the question, then
 * one card per voucher with a picture of what it buys. Tapping a card folds
 * the rest away into that one card as a slim closed box, with the voucher
 * underneath; tapping the box opens every choice again.
 */
export default function VoucherChoicePicker({ choices, query }) {
  const [picked, setPicked] = useState(null);
  const shop = shopName(choices);
  const website = choices.find((c) => c.shop_website)?.shop_website || null;

  const pick = (i) => {
    setPicked(i);
    track('Voucher Type Picked', { query, choice: choices[i].choice_label, brand: choices[i].brand_name });
  };

  const chosen = picked != null ? choices[picked] : null;

  return (
    <Flex direction="column" gap="14px">
      <Flex align="center" gap="12px" bg="surface" border="1px solid" borderColor="border" borderRadius="14px" p="12px">
        <ShopLogo website={website} name={shop} />
        <Box minW={0}>
          <Text fontSize="16px" fontWeight={800} color="text">What are you buying?</Text>
          <Text fontSize="13px" color="text2" mt="2px">{shop} has a different voucher for each</Text>
        </Box>
      </Flex>

      {chosen ? (
        <Flex
          as="button"
          type="button"
          onClick={() => setPicked(null)}
          aria-expanded={false}
          aria-label={`${chosen.choice_label} picked. Show all ${choices.length} ${shop} vouchers`}
          align="center"
          gap="12px"
          w="100%"
          minH="60px"
          px="14px"
          py="10px"
          textAlign="left"
          bg="brandSoft"
          border="2px solid"
          borderColor="brand"
          borderRadius="14px"
          cursor="pointer"
          _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
        >
          <TypeIcon label={chosen.choice_label} />
          <Text flex="1" minW={0} fontSize="15px" fontWeight={700} color="text">{chosen.choice_label}</Text>
          <RateBadge text={pct(chosen)} bg="surface" />
          <I.chevDown size={18} color="text2" />
        </Flex>
      ) : (
        <Grid templateColumns="repeat(2, minmax(0, 1fr))" gap="10px" role="group" aria-label={`${shop} voucher types`}>
          {choices.map((c, i) => (
            <Flex
              as="button"
              type="button"
              key={`${c.brand_name}-${c.voucher_source}`}
              onClick={() => pick(i)}
              direction="column"
              align="stretch"
              gap="10px"
              minH="128px"
              p="14px"
              textAlign="left"
              bg="surface"
              border="2px solid"
              borderColor="border"
              borderRadius="14px"
              cursor="pointer"
              transition="border-color .15s"
              _hover={{ borderColor: 'brand' }}
              _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
            >
              <Flex justify="space-between" align="flex-start" gap="8px">
                <TypeIcon label={c.choice_label} />
                <RateBadge text={pct(c)} />
              </Flex>
              <Text fontSize="15px" fontWeight={700} lineHeight="1.2" color="text">{c.choice_label}</Text>
              {c.covers && (
                <Text fontSize="12.5px" lineHeight="1.35" color="text2">{c.covers}</Text>
              )}
            </Flex>
          ))}
        </Grid>
      )}

      {chosen && <BrandVoucherCard key={picked} voucher={chosen} query={query} />}
    </Flex>
  );
}
