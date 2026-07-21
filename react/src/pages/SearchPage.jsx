import { Box, Flex, Link, Text } from '@chakra-ui/react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';

import Logo from '@/components/common/Logo';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import { gradients } from '@/theme/foundations/colors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';

const PILLARS = [
  { icon: 'trendUp', label: 'Best price', desc: 'Compared across trusted stores' },
  { icon: 'ticket', label: 'Gift Voucher discounts', desc: 'Real discounts, applied for you' },
  { icon: 'checkCircle', label: 'One simple way to buy', desc: 'No credit card needed, works for anyone' },
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
        <Box mb={{ base: '22px', md: '28px' }}>
          <Link as={RouterLink} to={ROUTES.home} _hover={{ textDecoration: 'none' }}>
            <Logo size={38} />
          </Link>
        </Box>

        <Text
          fontSize={{ base: '30px', md: '44px' }}
          fontWeight={800}
          letterSpacing="-.03em"
          lineHeight={1.12}
          color="text"
        >
          The smartest way to{' '}
          <Box as="span" color="brand">
            buy
          </Box>
        </Text>
        <Text fontSize={{ base: '14px', md: '15px' }} color="text2" mt="12px" maxW="440px" lineHeight={1.6}>
          Paste a product link or type what you want. We&apos;ll find the lowest price and show
          you exactly how to get it — no credit card required.
        </Text>

        <Box
          w="100%"
          mt="36px"
          bg="surface"
          border="1px solid"
          borderColor="border"
          borderRadius="lg"
          boxShadow="lg"
          p={{ base: '14px', md: '18px' }}
        >
          <SearchBox initialValue={query} onSubmit={handleSubmit} />
        </Box>

        <Flex gap="12px" mt="28px" w="100%" flexWrap="wrap">
          {PILLARS.map((p) => {
            const Icon = I[p.icon];
            return (
              <Flex
                key={p.label}
                flex="1 1 160px"
                bg="surface"
                border="1px solid"
                borderColor="border"
                borderRadius="md"
                boxShadow="sm"
                p="16px"
                textAlign="left"
                gap="10px"
                align="flex-start"
                transition="transform .15s ease, box-shadow .15s ease"
                _hover={{ transform: 'translateY(-2px)', boxShadow: 'md' }}
              >
                <Flex
                  flex="0 0 auto"
                  w="30px"
                  h="30px"
                  borderRadius="9px"
                  bg="brandSoft"
                  color="brand"
                  align="center"
                  justify="center"
                >
                  <Icon size={16} />
                </Flex>
                <Box>
                  <Text fontSize="13px" fontWeight={700} color="text">
                    {p.label}
                  </Text>
                  <Text fontSize="12px" color="text3" mt="2px" lineHeight={1.5}>
                    {p.desc}
                  </Text>
                </Box>
              </Flex>
            );
          })}
        </Flex>
      </Flex>
    </Box>
  );
}
