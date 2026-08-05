import { useState } from 'react';
import { Box, Flex, Link, Text } from '@chakra-ui/react';

import { I } from '@/components/common/icons';
import TourRing from '@/components/onboarding/TourRing';
import { useTourHighlight } from '@/components/onboarding/useTourHighlight';

/** Tone → soft circle background + accent color (semantic tokens). */
const TONES = {
  brand: { bg: 'brandSoft', color: 'brand', border: 'brand' },
  voucher: { bg: 'amberSoft', color: 'amber', border: 'amber' },
  checkout: { bg: 'greenSoft', color: 'green', border: 'green' },
};

/**
 * Attention cue for an unfinished CTA: three chevrons fall toward the button
 * in sequence, and two rings expand outward from it below — same mechanic
 * on every row, colored to that row's own tone. Offset timings (chevrons
 * 1.6s, rings 2s + a 0.65s stagger between the two rings) so the two
 * motions don't lock into a mechanical-looking sync.
 */
function TapCue({ color }) {
  return (
    <Box position="absolute" top="-17px" left="50%" transform="translateX(-50%)" pointerEvents="none">
      {[0, 1, 2].map((i) => (
        <Box
          key={i}
          as="svg"
          viewBox="0 0 22 11"
          w="18px"
          h="9px"
          mt={i === 0 ? 0 : '-4px'}
          display="block"
          sx={{
            '@keyframes dealoChevronFall': {
              '0%': { opacity: 0, transform: 'translateY(-3px)' },
              '35%': { opacity: 1, transform: 'translateY(0)' },
              '65%': { opacity: 1, transform: 'translateY(2px)' },
              '100%': { opacity: 0, transform: 'translateY(6px)' },
            },
            animation: `dealoChevronFall 1.6s ease-in-out infinite`,
            animationDelay: `${i * 0.18}s`,
            '@media (prefers-reduced-motion: reduce)': { animation: 'none', opacity: 1 },
          }}
        >
          <path d="M2 2l9 7 9-7" fill="none" stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        </Box>
      ))}
    </Box>
  );
}

/**
 * Grows as a fixed-pixel box-shadow ring rather than a scaled-up box —
 * scaling the whole element worked when the button was a small pill, but on
 * the new full-width button a 1.45x scale of a ~550px-wide box overflowed
 * ~120px past the card's edge. A box-shadow spread expands by the same
 * absolute amount regardless of how wide the button is.
 */
function PingRings({ color }) {
  return (
    <>
      {[0, 1].map((i) => (
        <Box
          key={i}
          position="absolute"
          inset="0"
          borderRadius="99px"
          pointerEvents="none"
          sx={{
            '@keyframes dealoPing': {
              '0%': { boxShadow: `0 0 0 0px ${color}`, opacity: 0.7 },
              '100%': { boxShadow: `0 0 0 10px ${color}`, opacity: 0 },
            },
            animation: `dealoPing 2s cubic-bezier(0,.5,.5,1) infinite`,
            animationDelay: i === 1 ? '0.65s' : '0s',
            '@media (prefers-reduced-motion: reduce)': { animation: 'none', display: 'none' },
          }}
        />
      ))}
    </>
  );
}

function CheckIcon(props) {
  return (
    <Box
      as="svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      w="14px"
      h="14px"
      {...props}
    >
      <path d="M5 13l4 4L19 7" />
    </Box>
  );
}

/**
 * Vertical connector between two rows, aligned under the icon dots. Colors
 * in once the row above is done — a real, growing green line rather than a
 * neutral divider — so the checklist reads as one path being walked rather
 * than three independent rows. A small "then" chevron always shows on the
 * line (not just once done) — a static divider reads as a boundary between
 * unrelated facts; the chevron is what makes it read as a sequence you're
 * meant to walk through in order.
 */
export function JourneyConnector({ done = false }) {
  return (
    <Flex align="center" gap="14px">
      <Flex w="34px" flex="0 0 34px" direction="column" align="center" gap="1px">
        <Box w="2px" h="10px" bg={done ? 'brand' : 'borderStrong'} transition="background .3s" />
        <Box
          as="svg"
          viewBox="0 0 12 7"
          w="10px"
          h="6px"
          color={done ? 'brand' : 'text3'}
          opacity={done ? 1 : 0.7}
          transition="color .3s"
        >
          <path d="M1 1l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </Box>
        <Box w="2px" h="10px" bg={done ? 'brand' : 'borderStrong'} transition="background .3s" />
      </Flex>
      <Box flex="1" />
    </Flex>
  );
}

/**
 * One step, rendered as its own self-contained card — always the only thing
 * on screen inside JourneyPanels' one-at-a-time viewport, so it doesn't need
 * to compete visually with neighboring steps (that's what the "quiet
 * unselected row" dimming used to do; it no longer applies here since there
 * are no visible neighbors to dim relative to). Redesigned from an earlier
 * horizontal icon+label+button row after user testing showed the CTA
 * reading as "just another piece of information" rather than the one thing
 * to tap — everything here is centered and stacked so the button is the
 * single dominant element, not sharing a row with the label and icon.
 */
export default function JourneyRow({
  tone = 'brand',
  icon: Ico,
  label,
  facts,
  caption,
  badge,
  link,
  checked = false,
  ready = false,
  pending = false,
  current = false,
  stepNumber,
  totalSteps,
  nextLabel,
  preCheck,
  onCheck,
  hintText,
  hintDetail,
  hintVisible,
  onHideHint,
  tourId,
}) {
  const [detailOpen, setDetailOpen] = useState(false);
  const t = TONES[tone] || TONES.brand;
  const filled = checked || ready;
  const { active: tourHighlighted, dim: tourDim } = useTourHighlight(tourId);

  // The step actually next in line (not just the one being looked at) still
  // gets a glow — that distinction matters when someone swipes ahead to
  // preview a later step without having done the current one yet.
  const currentActive = current && !filled;

  return (
    <Box
      zIndex={tourHighlighted && tourDim ? 201 : undefined}
      bg={filled ? 'brandSoft' : 'surface'}
      border="1.5px solid"
      borderColor={filled ? 'brand' : t.border}
      borderRadius="16px"
      px={{ base: '18px', md: '26px' }}
      py={{ base: '18px', md: '22px' }}
      textAlign="center"
      position="relative"
      transition="background 1.4s ease, border-color .3s ease"
      sx={{
        '@keyframes dealoCurrentArrive': {
          '0%': { transform: 'scale(.97)', boxShadow: '0 0 0 0 transparent' },
          '100%': { transform: 'scale(1)' },
        },
        '@keyframes dealoCurrentGlow': {
          '0%, 100%': {
            boxShadow: `0 0 0 1px var(--chakra-colors-${t.color}), 0 0 14px -6px var(--chakra-colors-${t.color})`,
          },
          '50%': {
            boxShadow: `0 0 0 1.5px var(--chakra-colors-${t.color}), 0 0 28px -5px var(--chakra-colors-${t.color})`,
          },
        },
        boxShadow: currentActive
          ? `0 0 0 1px var(--chakra-colors-${t.color}), 0 0 14px -6px var(--chakra-colors-${t.color})`
          : 'none',
        animation: currentActive
          ? 'dealoCurrentArrive .45s cubic-bezier(.16,1,.3,1), dealoCurrentGlow 2.4s ease-in-out .45s infinite'
          : 'none',
        '@media (prefers-reduced-motion: reduce)': {
          animation: 'none',
          boxShadow: currentActive
            ? `0 0 0 1.5px var(--chakra-colors-${t.color})`
            : 'none',
        },
      }}
    >
      {tourHighlighted && <TourRing />}
      {stepNumber && totalSteps && (
        <Flex justify="center" align="center" mb="8px">
          <Flex
            w="26px"
            h="26px"
            flex="0 0 26px"
            borderRadius="50%"
            bg={filled ? 'brand' : t.bg}
            color={filled ? 'onBrand' : t.color}
            border="2px solid"
            borderColor={pending ? 'brand' : filled ? 'brand' : t.border}
            align="center"
            justify="center"
            transition="background .25s ease, border-color .25s ease"
            sx={{
              '@keyframes dealoStepPulse': { '0%, 100%': { opacity: 0.55 }, '50%': { opacity: 1 } },
              '@keyframes dealoStepPop': {
                '0%': { transform: 'scale(.7)' },
                '100%': { transform: 'scale(1)' },
              },
              animation: pending
                ? 'dealoStepPulse .6s ease-in-out infinite'
                : checked
                  ? 'dealoStepPop .35s cubic-bezier(.16,1,.3,1)'
                  : 'none',
            }}
          >
            {checked ? <CheckIcon /> : Ico ? <Ico size={13} /> : null}
          </Flex>
        </Flex>
      )}

      <Text fontSize="18px" fontWeight={800} color="text" letterSpacing="-.01em">
        {label}
      </Text>

      {badge && !filled && (
        <Text
          display="inline-block"
          mt="6px"
          fontSize="10.5px"
          fontWeight={700}
          color={t.color}
          bg={t.bg}
          border="1px solid"
          borderColor={t.border}
          borderRadius="99px"
          px="10px"
          py="2px"
        >
          {badge}
        </Text>
      )}

      <Box mt="12px">{facts}</Box>

      {caption && (
        <Text fontSize="11px" color="text3" mt="6px">
          {caption}
        </Text>
      )}

      {preCheck?.href && !checked && (
        <Flex
          mt="14px"
          bg="amberSoft"
          border="1.5px solid"
          borderColor="amber"
          borderRadius="sm"
          px="16px"
          py="14px"
          gap="10px"
          align="center"
          justify="space-between"
          textAlign="left"
          sx={{
            '@keyframes dealoPrecheckGlow': {
              '0%, 100%': { boxShadow: '0 0 0 0px rgba(184,132,42,.35)' },
              '50%': { boxShadow: '0 0 0 7px rgba(184,132,42,0)' },
            },
            animation: 'dealoPrecheckGlow 1.8s ease-in-out infinite',
            '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
          }}
        >
          <Flex align="center" gap="9px" flex="1" minW={0}>
            <Box color="amber" flex="0 0 auto">
              <I.alert size={16} />
            </Box>
            <Text fontSize="13.5px" fontWeight={800} color="text" lineHeight={1.3}>
              Double-check size & price first.
            </Text>
          </Flex>
          <Link
            href={preCheck.href}
            isExternal
            flex="0 0 auto"
            fontSize="13px"
            fontWeight={800}
            color="onBrand"
            bg="amber"
            border="1.5px solid"
            borderColor="amber"
            borderRadius="99px"
            px="14px"
            py="8px"
            whiteSpace="nowrap"
            boxShadow="0 4px 14px -4px var(--chakra-colors-amber)"
            _hover={{ textDecoration: 'none', bg: 'brassSoft', color: 'amber' }}
          >
            Check {preCheck.merchantName} →
          </Link>
        </Flex>
      )}

      {link?.href && (
        <Box position="relative" mt="16px">
          {!checked && <TapCue color={`var(--chakra-colors-${t.color})`} />}
          {!checked && <PingRings color={`var(--chakra-colors-${t.color})`} />}
          <Link
            href={link.href}
            isExternal
            onClick={onCheck}
            pointerEvents={pending ? 'none' : 'auto'}
            position="relative"
            display="block"
            w="100%"
            fontSize="15px"
            fontWeight={800}
            color="onBrand"
            bg={checked ? 'brand' : t.color}
            border="1.5px solid"
            borderColor={checked ? 'brand' : t.color}
            borderRadius="99px"
            px="20px"
            py="12px"
            boxShadow={checked ? 'none' : `0 4px 16px -4px var(--chakra-colors-${t.color})`}
            transition="background .2s"
            _hover={{ textDecoration: 'none', bg: checked ? 'brandHover' : t.color }}
          >
            {checked ? '✓ Done' : pending ? 'Confirming…' : link.label}
          </Link>
        </Box>
      )}

      {hintVisible && (
        <Flex
          mt="12px"
          bg="brassSoft"
          border="1px solid"
          borderColor="brass"
          borderRadius="xs"
          px="12px"
          py="9px"
          gap="10px"
          align="flex-start"
          justify="space-between"
          fontSize="12px"
          color="text"
          lineHeight={1.45}
          textAlign="left"
        >
          <Box flex="1" minW={0}>
            <Flex align="baseline" gap="6px">
              <Text>{hintText}</Text>
              {hintDetail && (
                <Box
                  as="button"
                  type="button"
                  onClick={() => setDetailOpen((o) => !o)}
                  aria-expanded={detailOpen}
                  aria-label="More detail"
                  flex="0 0 auto"
                  w="15px"
                  h="15px"
                  borderRadius="50%"
                  border="1px solid"
                  borderColor="brass"
                  bg={detailOpen ? 'brass' : 'transparent'}
                  color={detailOpen ? 'onBrand' : 'brass'}
                  fontSize="9.5px"
                  fontWeight={700}
                  fontStyle="italic"
                  fontFamily="serif"
                  display="inline-flex"
                  alignItems="center"
                  justifyContent="center"
                  lineHeight="1"
                  transition="background .12s ease, color .12s ease"
                  _focusVisible={{ outline: '2px solid', outlineColor: 'brass', outlineOffset: '2px' }}
                >
                  i
                </Box>
              )}
            </Flex>
            {hintDetail && detailOpen && (
              <Text mt="6px" fontSize="11.5px" color="text2">
                {hintDetail}
              </Text>
            )}
          </Box>
          <Box
            as="button"
            type="button"
            onClick={onHideHint}
            flex="0 0 auto"
            fontSize="11px"
            fontWeight={700}
            opacity={0.85}
            textDecoration="underline"
            whiteSpace="nowrap"
            color="brass"
            _hover={{ opacity: 1 }}
            _focusVisible={{ outline: '2px solid currentColor', outlineOffset: '2px', borderRadius: '4px' }}
          >
            Hide
          </Box>
        </Flex>
      )}

      {nextLabel && (
        <Flex mt="12px" justify="center" align="center" gap="5px" opacity={0.55}>
          <Text fontSize="10px" fontWeight={700} color="text3" textTransform="uppercase" letterSpacing=".03em">
            Up next
          </Text>
          <Text fontSize="11px" color="text2" fontWeight={600}>
            {nextLabel}
          </Text>
          <Box color="text3" w="9px" h="9px">
            <I.chevRight size={9} />
          </Box>
        </Flex>
      )}
    </Box>
  );
}
