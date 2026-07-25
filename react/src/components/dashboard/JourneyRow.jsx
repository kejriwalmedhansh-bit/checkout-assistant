import { Box, Flex, Link, Text } from '@chakra-ui/react';

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

function PingRings({ borderColor }) {
  return (
    <>
      {[0, 1].map((i) => (
        <Box
          key={i}
          position="absolute"
          inset="0"
          borderRadius="99px"
          border="1.5px solid"
          borderColor={borderColor}
          pointerEvents="none"
          sx={{
            '@keyframes dealoPing': {
              '0%': { opacity: 0.7, transform: 'scale(1)' },
              '100%': { opacity: 0, transform: 'scale(1.45)' },
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
 * One always-visible row in the checklist: icon dot, label, and the action
 * button side by side, with the real facts (price / voucher amounts) and a
 * dismissible hint always shown beneath — nothing is hidden behind a
 * dropdown, since every step's information matters regardless of which step
 * is currently active. Once a step is done, the whole row washes to a soft
 * green rather than only the icon dot changing — deliberately slow (see the
 * `background` transition below) so it reads as a gentle confirmation, not
 * a jarring flip.
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
  emphasized = false,
  current = false,
  onCheck,
  hintText,
  hintVisible,
  onHideHint,
}) {
  const t = TONES[tone] || TONES.brand;
  const filled = checked || ready;
  // Nothing is ever hidden — every step stays fully visible and fully
  // readable regardless of progress (that shell was tried twice before and
  // reverted both times for hiding info the user considered important). The
  // "flow" feeling instead comes from contrast: the step that's next gets a
  // glow and full opacity, everything else (not yet reached, and not done)
  // sits quieter — a look difference, not an information difference.
  const quiet = !filled && !current;

  // When a step becomes current, it pops in (a quick scale-up, not just a
  // fade) and then breathes gently in place — the same "something needs you"
  // language as the button's own TapCue/PingRings, just on the whole card
  // this time, since asking someone to notice a color change alone (even
  // glowing) is easy to miss on a page they're skimming.
  const currentActive = current && !filled;

  return (
    <Box
      bg={filled ? 'brandSoft' : emphasized ? t.bg : 'transparent'}
      border={(emphasized || current) && !filled ? '1.5px solid' : '1.5px solid transparent'}
      borderColor={(emphasized || current) && !filled ? t.border : 'transparent'}
      borderRadius="10px"
      px={filled || emphasized || current ? '13px' : '0'}
      mx={filled || emphasized || current ? '-13px' : '0'}
      opacity={quiet ? 0.6 : 1}
      transition="background 1.4s ease, padding .3s ease, margin .3s ease, border-color .3s ease, opacity .35s ease"
      sx={{
        '@keyframes dealoCurrentArrive': {
          '0%': { transform: 'scale(.97)', boxShadow: '0 0 0 0 transparent' },
          '40%': { transform: 'scale(1.008)' },
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
          ? 'dealoCurrentArrive .45s cubic-bezier(.34,1.2,.64,1), dealoCurrentGlow 2.4s ease-in-out .45s infinite'
          : 'none',
        '@media (prefers-reduced-motion: reduce)': {
          animation: 'none',
          boxShadow: currentActive
            ? `0 0 0 1.5px var(--chakra-colors-${t.color})`
            : 'none',
        },
      }}
    >
      <Flex align="center" gap="14px" py="11px">
        <Flex
          w="34px"
          h="34px"
          flex="0 0 34px"
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
              '60%': { transform: 'scale(1.15)' },
              '100%': { transform: 'scale(1)' },
            },
            animation: pending
              ? 'dealoStepPulse .6s ease-in-out infinite'
              : checked
                ? 'dealoStepPop .35s cubic-bezier(.34,1.56,.64,1)'
                : 'none',
          }}
        >
          {checked ? <CheckIcon /> : Ico ? <Ico size={16} /> : null}
        </Flex>

        <Box flex="1" minW={0}>
          <Text fontSize="13.5px" fontWeight={700} color="text">
            {label}
          </Text>
          {badge && !filled && (
            <Text
              display="inline-block"
              mt="3px"
              fontSize="10.5px"
              fontWeight={700}
              color={t.color}
              bg={t.bg}
              border="1px solid"
              borderColor={t.border}
              borderRadius="99px"
              px="8px"
              py="1px"
            >
              {badge}
            </Text>
          )}
        </Box>

        {link?.href && (
          <Box position="relative" flex="0 0 auto">
            {!checked && <TapCue color={`var(--chakra-colors-${t.color})`} />}
            {!checked && <PingRings borderColor={t.color} />}
            <Link
              href={link.href}
              isExternal
              onClick={onCheck}
              pointerEvents={pending ? 'none' : 'auto'}
              position="relative"
              fontSize="12.5px"
              fontWeight={700}
              color="onBrand"
              bg={checked ? 'brand' : t.color}
              border="1.5px solid"
              borderColor={checked ? 'brand' : t.color}
              borderRadius="99px"
              px="14px"
              py="8px"
              whiteSpace="nowrap"
              boxShadow={checked ? 'none' : `0 2px 10px -2px var(--chakra-colors-${t.color})`}
              transition="background .2s"
              _hover={{ textDecoration: 'none', bg: checked ? 'brandHover' : t.color }}
            >
              {checked ? '✓ Done' : pending ? 'Confirming…' : link.label}
            </Link>
          </Box>
        )}
      </Flex>

      <Box pl="48px" pb="11px">
        {facts}

        {caption && (
          <Text fontSize="11px" color="text3" mt="6px">
            {caption}
          </Text>
        )}

        {hintVisible && (
          <Flex
            mt="10px"
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
          >
            <Text>{hintText}</Text>
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
      </Box>
    </Box>
  );
}
