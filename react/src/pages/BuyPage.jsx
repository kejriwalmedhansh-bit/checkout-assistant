import { useEffect, useState } from 'react';
import { Box, Button, Text } from '@chakra-ui/react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { HubbleBrandCard } from '@/components/dashboard/BrandVoucherCard';
import { hubbleApi } from '@/api/hubble.api';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { track } from '@/utils/analytics';

const HUBBLE_ON = import.meta.env.VITE_HUBBLE_ENABLED === 'true';

/**
 * /buy/<shop>?amount=2000&src=wa — the one page every other surface sends
 * people to. WhatsApp, the Chrome extension and the ChatGPT/Claude app can
 * tell someone a voucher is cheaper, but the login and Hubble's payment
 * window only run on the website, so they all hand over here with the shop
 * (and the amount, when they know it) already chosen.
 *
 * The sender has already decided this voucher is worth buying (the 2-point
 * rule runs where the link is made), so this page does not re-check it
 * against Gyftr/Maximize/BuyHatke: it asks Hubble for the voucher by slug
 * and shows the same card a shop-name search shows.
 */
function shopName(slug) {
  return slug
    .split('-')
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function BuyPage() {
  const { slug = '' } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const runSearch = useSearchStore((s) => s.runSearch);

  const params = new URLSearchParams(location.search);
  const amount = Number(params.get('amount')) || null;
  const src = params.get('src') || 'link';

  const [state, setState] = useState({ status: HUBBLE_ON ? 'loading' : 'missing', brand: null });
  const name = state.brand?.brand_name || shopName(slug);

  usePageTitle(`Buy ${name} Gift Voucher`, `Buy a discounted ${name} gift voucher on Dealo. Pay by UPI, voucher in seconds.`);

  useEffect(() => {
    if (!HUBBLE_ON || !slug) return undefined;
    let live = true;
    setState({ status: 'loading', brand: null });
    hubbleApi
      .brand(null, null, { slug })
      .then((res) => {
        if (!live) return;
        setState(res.available ? { status: 'ready', brand: res.brand } : { status: 'missing', brand: null });
        track('Buy Link Opened', { slug, amount, src, available: Boolean(res.available) });
      })
      .catch(() => live && setState({ status: 'missing', brand: null }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  const searchInstead = () => {
    track('Buy Link Fallback Search', { slug, src });
    runSearch(name);
    navigate(ROUTES.select);
  };

  return (
    <InfoPageShell title={`${name} Gift Voucher`} subtitle="Sold by Dealo. Pay by UPI, voucher in seconds." maxW="560px">
      {state.status === 'loading' && (
        <Text color="text3" fontSize="14px">
          Checking today’s rate…
        </Text>
      )}
      {state.status === 'ready' && (
        <HubbleBrandCard brand={state.brand} merchant={state.brand.brand_name} query={`buy:${slug}`} initialAmount={amount} />
      )}
      {state.status === 'missing' && (
        <Box>
          <Text color="text2" fontSize="15px" mb="16px">
            Dealo isn’t selling a {name} voucher right now. Search {name} and we’ll show the cheapest way to pay today.
          </Text>
          <Button onClick={searchInstead} h="48px" px="22px" borderRadius="pill" bg="text" color="onBrand" fontWeight={800} _hover={{}}>
            Search {name}
          </Button>
        </Box>
      )}
    </InfoPageShell>
  );
}
