import { useEffect, useState } from 'react';
import { Box, Button, Flex, ListItem, Spinner, Text, UnorderedList } from '@chakra-ui/react';
import { useNavigate, useParams } from 'react-router-dom';

import Card from '@/components/common/Card';
import Chip from '@/components/common/Chip';
import Topbar from '@/components/layout/Topbar';
import { I } from '@/components/common/icons';
import { vouchersApi } from '@/api/vouchers.api';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cleanInstructions } from '@/utils/format';
import { extractErrorMessage } from '@/utils/errors';
import { ROUTES } from '@/routes/paths';

export default function VoucherDetailPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('loading');
  const [voucher, setVoucher] = useState(null);
  const [error, setError] = useState(null);

  const name = voucher?.brand || voucher?.merchant || voucher?.name || slug;
  usePageTitle(name || 'Voucher');

  useEffect(() => {
    let alive = true;
    setStatus('loading');
    (async () => {
      try {
        const data = await vouchersApi.detail(slug);
        if (!alive) return;
        setVoucher(data);
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
  }, [slug]);

  const terms = cleanInstructions(
    voucher?.redemption_restrictions || voucher?.redemption_instructions || voucher?.terms || [],
  );
  const pct = voucher?.upi?.pct ?? voucher?.discount_pct ?? voucher?.best_discount ?? null;

  return (
    <Box>
      <Topbar title={name}>
        <Button variant="ghost" leftIcon={<I.arrowLeft size={16} />} onClick={() => navigate(ROUTES.vouchers)}>
          All vouchers
        </Button>
      </Topbar>

      {status === 'loading' && (
        <Flex justify="center" py="48px">
          <Spinner color="brand" size="lg" thickness="3px" />
        </Flex>
      )}

      {status === 'error' && (
        <Card p="22px">
          <Text fontSize="14px" fontWeight={600} color="text" mb="4px">
            Couldn&apos;t load this voucher
          </Text>
          <Text fontSize="13px" color="text2">
            {error}
          </Text>
        </Card>
      )}

      {status === 'success' && voucher && (
        <Flex direction="column" gap="14px">
          <Card p="20px">
            <Flex align="center" gap="14px">
              <Flex
                w="46px"
                h="46px"
                borderRadius="12px"
                bg="brandSoft"
                color="brand"
                align="center"
                justify="center"
                flex="0 0 auto"
              >
                <I.ticket size={22} />
              </Flex>
              <Box>
                <Text fontSize="18px" fontWeight={700} color="text">
                  {name}
                </Text>
                {pct != null && (
                  <Chip tone="green" mono={false} mt="6px">
                    {pct}% off via UPI
                  </Chip>
                )}
              </Box>
            </Flex>
          </Card>

          {terms.length > 0 && (
            <Card p="20px">
              <Text fontSize="13px" fontWeight={700} color="text" mb="10px">
                Terms &amp; redemption
              </Text>
              <UnorderedList spacing="6px" pl="18px" m={0}>
                {terms.map((t, i) => (
                  <ListItem key={i} fontSize="13px" color="text2" lineHeight={1.55}>
                    {t}
                  </ListItem>
                ))}
              </UnorderedList>
            </Card>
          )}
        </Flex>
      )}
    </Box>
  );
}
