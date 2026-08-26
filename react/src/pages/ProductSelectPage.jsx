import { useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';
import { Navigate, useNavigate } from 'react-router-dom';

import BackButton from '@/components/common/BackButton';
import Card from '@/components/common/Card';
import ErrorBox from '@/components/common/ErrorBox';
import LoadingCard from '@/components/common/LoadingCard';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import BrandVoucherCard from '@/components/dashboard/BrandVoucherCard';
import LowConfidenceNotice from '@/components/dashboard/LowConfidenceNotice';
import ProductCandidateCard from '@/components/dashboard/ProductCandidateCard';
import ProductQuickView from '@/components/dashboard/ProductQuickView';
import { usePageTitle } from '@/hooks/usePageTitle';
import { gradients } from '@/theme/foundations/colors';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { useUiStore } from '@/store/uiStore';

// Shown while candidates are being fetched, before the picker appears.
const PICKER_TIPS = [
  'Pick the exact match — it decides your price.',
  'Not right? Add the brand name and search again.',
];

const PER_PAGE = 8;

export default function ProductSelectPage() {
  usePageTitle('Select a product');
  const prefersReduced = useReducedMotion();
  const heroGlow = gradients.promptHero;

  const navigate = useNavigate();
  const query = useSearchStore((s) => s.query);
  const candidates = useSearchStore((s) => s.candidates);
  const mode = useSearchStore((s) => s.mode);
  const voucher = useSearchStore((s) => s.voucher);
  const searchStatus = useSearchStore((s) => s.searchStatus);
  const status = useSearchStore((s) => s.status);
  const selectedToken = useSearchStore((s) => s.selectedToken);
  const approximate = useSearchStore((s) => s.approximate);
  const error = useSearchStore((s) => s.error);
  const runSearch = useSearchStore((s) => s.runSearch);
  const selectProduct = useSearchStore((s) => s.selectProduct);
  const [quickViewIndex, setQuickViewIndex] = useState(null);
  const [page, setPage] = useState(1);
  const tourActive = useUiStore((s) => s.tourActive);
  const advanceTour = useUiStore((s) => s.advanceTour);

  // A fresh search result set always starts back on page 1.
  useEffect(() => {
    setPage(1);
  }, [candidates]);

  // Direct load with no search in flight → back to home.
  if (searchStatus === 'idle') return <Navigate to={ROUTES.home} replace />;

  const rerun = (q) => runSearch(q);

  const pageCount = Math.max(1, Math.ceil(candidates.length / PER_PAGE));
  const pageStart = (page - 1) * PER_PAGE;
  const pageCandidates = candidates.slice(pageStart, pageStart + PER_PAGE);

  const handleSelect = (token, title, price, source, thumbnail) => {
    if (tourActive) advanceTour();
    selectProduct(token, title, price, source, thumbnail); // fire-and-forget; ResultsPage shows its own loader
    navigate(ROUTES.results);
  };

  return (
    <Box position="relative">
      {/* Same fix as SearchPage.jsx's hero glow: this decorative div is
          deliberately 130% wide (bleeds past the edges on wide screens), so
          it needs its own clipped, pointer-events-none layer — otherwise it
          creates real horizontal page overflow on any phone-width viewport
          (confirmed: a 595px-wide element on a 500px viewport here, the
          "weird black rectangle" on the right edge users reported). */}
      <Box position="absolute" inset={0} overflow="hidden" pointerEvents="none" zIndex={0}>
        <Box
          position="absolute"
          top="-120px"
          left="50%"
          transform="translateX(-50%)"
          w="min(900px, 130%)"
          h="320px"
          bgImage={heroGlow}
        />
      </Box>

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
          <Text as="h1" fontSize={{ base: '20px', md: '24px' }} fontWeight={800} letterSpacing="-.02em" color="text" noOfLines={1} m={0}>
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

        {searchStatus === 'loading' && <LoadingCard tips={PICKER_TIPS} />}

        {searchStatus === 'error' && <ErrorBox message={error || 'Search failed.'} />}

        {searchStatus === 'success' && mode === 'brand_voucher' && voucher && (
          <motion.div
            initial={prefersReduced ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            <BrandVoucherCard voucher={voucher} />
          </motion.div>
        )}

        {searchStatus === 'success' && mode !== 'brand_voucher' && candidates.length === 0 && (
          <motion.div
            initial={prefersReduced ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
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
                    Try adding the brand name, or search with different words.
                  </Text>
                </Box>
              </Flex>
            </Card>
          </motion.div>
        )}

        {searchStatus === 'success' && mode !== 'brand_voucher' && candidates.length > 0 && (
          <>
            {approximate && <LowConfidenceNotice />}
            <Text fontSize="13px" color="text3" mb="12px">
              Select the exact product you want — we&apos;ll find the cheapest way to buy it.
            </Text>
            <Flex direction="column" gap="10px">
              {pageCandidates.map((p, i) => {
                const globalIndex = pageStart + i;
                return (
                  <motion.div
                    key={p.product_token || globalIndex}
                    initial={prefersReduced ? false : { opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, delay: Math.min(i * 0.045, 0.4), ease: [0.16, 1, 0.3, 1] }}
                  >
                    <ProductCandidateCard
                      product={p}
                      onSelect={handleSelect}
                      onEnlarge={() => setQuickViewIndex(i)}
                      tourId={globalIndex === 0 ? 'picker-first-thumbnail' : undefined}
                      isSelecting={status === 'loading' && selectedToken === p.product_token}
                    />
                  </motion.div>
                );
              })}
            </Flex>

            {pageCount > 1 && (
              <Flex justify="center" align="center" gap="6px" mt="18px">
                <PageButton disabled={page === 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                  <Box transform="rotate(180deg)">
                    <I.chevRight size={14} />
                  </Box>
                </PageButton>
                {Array.from({ length: pageCount }, (_, i) => i + 1).map((p) => (
                  <PageButton key={p} active={p === page} onClick={() => setPage(p)}>
                    {p}
                  </PageButton>
                ))}
                <PageButton disabled={page === pageCount} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                  <I.chevRight size={14} />
                </PageButton>
              </Flex>
            )}
          </>
        )}

        {quickViewIndex != null && (
          <ProductQuickView
            products={pageCandidates}
            index={quickViewIndex}
            onIndexChange={setQuickViewIndex}
            onSelect={handleSelect}
            onClose={() => setQuickViewIndex(null)}
          />
        )}
      </Box>
    </Box>
  );
}

// One numbered pill in the picker's page strip (also used for the ‹ / › arrows).
function PageButton({ active, disabled, children, ...rest }) {
  return (
    <Flex
      as="button"
      type="button"
      disabled={disabled}
      minW="34px"
      h="34px"
      px="6px"
      align="center"
      justify="center"
      borderRadius="999px"
      border="1px solid"
      borderColor={active ? 'brand' : 'border'}
      bg={active ? 'brand' : 'surface'}
      color={active ? 'onBrand' : 'text2'}
      fontSize="13px"
      fontWeight={700}
      cursor={disabled ? 'default' : 'pointer'}
      opacity={disabled ? 0.35 : 1}
      transition="background .18s ease, color .18s ease, border-color .18s ease"
      _hover={disabled ? undefined : { borderColor: active ? 'brand' : 'borderStrong' }}
      _focusVisible={{ outline: '2px solid', outlineColor: 'brand', outlineOffset: '2px' }}
      {...rest}
    >
      {children}
    </Flex>
  );
}
