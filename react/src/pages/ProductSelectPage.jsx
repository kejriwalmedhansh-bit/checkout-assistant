import { Box, Flex, Text } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';
import { Navigate, useNavigate } from 'react-router-dom';

import BackButton from '@/components/common/BackButton';
import Card from '@/components/common/Card';
import ErrorBox from '@/components/common/ErrorBox';
import LoadingCard from '@/components/common/LoadingCard';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import ApproximateNotice from '@/components/dashboard/ApproximateNotice';
import ProductCandidateCard from '@/components/dashboard/ProductCandidateCard';
import { usePageTitle } from '@/hooks/usePageTitle';
import { gradients } from '@/theme/foundations/colors';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';

const LOADING_MSGS = [
  'Looking that up...',
  'Checking what is actually in stock...',
  'Matching the exact product...',
  'Almost there...',
];

export default function ProductSelectPage() {
  usePageTitle('Select a product');
  const prefersReduced = useReducedMotion();
  const heroGlow = gradients.promptHero;

  const navigate = useNavigate();
  const query = useSearchStore((s) => s.query);
  const candidates = useSearchStore((s) => s.candidates);
  const approximate = useSearchStore((s) => s.approximate);
  const searchStatus = useSearchStore((s) => s.searchStatus);
  const status = useSearchStore((s) => s.status);
  const selectedToken = useSearchStore((s) => s.selectedToken);
  const error = useSearchStore((s) => s.error);
  const runSearch = useSearchStore((s) => s.runSearch);
  const selectProduct = useSearchStore((s) => s.selectProduct);

  // Direct load with no search in flight → back to home.
  if (searchStatus === 'idle') return <Navigate to={ROUTES.home} replace />;

  const rerun = (q) => runSearch(q);

  const handleSelect = (token, title, price, source, thumbnail) => {
    selectProduct(token, title, price, source, thumbnail); // fire-and-forget; ResultsPage shows its own loader
    navigate(ROUTES.results);
  };

  return (
    <Box position="relative">
      <Box
        position="absolute"
        top="-120px"
        left="50%"
        transform="translateX(-50%)"
        w="min(900px, 130%)"
        h="320px"
        bgImage={heroGlow}
        pointerEvents="none"
        zIndex={0}
      />

      <Box maxW="680px" mx="auto" position="relative" zIndex={1}>
        <Box mb="10px" ml="-10px">
          <BackButton fallback={ROUTES.home} label="Back to search" />
        </Box>

        <Box mb="20px">
          <Text fontSize="11px" color="text3" fontWeight={500} letterSpacing=".06em" textTransform="uppercase">
            {searchStatus === 'loading'
              ? 'Looking for'
              : searchStatus === 'success' && candidates.length > 0
                ? 'Here is what we found for'
                : 'You searched for'}
          </Text>
          <Text fontSize={{ base: '20px', md: '24px' }} fontWeight={800} letterSpacing="-.02em" color="text" noOfLines={1}>
            {query}
          </Text>
        </Box>

        <Box mb="20px">
          <SearchBox
            initialValue={query}
            onSubmit={rerun}
            isLoading={searchStatus === 'loading'}
            size="md"
            buttonLabel="Search"
          />
        </Box>

        {searchStatus === 'loading' && <LoadingCard messages={LOADING_MSGS} />}

        {searchStatus === 'error' && <ErrorBox message={error || 'Search failed.'} />}

        {searchStatus === 'success' && candidates.length === 0 && (
          <Card p="36px 22px">
            <Flex direction="column" align="center" gap="12px" textAlign="center">
              <Flex w="48px" h="48px" borderRadius="12px" bg="brandSoft" color="brand" align="center" justify="center">
                <I.search size={22} />
              </Flex>
              <Box>
                <Text fontSize="14px" fontWeight={600} color="text">
                  No products found
                </Text>
                <Text fontSize="13px" color="text3" mt="2px">
                  Try a shorter or more general search term.
                </Text>
              </Box>
            </Flex>
          </Card>
        )}

        {searchStatus === 'success' && candidates.length > 0 && (
          <>
            {approximate && <ApproximateNotice variant="picker" />}
            <Text fontSize="13px" color="text3" mb="12px">
              Select the exact product you want — we&apos;ll find the cheapest way to buy it.
            </Text>
            <Flex direction="column" gap="10px">
              {candidates.map((p, i) => (
                <motion.div
                  key={p.product_token || i}
                  initial={prefersReduced ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: Math.min(i * 0.045, 0.4), ease: [0.16, 1, 0.3, 1] }}
                >
                  <ProductCandidateCard
                    product={p}
                    onSelect={handleSelect}
                    isSelecting={status === 'loading' && selectedToken === p.product_token}
                  />
                </motion.div>
              ))}
            </Flex>
          </>
        )}
      </Box>
    </Box>
  );
}
