/** Two-step search surface.
 *  Step 1: POST /search {query}          -> candidate product list
 *  Step 2: POST /routes {product_token}  -> full route/voucher/card result
 */
import { apiClient } from './client';

export const searchApi = {
  /** Step 1 — google_shopping search. Returns { query, products[], error }. */
  candidates: async (query) => {
    const { data } = await apiClient.post('/search', { query });
    return data;
  },

  /** Step 2 — build routes for a chosen product_token. Returns the result object. */
  routes: async (productToken, query = '') => {
    const { data } = await apiClient.post('/routes', {
      product_token: productToken,
      query,
    });
    return data;
  },
};
