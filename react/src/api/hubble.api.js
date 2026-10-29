/** Buying a voucher inside Dealo through Hubble (see src/api/routers/hubble.py). */
import { apiClient } from './client';

export const hubbleApi = {
  /** GET /hubble/offer -> { available, offer } */
  offer: async (merchant, price, inStore = false, bestPct = null) => {
    const params = { merchant, price: Math.round(price), in_store: inStore };
    if (bestPct != null) params.best_pct = bestPct;
    const { data } = await apiClient.get('/hubble/offer', { params });
    return data;
  },
  /** GET /hubble/brand -> { available, brand:{discount_pct, cards, min_amount, max_amount, typed, in_store} } — shop-name search, no cart yet. */
  brand: async (merchant, bestPct = null) => {
    const params = { merchant };
    if (bestPct != null) params.best_pct = bestPct;
    const { data } = await apiClient.get('/hubble/brand', { params });
    return data;
  },
  /** POST /hubble/session -> { url, offer } — the link that opens Hubble on the pay step. */
  session: async (body) => {
    const { data } = await apiClient.post('/hubble/session', body);
    return data;
  },
  /** GET /hubble/orders/latest -> { found, brand, vouchers:[{code,pin,amount}] } */
  latestOrder: async (idToken) => {
    const { data } = await apiClient.get('/hubble/orders/latest', { headers: { Authorization: `Bearer ${idToken}` } });
    return data;
  },
};
