import { useRef, useState } from 'react';
import { Box, Flex } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';
import { Navigate, useNavigate } from 'react-router-dom';

import BackButton from '@/components/common/BackButton';
import ErrorBox from '@/components/common/ErrorBox';
import LoadingCard from '@/components/common/LoadingCard';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import BestPriceConfirmed from '@/components/dashboard/BestPriceConfirmed';
import ProductIdentity from '@/components/dashboard/ProductIdentity';
import SavingsBar from '@/components/dashboard/SavingsBar';
import RouteWire from '@/components/dashboard/RouteWire';
import RouteCard from '@/components/dashboard/RouteCard';
import CardFomo from '@/components/dashboard/CardFomo';
import AlternativesToggle from '@/components/dashboard/AlternativesToggle';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { affiliateUrl, finalPrice as calcFinal, originalPrice as calcOriginal, saving as calcSaving } from '@/utils/format';

// Shown one at a time while the route is being built — this is Dealo's real
// trust gap (buying a gift voucher is an unfamiliar concept to most users,
// per PRODUCT.md), so the wait is spent addressing that instead of a generic
// "please wait" status line.
const ROUTE_TIPS = [
  'Vouchers are real store credit — not a trick.',
  "We're not the seller. We just find your best deal.",
  "Read the gift voucher site's redemption steps first.",
  'Follow the steps in order for the full discount.',
  'In-store? Ask the cashier if they take vouchers first.',
];

export default function ResultsPage() {
  usePageTitle('Results');

  const navigate = useNavigate();
  const prefersReduced = useReducedMotion();
  const query = useSearchStore((s) => s.query);
  const result = useSearchStore((s) => s.result);
  const selectedThumbnail = useSearchStore((s) => s.selectedThumbnail);
  const status = useSearchStore((s) => s.status);
  const error = useSearchStore((s) => s.error);
  const runSearch = useSearchStore((s) => s.runSearch);

  const scrollRef = useRef(null);
  const [selectedAlt, setSelectedAlt] = useState(null);
  // Collapsed by default: on a phone, the back button + full search box
  // used to stack into ~100px of chrome above the fold on every single
  // visit, even though re-running a search from here is rare. Opening it is
  // one tap away; nothing about the ability to search again is lost.
  const [searchOpen, setSearchOpen] = useState(false);

  const loading = status === 'loading';

  if (loading) return <LoadingCard tips={ROUTE_TIPS} />;

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
  // The exact vendor product page — the URL the user pasted, when they
  // pasted one, or otherwise the recommended (or picked-alternative)
  // route's own merchant link. Either way, this is "click through and see
  // the real listing," not just a name string — the photo and product name
  // both link here so someone can verify it's the right item before buying
  // a voucher for it.
  const vendorLink = activeRoute?.sellers?.[0]?.link;
  const sourceUrl = result?.mode === 'url' ? query : vendorLink ? affiliateUrl(vendorLink) : null;

  return (
    <Box ref={scrollRef} maxW="640px" mx="auto">
      <Flex align="center" gap="6px" mb="8px">
        {/* Viewing an alternative is page state, not a navigation — real
            history's previous entry is the picker. Back must still mean one
            screen: first leave the alternative, only then leave the page. */}
        <BackButton
          fallback={ROUTES.select}
          label={selectedAlt ? 'Back to recommended' : 'Back to products'}
          onClick={selectedAlt ? backToRecommended : undefined}
          iconOnly
        />
        {!searchOpen && (
          <Box
            as="button"
            type="button"
            onClick={() => setSearchOpen(true)}
            display="flex"
            alignItems="center"
            gap="6px"
            h="32px"
            px="10px"
            flex={1}
            minW={0}
            borderRadius="xs"
            color="text2"
            fontSize="12.5px"
            fontWeight={600}
            _hover={{ bg: 'surface3' }}
          >
            <I.search size={14} />
            Search again
          </Box>
        )}
      </Flex>

      {searchOpen && (
        <Box mb="18px">
          <Flex justify="flex-end" mb="6px">
            <Box
              as="button"
              type="button"
              onClick={() => setSearchOpen(false)}
              fontSize="12px"
              fontWeight={600}
              color="text2"
              _hover={{ color: 'text' }}
            >
              Cancel
            </Box>
          </Flex>
          <SearchBox
            initialValue={query}
            onSubmit={rerun}
            isLoading={loading}
            size="md"
            buttonLabel="Search again"
          />
        </Box>
      )}

      {error || result?.error ? (
        <ErrorBox message={error || result.error} />
      ) : !rec ? (
        <ErrorBox message="No results found. Try a different search." />
      ) : (
        // The loader (pulsing dots) unmounts and this whole block mounts in
        // its place the instant a search resolves — without this, that's a
        // hard cut on every single search, the most-repeated moment in the
        // product. A quick fade + rise bridges it instead of snapping.
        <motion.div
          initial={prefersReduced ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          <Flex direction="column" gap="14px">
            <ProductIdentity name={productName} sourceUrl={sourceUrl} thumbnail={selectedThumbnail} />
            {/* Savings node + wire + step card render as one continuous
                unit (zero gap) — the reward is the first stop on the same
                route the steps below continue, not a separate block a
                user has to scroll past to find what to do. */}
            <Flex direction="column" gap={0}>
              {calcSaving(result, activeRoute) > 0 ? (
                <>
                  <SavingsBar
                    originalPrice={calcOriginal(result, activeRoute)}
                    finalPrice={calcFinal(activeRoute)}
                    saving={calcSaving(result, activeRoute)}
                    voucherRequired={!!activeRoute.voucher}
                  />
                  <RouteWire animated={!prefersReduced} />
                </>
              ) : (
                <BestPriceConfirmed comparedCount={result?.routes?.compared_count} />
              )}
              <RouteCard
                key={`${activeRoute.merchant}-${activeRoute.final_cost ?? ''}`}
                result={result}
                rec={activeRoute}
                isAlt={!!selectedAlt}
                onBack={backToRecommended}
              />
            </Flex>
            <CardFomo cardFomo={activeRoute.card_fomo} />
            <AlternativesToggle
              alternatives={result.routes?.alternatives}
              onSelect={selectAlt}
              selectedMerchant={selectedAlt?.merchant}
            />
          </Flex>
        </motion.div>
      )}
    </Box>
  );
}
