/** Buying a voucher inside Dealo through Hubble (see src/api/routers/hubble.py). */
import { apiClient } from './client';

export const hubbleApi = {
  /** GET /hubble/offer -> { available, offer } */
  offer: async (merchant, price) => {
    const { data } = await apiClient.get('/hubble/offer', { params: { merchant, price: Math.round(price) } });
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
