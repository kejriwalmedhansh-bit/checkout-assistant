import { useState } from 'react';
import { Box, Button, Collapse, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import BackButton from '@/components/common/BackButton';
import { I } from '@/components/common/icons';
import { useJsonLd } from '@/hooks/useJsonLd';
import { usePageHeader } from '@/hooks/usePageHeader';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { track } from '@/utils/analytics';

const FAQS = [
  {
    q: 'Why do I sometimes buy a Gift Voucher before checkout?',
    a: "It's usually the cheapest legitimate route: the store's own official voucher partner sells store credit at a discount. You buy the Gift Voucher, then spend it at checkout exactly like a gift card — same store, same product, lower total. It's real store credit, not a workaround.",
  },
  {
    q: 'Is this safe?',
    a: 'Yes. Gift Vouchers come from the store’s official partner, and Dealo never handles your money or your card details — you always pay the store directly, on the store’s own site.',
  },
  {
    q: 'Do I need a credit card?',
    a: "No. Our top recommendation never requires one. If you do have a card, we'll show you when it saves you a little more — never as a requirement.",
  },
];

// Eligible for Google's FAQ rich result — the on-page copy and this data
// are the same three questions, kept in the same array on purpose so they
// can never drift apart.
const FAQ_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: FAQS.map((f) => ({
    '@type': 'Question',
    name: f.q,
    acceptedAnswer: { '@type': 'Answer', text: f.a },
  })),
};

function FaqItem({ q, a, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Box border="1px solid" borderColor="border" borderRadius="12px" bg="surface" overflow="hidden">
      <Button
        variant="ghost"
        w="100%"
        h="auto"
        py="12px"
        px="13px"
        justifyContent="space-between"
        borderRadius="0"
        fontSize="12.5px"
        fontWeight={700}
        textAlign="left"
        whiteSpace="normal"
        onClick={() => {
          if (!open) track('Clicked FAQ Item', { question: q });
          setOpen((v) => !v);
        }}
        rightIcon={
          <Box as="span" flex="0 0 auto" color="text3" transform={open ? 'rotate(180deg)' : 'none'} transition="transform .18s ease">
            <I.chevDown size={15} />
          </Box>
        }
      >
        {q}
      </Button>
      <Collapse in={open} animateOpacity>
        <Text m={0} px="13px" pb="13px" fontSize="12px" color="text2" lineHeight={1.6}>
          {a}
        </Text>
      </Collapse>
    </Box>
  );
}

/** The step's screenshot, on an offset colour card with a slight rotation —
 * reads as placed and designed rather than a flat crop in a box. `side`
 * drives float direction (and which way the card leans); `center` is the
 * one exception, the establishing shot in step 1, which doesn't need text
 * wrapping around it. */
function Shot({ src, alt, side = 'left', center = false }) {
  if (center) {
    return (
      <Box w={{ base: '72vw', md: '340px' }} maxW={{ base: '300px', md: '340px' }} mx="auto" mb="22px" position="relative">
        <Box position="absolute" inset="14px -14px -14px 14px" borderRadius="20px" bg="brandSoft" transform="rotate(-1.6deg)" />
        <Box position="relative" borderRadius="18px" overflow="hidden" border="1px solid" borderColor="border" boxShadow="0 24px 44px -20px rgba(22,32,43,.34)" bg="surface">
          <Box as="img" src={src} alt={alt} display="block" w="100%" h="auto" />
        </Box>
      </Box>
    );
  }
  const left = side === 'left';
  return (
    <Box
      float={{ base: 'none', md: left ? 'left' : 'right' }}
      ml={{ base: 'auto', md: left ? 0 : '34px' }}
      mr={{ base: 'auto', md: left ? '34px' : 0 }}
      w={{ base: '58vw', md: '250px' }}
      maxW={{ base: '230px', md: '250px' }}
      mb="18px"
      position="relative"
    >
      <Box
        position="absolute"
        inset="14px -14px -14px 14px"
        borderRadius="20px"
        bg={left ? 'brandSoft' : 'brassSoft'}
        transform={left ? 'rotate(-2deg)' : 'rotate(2deg)'}
      />
      <Box
        position="relative"
        borderRadius="18px"
        overflow="hidden"
        border="1px solid"
        borderColor="border"
        boxShadow="0 24px 44px -20px rgba(22,32,43,.34)"
        bg="surface"
        transform={left ? 'rotate(-1.4deg)' : 'rotate(1.4deg)'}
      >
        <Box as="img" src={src} alt={alt} display="block" w="100%" h="auto" />
      </Box>
    </Box>
  );
}

/** Step 2's pair — the listing and the closer look, overlapping. */
function Duo({ srcA, altA, srcB, altB }) {
  return (
    <Box
      float={{ base: 'none', md: 'left' }}
      ml={{ base: 'auto', md: 0 }}
      mr={{ base: 'auto', md: '34px' }}
      w={{ base: '58vw', md: '250px' }}
      maxW={{ base: '230px', md: '250px' }}
      h={{ base: '210px', md: '290px' }}
      mb="18px"
      position="relative"
    >
      <Box position="absolute" inset="14px -14px -14px 14px" borderRadius="20px" bg="brandSoft" transform="rotate(-2deg)" />
      <Box
        as="img"
        src={srcA}
        alt={altA}
        position="absolute"
        top={0}
        left={0}
        w="78%"
        borderRadius="14px"
        border="3px solid"
        borderColor="surface"
        boxShadow="0 20px 36px -16px rgba(22,32,43,.36)"
        transform="rotate(-2deg)"
        zIndex={1}
      />
      <Box
        as="img"
        src={srcB}
        alt={altB}
        position="absolute"
        bottom={0}
        right={0}
        w="56%"
        borderRadius="14px"
        border="3px solid"
        borderColor="surface"
        boxShadow="0 20px 36px -16px rgba(22,32,43,.36)"
        transform="rotate(2deg)"
        zIndex={2}
      />
    </Box>
  );
}

function Marker({ children }) {
  return (
    <Flex
      align="center"
      justify="center"
      w="34px"
      h="34px"
      borderRadius="999px"
      bg="brand"
      color="onBrand"
      fontFamily="mono"
      fontSize="13px"
      fontWeight={700}
      mb="12px"
    >
      {children}
    </Flex>
  );
}

function StepTitle({ children }) {
  return (
    <Text as="h3" m="0 0 9px" fontSize="24px" fontWeight={800} letterSpacing="-.02em" lineHeight={1.14} color="brand">
      {children}
    </Text>
  );
}

function StepBody({ children }) {
  return (
    <Text fontSize="14.5px" color="text2" lineHeight={1.55} m={0}>
      {children}
    </Text>
  );
}

const Emph = (props) => <Text as="b" color="text" fontWeight={800} {...props} />;
const Stat = (props) => <Text as="span" fontFamily="mono" color="brass" fontWeight={700} {...props} />;

/** The real Dealo mark — an ink ring "picked up," a navy dashed route, and
 * a copper dot "dropped off." This is the approved two-tone lockup asset
 * (distinct from the single-colour nav icon in LogoIcon.jsx), used here
 * as a deliberate brand touch: once as a badge, once as a divider mark. */
function DealoMarkBadge({ size = 56 }) {
  return (
    <Box w={`${size}px`} h={`${size}px`} mx="auto" mb="18px" borderRadius="999px" boxShadow="0 12px 26px -12px rgba(31,58,95,.55)">
      <svg width={size} height={size} viewBox="0 0 512 512">
        <circle cx="256" cy="256" r="256" fill="#1F3A5F" />
        <g transform="translate(102 102) scale(4.8)">
          <circle cx="15" cy="49" r="5.5" fill="none" stroke="#FAFAF7" strokeWidth="4.5" />
          <path d="M15 39.5 C15 26 49 38 49 23" fill="none" stroke="#FAFAF7" strokeWidth="4.5" strokeLinecap="butt" strokeDasharray="9 7" />
          <circle cx="49" cy="17" r="7.5" fill="#D8873F" />
        </g>
      </svg>
    </Box>
  );
}

function DealoMarkLine({ size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" style={{ opacity: 0.85, flex: '0 0 auto' }}>
      <circle cx="15" cy="49" r="5.5" fill="none" stroke="#16202B" strokeWidth="4.5" />
      <path d="M15 39.5 C15 26 49 38 49 23" fill="none" stroke="#1F3A5F" strokeWidth="4.5" strokeLinecap="butt" strokeDasharray="9 7" />
      <circle cx="49" cy="17" r="7.5" fill="#C2712F" />
    </svg>
  );
}

export default function HowItWorksPage() {
  usePageTitle(
    'How it works',
    'How Dealo finds the cheapest legitimate way to buy something online — from pasting a product link to checking out with a discounted Gift Voucher.'
  );
  useJsonLd(FAQ_JSON_LD);

  const backControl = <BackButton fallback={ROUTES.home} iconOnly />;
  // Below `lg` this renders in AppLayout's mobile top bar instead of an
  // in-page row, matching the pattern ResultsPage uses for its own back
  // control (see usePageHeader.js).
  usePageHeader({ left: backControl });

  return (
    <Box maxW="680px" mx="auto">
      <Flex display={{ base: 'none', lg: 'flex' }} align="center" gap="6px" mb="14px">
        {backControl}
      </Flex>

      <Box bg="surface" border="1px solid" borderColor="border" borderRadius="28px" boxShadow="0 1px 2px rgba(22,32,43,.06), 0 24px 52px -20px rgba(22,32,43,.24)" px={{ base: '22px', md: '40px' }} py={{ base: '30px', md: '38px' }}>
        {/* ---- page head ---- */}
        <Box textAlign="center" mb="40px">
          <DealoMarkBadge />
          <Text as="h1" m="0 0 9px" fontSize="32px" fontWeight={800} letterSpacing="-.025em" lineHeight={1.08}>
            How Dealo works
          </Text>
          <Text fontSize="14px" color="text2" lineHeight={1.55} maxW="400px" mx="auto">
            Same product end to end, so you can see exactly what happens at each step.
          </Text>
        </Box>

        {/* ---- step 1 ---- */}
        <Box display="flow-root" mb="60px" textAlign="center">
          <Shot center src="/how-it-works/search.png" alt="Searching Birkenstock shoes on Dealo" />
          <Marker>1</Marker>
          <StepTitle>Tell us what you want</StepTitle>
          <StepBody>
            <ChakraLink as={RouterLink} to={ROUTES.home} color="brand" fontWeight={700} textDecoration="underline" textUnderlineOffset="2px">
              Paste a product link
            </ChakraLink>{' '}
            from any store, or just describe it, like <Emph>&ldquo;Birkenstock shoes.&rdquo;</Emph> That&rsquo;s all we need.
          </StepBody>
        </Box>

        {/* ---- step 2 ---- */}
        <Box display="flow-root" mb="60px">
          <Duo
            srcA="/how-it-works/picker.png"
            altA="Matching Birkenstock listings on Dealo"
            srcB="/how-it-works/quickview.png"
            altB="A closer look at one listing"
          />
          <Marker>2</Marker>
          <StepTitle>Pick the exact one you mean</StepTitle>
          <StepBody>
            <Emph>&ldquo;Birkenstock shoes&rdquo;</Emph> could mean a dozen models, so tap a photo for a closer look, then we check
            that exact listing everywhere.
          </StepBody>
        </Box>

        {/* ---- step 3 ---- */}
        <Box display="flow-root" mb="60px">
          <Shot side="right" src="/how-it-works/voucher.png" alt="Dealo recommending a Gift Voucher for Birkenstock, with a check-the-product-first button" />
          <Marker>3</Marker>
          <StepTitle>Check the product, then buy the voucher</StepTitle>
          <StepBody>
            Quickly confirm size and colour on the real product page, sizes vary by store, then buy the <Emph>Gift Voucher</Emph>:{' '}
            <Stat>10% off</Stat> here, real store credit.
          </StepBody>
        </Box>

        {/* ---- step 4 ---- */}
        <Box display="flow-root" mb="60px">
          <Shot side="left" src="/how-it-works/checkout.png" alt="Checking out at Birkenstock India with the voucher applied" />
          <Marker>4</Marker>
          <StepTitle>Check out with the store, directly</StepTitle>
          <StepBody>
            Add it to your cart, apply the code, pay what&rsquo;s left. Dealo never sees your card, you&rsquo;re paying <Emph>Birkenstock</Emph>.
          </StepBody>
        </Box>

        {/* ---- divider ---- */}
        <Flex align="center" gap="12px" mb="48px">
          <Box flex={1} h="1px" bg="border" />
          <DealoMarkLine />
          <Text fontFamily="mono" fontSize="10.5px" fontWeight={600} letterSpacing=".05em" color="text3" textTransform="uppercase" whiteSpace="nowrap">
            A second thing we do
          </Text>
          <Box flex={1} h="1px" bg="border" />
        </Flex>

        {/* ---- second feature: standalone voucher search ---- */}
        <Text as="h2" m="0 0 9px" fontSize="22px" fontWeight={800} letterSpacing="-.02em" color="brand">
          Can&rsquo;t search it? You can still save on it.
        </Text>
        <Text fontSize="14px" color="text2" lineHeight={1.55} mb="28px">
          Dealo&rsquo;s search box is built for products, so you can&rsquo;t type in a flight or a hotel booking. But the same{' '}
          <Emph>Gift Voucher</Emph> discounts exist for travel brands too,{' '}
          <ChakraLink as={RouterLink} to={ROUTES.home} color="brand" fontWeight={700} textDecoration="underline" textUnderlineOffset="2px">
            search the brand by name
          </ChakraLink>{' '}
          on its own and we&rsquo;ll show you its rate directly.
        </Text>

        <Box display="flow-root" mb="8px">
          <Shot side="right" src="/how-it-works/makemytrip.png" alt="MakeMyTrip Gift Voucher at 7.5% off on Dealo" />
          <Marker>✦</Marker>
          <StepTitle>Booking with MakeMyTrip?</StepTitle>
          <StepBody>
            Search <Emph>&ldquo;MakeMyTrip&rdquo;</Emph> on its own, no flight details needed: <Stat>7.5% off</Stat>, checked live,
            spend it like store credit when you book.
          </StepBody>
        </Box>

        {/* ---- verify strip ---- */}
        <Flex clear="both" align="flex-start" gap="10px" p="14px 16px" borderRadius="14px" bg="greenSoft" border="1px solid #CFE4D8" mt="8px">
          <Box color="green" mt="1px" flex="0 0 auto">
            <I.check size={16} />
          </Box>
          <Text m={0} fontSize="12.5px" color="#1E5B41" lineHeight={1.55}>
            <Text as="b" fontWeight={700}>
              Every price and discount shown is checked live
            </Text>{' '}
            at the moment you search, not looked up from a stale list.
          </Text>
        </Flex>
      </Box>

      {/* ---- FAQ ---- */}
      <Box mt="22px">
        <Text as="h2" m="0 0 8px" fontSize="14px" fontWeight={800} letterSpacing="-.005em">
          Questions people actually ask
        </Text>
        <Flex direction="column" gap="8px">
          {FAQS.map((f, i) => (
            <FaqItem key={f.q} q={f.q} a={f.a} defaultOpen={i === 0} />
          ))}
        </Flex>
      </Box>

      <Flex align="center" justify="center" gap="6px" fontSize="11px" color="text3" mt="18px">
        <I.pay size={13} />
        <Text as="span">Dealo never asks for your card number or OTP.</Text>
      </Flex>
    </Box>
  );
}
