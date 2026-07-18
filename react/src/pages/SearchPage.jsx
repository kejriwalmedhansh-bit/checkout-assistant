import { Box, Flex, Text } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';

import SearchBox from '@/components/common/SearchBox';
import { gradients } from '@/theme/foundations/colors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useColorModeValue } from '@chakra-ui/react';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';

const PILLARS = [
  { label: 'Best price', desc: 'Compared across trusted stores' },
  { label: 'Gift Voucher discounts', desc: 'Real discounts, applied for you' },
  { label: 'One simple way to buy', desc: 'No credit card needed, works for anyone' },
];

export default function SearchPage() {
  usePageTitle('Search');
  const navigate = useNavigate();
  const runSearch = useSearchStore((s) => s.runSearch);
  const query = useSearchStore((s) => s.query);

  const heroGlow = useColorModeValue(gradients.promptHeroLight, gradients.promptHeroDark);

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

      <Flex
        direction="column"
        align="center"
        justify="center"
        textAlign="center"
        maxW="640px"
        mx="auto"
        pt={{ base: '40px', md: '76px' }}
        position="relative"
        zIndex={1}
      >
        <Text
          fontSize={{ base: '28px', md: '40px' }}
          fontWeight={800}
          letterSpacing="-.03em"
          lineHeight={1.15}
          color="text"
        >
          The smartest way to{' '}
          <Box as="span" color="brand">
            buy
          </Box>
        </Text>
        <Text fontSize={{ base: '14px', md: '15px' }} color="text2" mt="10px" maxW="440px" lineHeight={1.6}>
          Paste a product link or type what you want. We&apos;ll find the lowest price and show
          you exactly how to get it — no credit card required.
        </Text>

        <Box w="100%" mt="32px">
          <SearchBox initialValue={query} onSubmit={handleSubmit} />
        </Box>

        <Flex gap="12px" mt="28px" w="100%" flexWrap="wrap">
          {PILLARS.map((p) => (
            <Box
              key={p.label}
              flex="1 1 160px"
              bg="surface"
              border="1px solid"
              borderColor="border"
              borderRadius="sm"
              boxShadow="sm"
              p="14px 16px"
              textAlign="left"
            >
              <Text fontSize="13px" fontWeight={700} color="text">
                {p.label}
              </Text>
              <Text fontSize="12px" color="text3" mt="2px" lineHeight={1.5}>
                {p.desc}
              </Text>
            </Box>
          ))}
        </Flex>
      </Flex>
    </Box>
  );
}
