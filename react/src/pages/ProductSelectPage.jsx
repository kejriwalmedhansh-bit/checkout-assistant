import { Box, Flex, Spinner, Stack, Text } from '@chakra-ui/react';
import { Navigate, useNavigate } from 'react-router-dom';

import Card from '@/components/common/Card';
import SearchBox from '@/components/common/SearchBox';
import { I } from '@/components/common/icons';
import ProductCandidateCard from '@/components/dashboard/ProductCandidateCard';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';

function ErrorBox({ message }) {
  return (
    <Flex
      align="flex-start"
      gap="10px"
      bg="brandSoft2"
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

export default function ProductSelectPage() {
  usePageTitle('Select a product');

  const navigate = useNavigate();
  const query = useSearchStore((s) => s.query);
  const candidates = useSearchStore((s) => s.candidates);
  const searchStatus = useSearchStore((s) => s.searchStatus);
  const status = useSearchStore((s) => s.status);
  const selectedToken = useSearchStore((s) => s.selectedToken);
  const error = useSearchStore((s) => s.error);
  const runSearch = useSearchStore((s) => s.runSearch);
  const selectProduct = useSearchStore((s) => s.selectProduct);

  // Direct load with no search in flight → back to home.
  if (searchStatus === 'idle') return <Navigate to={ROUTES.home} replace />;

  const rerun = (q) => runSearch(q);

  const handleSelect = (token, title, price, source) => {
    selectProduct(token, title, price, source); // fire-and-forget; ResultsPage shows its own loader
    navigate(ROUTES.results);
  };

  return (
    <Box maxW="680px" mx="auto">
      <Box mb="18px">
        <SearchBox
          initialValue={query}
          onSubmit={rerun}
          isLoading={searchStatus === 'loading'}
          size="md"
          buttonLabel="Search"
        />
      </Box>

      {searchStatus === 'loading' && (
        <Flex justify="center" py="48px">
          <Spinner color="brand" size="lg" thickness="3px" />
        </Flex>
      )}

      {searchStatus === 'error' && <ErrorBox message={error || 'Search failed.'} />}

      {searchStatus === 'success' && candidates.length === 0 && (
        <Card p="32px 22px">
          <Flex direction="column" align="center" gap="10px" textAlign="center">
            <Flex
              w="44px"
              h="44px"
              borderRadius="12px"
              bg="surface3"
              color="text3"
              align="center"
              justify="center"
            >
              <I.search size={20} />
            </Flex>
            <Text fontSize="14px" color="text2">
              No products found. Try a different search.
            </Text>
          </Flex>
        </Card>
      )}

      {searchStatus === 'success' && candidates.length > 0 && (
        <>
          <Text fontSize="13px" color="text3" mb="12px">
            Select the exact product you want — we&apos;ll find the cheapest way to buy it.
          </Text>
          <Stack spacing="10px">
            {candidates.map((p, i) => (
              <ProductCandidateCard
                key={p.product_token || i}
                product={p}
                onSelect={handleSelect}
                isSelecting={status === 'loading' && selectedToken === p.product_token}
              />
            ))}
          </Stack>
        </>
      )}
    </Box>
  );
}
