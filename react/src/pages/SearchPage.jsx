import { Box, Flex, Link, Text } from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';

import FloatingOutlines from '@/components/common/FloatingOutlines';
import Logo from '@/components/common/Logo';
import SearchBox from '@/components/common/SearchBox';
import { gradients } from '@/theme/foundations/colors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';

// What actually happens, in the order it happens — replaces the old 3
// disconnected feature badges (Best price / Gift Voucher discounts / One
// simple way to buy) with the same numbered-step shape used on the results
// page, so "why am I typing this" gets answered as a sequence, not a list
// of separate claims.
const HOW_IT_WORKS = [
  {
    title: 'Tell us what you want',
    desc: 'A product name, or paste any store link — whatever’s easier.',
  },
  {
    title: 'We check prices + gift vouchers',
    desc: 'Every trusted store, plus discounted gift vouchers that stack on top.',
  },
  {
    title: 'You get the cheapest way to buy',
    desc: 'One recommended route, no credit card required, works for anyone.',
  },
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
    <Box position="relative">
      {/* green hero glow washing in from the top */}
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
          p={{ base: '16px 18px', md: '18px 22px' }}
          textAlign="left"
        >
          {HOW_IT_WORKS.map((step, i) => (
            <Box key={step.title}>
              <Flex gap="14px" align="flex-start" py="10px">
                <Flex
                  w="28px"
                  h="28px"
                  flex="0 0 28px"
                  borderRadius="50%"
                  bg="brandSoft"
                  color="brandText"
                  border="1.5px solid"
                  borderColor="brand"
                  align="center"
                  justify="center"
                  fontSize="12.5px"
                  fontWeight={800}
                >
                  {i + 1}
                </Flex>
                <Box>
                  <Text fontSize="13.5px" fontWeight={700} color="text">
                    {step.title}
                  </Text>
                  <Text fontSize="12px" color="text3" mt="2px" lineHeight={1.5}>
                    {step.desc}
                  </Text>
                </Box>
              </Flex>
              {i < HOW_IT_WORKS.length - 1 && (
                <Flex pl="13px">
                  <Box w="2px" h="10px" bg="borderStrong" />
                </Flex>
              )}
            </Box>
          ))}
        </Box>
      </Flex>
    </Box>
  );
}
