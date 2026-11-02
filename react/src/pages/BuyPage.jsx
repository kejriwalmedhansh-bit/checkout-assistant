import { useEffect, useState } from 'react';
import { Box, Button, Text } from '@chakra-ui/react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { HubbleBrandCard } from '@/components/dashboard/BrandVoucherCard';
import { hubbleApi } from '@/api/hubble.api';
import { searchApi } from '@/api/search.api';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { outboundLink, track } from '@/utils/analytics';

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
 *
 * When Hubble has no voucher for the shop today (rates move between the
 * message and the tap), the person is not told "no": the shop-name search
 * finds whichever of Gyftr/Maximize/BuyHatke has the best rate and they are
 * sent there, with the rate named on the way (owner's call, 2 Nov 2026).
 */
const SOURCE_LABELS = { maximize: 'Maximize', buyhatke: 'BuyHatke', gyftr: 'Gyftr' };
const REDIRECT_AFTER_MS = 1800;

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

  const [state, setState] = useState({ status: HUBBLE_ON ? 'loading' : 'missing', brand: null, rival: null });
  const name = state.brand?.brand_name || state.rival?.brand_name || shopName(slug);

  usePageTitle(`Buy ${name} Gift Voucher`, `Buy a discounted ${name} gift voucher on Dealo. Pay by UPI, voucher in seconds.`);

  useEffect(() => {
    if (!HUBBLE_ON || !slug) return undefined;
    let live = true;
    setState({ status: 'loading', brand: null });
    hubbleApi
      .brand(null, null, { slug })
      .then((res) => {
        if (!live) return;
        track('Buy Link Opened', { slug, amount, src, available: Boolean(res.available) });
        setState(res.available ? { status: 'ready', brand: res.brand } : { status: 'missing', brand: null });
      })
      .catch(() => live && setState({ status: 'missing', brand: null }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  // No Hubble voucher today: find the best rival for this shop and go there.
  // With nothing to send them to either, the ordinary search page takes over.
  useEffect(() => {
    if (state.status !== 'missing') return undefined;
    let live = true;
    searchApi
      .candidates(shopName(slug))
      .then((data) => {
        if (!live) return;
        const v = data.mode === 'brand_voucher' && data.voucher?.voucher_url ? data.voucher : null;
        if (v) {
          setState({ status: 'redirect', brand: null, rival: v });
        } else {
          track('Buy Link Fallback Search', { slug, src });
          runSearch(shopName(slug));
          navigate(ROUTES.select);
        }
      })
      .catch(() => {
        if (!live) return;
        runSearch(shopName(slug));
        navigate(ROUTES.select);
      });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status]);

  const rivalUrl = state.rival ? outboundLink(state.rival.voucher_url, 'voucher_site', 'buy_link_fallback') : null;
  const rivalLabel = state.rival ? SOURCE_LABELS[state.rival.voucher_source] || 'the voucher site' : '';

  useEffect(() => {
    if (state.status !== 'redirect' || !rivalUrl) return undefined;
    track('Buy Link Redirected', { slug, src, source: state.rival.voucher_source, pct: state.rival.best_discount_pct });
    const t = setTimeout(() => window.location.assign(rivalUrl), REDIRECT_AFTER_MS);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status, rivalUrl]);

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
        <Text color="text3" fontSize="14px">
          Finding today’s best {name} rate…
        </Text>
      )}
      {state.status === 'redirect' && (
        <Box>
          <Text color="text2" fontSize="15px" mb="16px">
            Today the best {name} voucher is on {rivalLabel}
            {state.rival.best_discount_pct ? ` at ${state.rival.best_discount_pct}% off` : ''}. Taking you there…
          </Text>
          <Button as="a" href={rivalUrl} h="48px" px="22px" borderRadius="pill" bg="text" color="onBrand" fontWeight={800} _hover={{}}>
            Go to {rivalLabel} now
          </Button>
        </Box>
      )}
    </InfoPageShell>
  );
}
