/**
 * Voucher endpoints.
 *
 * TODO: the backend voucher routes may still be in progress. The Vouchers pages
 * are written to degrade gracefully (loading / empty / error) if these 404.
 */
import { apiClient } from './client';

export const vouchersApi = {
  /** List Gyftr voucher brands. `params` is an optional query object. */
  list: async (params) => {
    const { data } = await apiClient.get('/vouchers', { params });
    return data;
  },

  /** Fetch a single voucher brand by slug. */
  detail: async (slug) => {
    const { data } = await apiClient.get(`/vouchers/${slug}`);
    return data;
  },
};
