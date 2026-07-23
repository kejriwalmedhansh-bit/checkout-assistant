import { useRef, useState } from 'react';
import { Box, Flex } from '@chakra-ui/react';
import { Navigate, useNavigate } from 'react-router-dom';

import BackButton from '@/components/common/BackButton';
import ErrorBox from '@/components/common/ErrorBox';
import LoadingCard from '@/components/common/LoadingCard';
import SearchBox from '@/components/common/SearchBox';
import ApproximateNotice from '@/components/dashboard/ApproximateNotice';
import ProductIdentity from '@/components/dashboard/ProductIdentity';
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
  'Checking deals across stores...',
  'Looking for gift voucher discounts...',
  'Working out the cheapest way to buy it...',
  'Almost there...',
];

export default function ResultsPage() {
  usePageTitle('Results');

  const navigate = useNavigate();
  const query = useSearchStore((s) => s.query);
  const result = useSearchStore((s) => s.result);
  const approximate = useSearchStore((s) => s.approximate);
  const selectedThumbnail = useSearchStore((s) => s.selectedThumbnail);
  const status = useSearchStore((s) => s.status);
  const error = useSearchStore((s) => s.error);
  const runSearch = useSearchStore((s) => s.runSearch);

  const scrollRef = useRef(null);
  const [selectedAlt, setSelectedAlt] = useState(null);

  const loading = status === 'loading';

  if (loading) return <LoadingCard messages={LOADING_MSGS} />;

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
      <Box mb="10px" ml="-10px">
        {/* Viewing an alternative is page state, not a navigation — real
            history's previous entry is the picker. Back must still mean one
            screen: first leave the alternative, only then leave the page. */}
        <BackButton
          fallback={ROUTES.select}
          label={selectedAlt ? 'Back to recommended' : 'Back to products'}
          onClick={selectedAlt ? backToRecommended : undefined}
        />
      </Box>

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
          {approximate && <ApproximateNotice variant="results" />}
          <ProductIdentity name={productName} sourceUrl={sourceUrl} thumbnail={selectedThumbnail} />
          <SavingsBar
            originalPrice={calcOriginal(result, activeRoute)}
            finalPrice={calcFinal(activeRoute)}
            saving={calcSaving(result, activeRoute)}
          />
          <RouteCard
            key={`${activeRoute.merchant}-${activeRoute.final_cost ?? ''}`}
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
