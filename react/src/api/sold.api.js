/**
 * Dealo's own Buy button, whichever seller stands behind it (Hubble or
 * Maximize; see src/api/routers/sold.py). The server picks the seller with
 * the higher rate to the shopper; the offer carries `seller`, and the
 * session / latest-order calls go to that seller's own endpoints.
 */
import { apiClient } from './client';

export const soldApi = {
  /** GET /sold/offer -> { available, offer } with offer.seller */
  offer: async (merchant, price, inStore = false, bestPct = null) => {
    const params = { merchant, price: Math.round(price), in_store: inStore };
    if (bestPct != null) params.best_pct = bestPct;
    const { data } = await apiClient.get('/sold/offer', { params });
    return data;
  },
  /** GET /sold/brand -> { available, brand } with brand.seller — shop-name search, no cart yet. */
  brand: async (merchant, bestPct = null) => {
    const params = { merchant };
    if (bestPct != null) params.best_pct = bestPct;
    const { data } = await apiClient.get('/sold/brand', { params });
    return data;
  },
  /** POST /<seller>/session -> { url, offer } — the frame address for this shopper. */
  session: async (seller, body) => {
    const { data } = await apiClient.post(`/${seller || 'hubble'}/session`, body);
    return data;
  },
  /** GET /<seller>/orders/latest -> { found, brand, vouchers:[{code,pin,amount}] } */
  latestOrder: async (seller, idToken) => {
    const { data } = await apiClient.get(`/${seller || 'hubble'}/orders/latest`, {
      headers: { Authorization: `Bearer ${idToken}` },
    });
    return data;
  },
};

/** Which frame hosts may talk to the page, per seller (postMessage origin check). */
export const SELLER_FRAME_HOSTS = {
  hubble: /myhubble\.money$/,
  maximize: /(^|\.)maximize\.money$|^98\.130\.140\.6$/,
};

export const SELLER_NAMES = { hubble: 'Hubble', maximize: 'Maximize' };
