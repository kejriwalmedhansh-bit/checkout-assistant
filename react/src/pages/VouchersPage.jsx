import { useEffect, useState } from 'react';
import { Box, SimpleGrid, Spinner, Text, Flex } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import Topbar from '@/components/layout/Topbar';
import VoucherCard from '@/components/dashboard/VoucherCard';
import { vouchersApi } from '@/api/vouchers.api';
import { usePageTitle } from '@/hooks/usePageTitle';
import { extractErrorMessage } from '@/utils/errors';

/** Normalize whatever the (in-progress) backend returns into an array. */
function toList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.vouchers)) return data.vouchers;
  if (Array.isArray(data?.brands)) return data.brands;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

export default function VouchersPage() {
  usePageTitle('Vouchers');
  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'error'
  const [vouchers, setVouchers] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await vouchersApi.list();
        if (!alive) return;
        setVouchers(toList(data));
        setStatus('success');
      } catch (err) {
        if (!alive) return;
        setError(extractErrorMessage(err));
        setStatus('error');
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <Box>
      <Topbar title="Vouchers" meta="Gyftr voucher brands with UPI discounts." />

      {status === 'loading' && (
        <Flex justify="center" py="48px">
          <Spinner color="brand" size="lg" thickness="3px" />
        </Flex>
      )}

      {status === 'error' && (
        <Card p="22px">
          <Text fontSize="14px" fontWeight={600} color="text" mb="4px">
            Vouchers aren&apos;t available right now
          </Text>
          <Text fontSize="13px" color="text2">
            {error}
          </Text>
        </Card>
      )}

      {status === 'success' && vouchers.length === 0 && (
        <Card p="22px">
          <Text fontSize="14px" color="text2">
            No vouchers to show yet.
          </Text>
        </Card>
      )}

      {status === 'success' && vouchers.length > 0 && (
        <SimpleGrid columns={{ base: 1, sm: 2, lg: 3 }} spacing="12px">
          {vouchers.map((v, i) => (
            <VoucherCard key={v.slug || v.id || v.brand || i} voucher={v} />
          ))}
        </SimpleGrid>
      )}
    </Box>
  );
}
