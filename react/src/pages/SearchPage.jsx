import { Box, Flex, Link, Text } from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';

import FloatingOutlines from '@/components/common/FloatingOutlines';
import Logo from '@/components/common/Logo';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import { gradients } from '@/theme/foundations/colors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';

// What actually happens, in the order it happens, said as pictures instead
// of sentences — per PRODUCT.md, design for the lower end of reading
// comfort by default. Replaces the earlier numbered 1-2-3 sentence list;
// the "Heads up" line below it exists because PRODUCT.md's real trust gap
// isn't online payment, it's that buying a gift voucher is an unfamiliar
// concept — naming it here means it's never a surprise on the results page.
const HOW_IT_WORKS = [
  { icon: I.link, label: 'Paste a link' },
  { icon: I.ticket, label: 'Buy a small voucher' },
  { icon: I.pay, label: 'Pay less' },
];

export default function SearchPage() {
  usePageTitle('Search');
  const navigate = useNavigate();
  const runSearch = useSearchStore((s) => s.runSearch);
  const query = useSearchStore((s) => s.query);

  const heroGlow = gradients.promptHero;

  const handleSubmit = (q) => {
    runSearch(q); // fire-and-forget; ProductSelectPage subscribes to the store
    navigate(ROUTES.select);
  };

  return (
    <Box position="relative" overflow="hidden">
      {/* green hero glow washing in from the top — deliberately wider than
          the page (up to 130%) so it bleeds past the edges on wide screens;
          this Box clips that bleed instead of letting it become real
          horizontal page overflow, which is what was making the whole page
          shift/scroll sideways on phones (confirmed: a single 744px-wide
          element on a 614px viewport, this one, nothing else). */}
      <Box
        position="absolute"
        top="-140px"
        left="50%"
        transform="translateX(-50%)"
        w="min(1100px, 130%)"
        h="420px"
        bgImage={heroGlow}
        pointerEvents="none"
        zIndex={0}
      />

      {/* faint floating product outlines — "Recall" background from the
          2026-07-28 homepage redesign, homepage-only (not used on data-dense
          pages like results/product-picker, where it would compete with
          real content) */}
      <FloatingOutlines />

      <Flex
        direction="column"
        align="center"
        justify="center"
        textAlign="center"
        maxW="640px"
        mx="auto"
        pt={{ base: '32px', md: '64px' }}
        position="relative"
        zIndex={1}
      >
        <Box mb={{ base: '18px', md: '22px' }}>
          <Link as={RouterLink} to={ROUTES.home} _hover={{ textDecoration: 'none' }}>
            <Logo size={{ base: '48px', md: '68px' }} />
          </Link>
        </Box>

        <Text
          fontSize={{ base: '30px', md: '44px' }}
          fontWeight={800}
          letterSpacing="-.03em"
          lineHeight={1.12}
          color="text"
        >
          Never pay full price.{' '}
          <Box as="span" color="brand">
            Just search.
          </Box>
        </Text>
        <Text fontSize={{ base: '14px', md: '15px' }} color="text2" mt="12px" maxW="440px" lineHeight={1.6}>
          Paste any product link, or type what you want to buy. We check every store and every
          gift-voucher discount, then show you the cheapest way to actually pay — no credit card
          needed.
        </Text>

        <Box
          w="100%"
          mt="36px"
          bg="surface"
          border="1.5px solid"
          borderColor="brand"
          borderRadius="lg"
          boxShadow="0 0 0 1px var(--chakra-colors-brand), 0 0 22px -6px var(--chakra-colors-brand)"
          p={{ base: '14px', md: '18px' }}
          textAlign="left"
        >
          <Text
            fontSize="10.5px"
            fontWeight={700}
            color="brandText"
            textTransform="uppercase"
            letterSpacing=".05em"
            mb="8px"
          >
            Type here
          </Text>
          <SearchBox
            initialValue={query}
            onSubmit={handleSubmit}
            placeholder={'e.g. "Onitsuka Tiger Mexico 66" or paste a link'}
          />
        </Box>

        <Box
          w="100%"
          mt="28px"
          bg="surface"
          border="1px solid"
          borderColor="border"
          borderRadius="lg"
          p={{ base: '14px 10px', md: '16px 14px' }}
        >
          <Flex align="center" justify="space-between">
            {HOW_IT_WORKS.map((step, i) => (
              <Flex key={step.label} align="center" flex={i === HOW_IT_WORKS.length - 1 ? '0 0 auto' : '1'}>
                <Flex direction="column" align="center" gap="6px" flex="1" minW="0" px="4px">
                  <Flex
                    w="38px"
                    h="38px"
                    flex="0 0 38px"
                    borderRadius="12px"
                    align="center"
                    justify="center"
                    bg={i === HOW_IT_WORKS.length - 1 ? 'greenSoft' : 'amberSoft'}
                    color={i === HOW_IT_WORKS.length - 1 ? 'green' : 'amber'}
                  >
                    <step.icon size={20} />
                  </Flex>
                  <Text fontSize="11px" fontWeight={700} color="text" textAlign="center" lineHeight={1.25}>
                    {step.label}
                  </Text>
                </Flex>
                {i < HOW_IT_WORKS.length - 1 && (
                  <Box color="border" flex="0 0 auto">
                    <I.chevRight size={16} />
                  </Box>
                )}
              </Flex>
            ))}
          </Flex>
        </Box>

        <Flex
          w="100%"
          mt="12px"
          gap="9px"
          align="flex-start"
          bg="amberSoft"
          borderRadius="md"
          p="11px 12px"
          textAlign="left"
        >
          <Box color="amber" mt="1px" flex="0 0 auto">
            <I.info size={15} />
          </Box>
          <Text fontSize="12px" color="text" lineHeight={1.45}>
            <Text as="span" fontWeight={700}>
              Heads up:
            </Text>{' '}
            step 2 is buying a small voucher yourself. Takes 30 seconds — that's how the discount
            works.
          </Text>
        </Flex>
      </Flex>
    </Box>
  );
}
