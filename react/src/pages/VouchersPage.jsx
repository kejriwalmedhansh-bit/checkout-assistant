import { useEffect, useState } from 'react';
import { Box, SimpleGrid, Spinner, Text, Flex } from '@chakra-ui/react';

import Card from '@/components/common/Card';
import Topbar from '@/components/layout/Topbar';
import VoucherCard from '@/components/dashboard/VoucherCard';
import { I } from '@/components/common/icons';
import { vouchersApi } from '@/api/vouchers.api';
import { usePageTitle } from '@/hooks/usePageTitle';
import { extractErrorMessage } from '@/utils/errors';

function StateCard({ icon, title, subtitle, tone = 'text2' }) {
  return (
    <Card p="32px 22px">
      <Flex direction="column" align="center" gap="10px" textAlign="center">
        <Flex
          w="44px"
          h="44px"
          borderRadius="12px"
          bg="surface3"
          color={tone}
          align="center"
          justify="center"
        >
          {icon}
        </Flex>
        {title && (
          <Text fontSize="14px" fontWeight={600} color="text">
            {title}
          </Text>
        )}
        <Text fontSize="14px" color="text2">
          {subtitle}
        </Text>
      </Flex>
    </Card>
  );
}

/** Normalize whatever the (in-progress) backend returns into an array. */
function toList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.vouchers)) return data.vouchers;
  if (Array.isArray(data?.brands)) return data.brands;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

export default function VouchersPage() {
  usePageTitle('Gift Vouchers');
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
      <Topbar title="Gift Vouchers" meta="Real store gift cards, sold at a discount." />

      {status === 'loading' && (
        <Flex justify="center" py="48px">
          <Spinner color="brand" size="lg" thickness="3px" />
        </Flex>
      )}

      {status === 'error' && (
        <StateCard
          icon={<I.alert size={20} />}
          tone="danger"
          title="Gift vouchers aren't available right now"
          subtitle={error}
        />
      )}

      {status === 'success' && vouchers.length === 0 && (
        <StateCard icon={<I.ticket size={20} />} subtitle="No gift vouchers to show yet." />
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
