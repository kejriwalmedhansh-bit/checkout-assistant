import { useEffect, useRef, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { Navigate, useNavigate } from 'react-router-dom';

import Card from '@/components/common/Card';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import ProductIdentity from '@/components/dashboard/ProductIdentity';
import UnverifiedWarning from '@/components/dashboard/UnverifiedWarning';
import SavingsBar from '@/components/dashboard/SavingsBar';
import RouteCard from '@/components/dashboard/RouteCard';
import CardFomo from '@/components/dashboard/CardFomo';
import AlternativesToggle from '@/components/dashboard/AlternativesToggle';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { finalPrice as calcFinal, originalPrice as calcOriginal, saving as calcSaving } from '@/utils/format';

const LOADING_MSGS = [
  'Finding the best price...',
  'Checking deals across merchants...',
  'Looking up voucher stacks...',
  'Building your route...',
  'Almost there...',
];

function LoadingCard() {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => Math.min(i + 1, LOADING_MSGS.length - 1)), 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <Flex justify="center" pt={{ base: '32px', md: '64px' }}>
      <Card p="40px 48px" maxW="360px" w="100%">
        <Flex direction="column" align="center" gap="18px">
          <Flex gap="8px">
            {[0, 1, 2].map((i) => (
              <Box
                key={i}
                w="10px"
                h="10px"
                borderRadius="50%"
                bg="orange"
                sx={{
                  animation: 'dealoPulse 1.2s ease-in-out infinite',
                  animationDelay: `${i * 0.2}s`,
                  '@keyframes dealoPulse': {
                    '0%, 100%': { opacity: 0.35, transform: 'scale(1)' },
                    '50%': { opacity: 1, transform: 'scale(1.3)' },
                  },
                }}
              />
            ))}
          </Flex>
          <Text fontSize="14px" color="text2" fontWeight={500}>
            {LOADING_MSGS[idx]}
          </Text>
        </Flex>
      </Card>
    </Flex>
  );
}

function ErrorBox({ message }) {
  return (
    <Flex
      align="flex-start"
      gap="10px"
      bg="orangeSoft2"
      border="1px solid"
      borderColor="danger"
      borderRadius="sm"
      px="18px"
      py="16px"
    >
      <Box color="danger" flex="0 0 auto" mt="1px">
        <I.alert size={18} />
      </Box>
      <Text fontSize="14px" color="text">
        {message}
      </Text>
    </Flex>
  );
}

export default function ResultsPage() {
  usePageTitle('Results');

  const navigate = useNavigate();
  const query = useSearchStore((s) => s.query);
  const result = useSearchStore((s) => s.result);
  const status = useSearchStore((s) => s.status);
  const error = useSearchStore((s) => s.error);
  const runSearch = useSearchStore((s) => s.runSearch);

  const scrollRef = useRef(null);
  const [selectedAlt, setSelectedAlt] = useState(null);

  const loading = status === 'loading';

  if (loading) return <LoadingCard />;

  // No result and nothing in flight → send the user back to search.
  if (!result && status !== 'error') return <Navigate to={ROUTES.home} replace />;

  const rec = result?.routes?.recommended || null;
  // A picked alternative is promoted here in full — same detail as the
  // recommended route — instead of expanding inline where it'd require
  // scrolling down to see.
  const activeRoute = selectedAlt || rec;

  const selectAlt = (alt) => {
    setSelectedAlt(alt);
    scrollRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const backToRecommended = () => setSelectedAlt(null);

  // "Search again" starts a fresh candidate search → back to the picker.
  const rerun = (q) => {
    setSelectedAlt(null);
    runSearch(q);
    navigate(ROUTES.select);
  };

  const productName = result?.source?.name || rec?.title || query;
  const sourceUrl = result?.mode === 'url' ? query : null;

  return (
    <Box ref={scrollRef} maxW="640px" mx="auto">
      <Box mb="18px">
        <SearchBox
          initialValue={query}
          onSubmit={rerun}
          isLoading={loading}
          size="md"
          buttonLabel="Search again"
        />
      </Box>

      {error || result?.error ? (
        <ErrorBox message={error || result.error} />
      ) : !rec ? (
        <ErrorBox message="No results found. Try a different search." />
      ) : (
        <Flex direction="column" gap="14px">
          <ProductIdentity name={productName} sourceUrl={sourceUrl} />
          {result.untrusted_sellers_warning && <UnverifiedWarning />}
          <SavingsBar
            originalPrice={calcOriginal(result, activeRoute)}
            finalPrice={calcFinal(activeRoute)}
            saving={calcSaving(result, activeRoute)}
          />
          <RouteCard
            result={result}
            rec={activeRoute}
            isAlt={!!selectedAlt}
            onBack={backToRecommended}
          />
          <CardFomo cardFomo={activeRoute.card_fomo} />
          <AlternativesToggle
            alternatives={result.routes?.alternatives}
            onSelect={selectAlt}
            selectedMerchant={selectedAlt?.merchant}
          />
        </Flex>
      )}
    </Box>
  );
}
