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

  /** Step 2 — build routes for a chosen product_token. `title` (the picked
   * candidate's own title) drives a focused re-search for that exact variant
   * server-side — pass it whenever available. `price`/`source` are the exact
   * price/seller the Product Picker displayed for this token — passing them
   * lets the backend pin that listing into the final result instead of
   * silently trusting a different, broader lookup for the same merchant.
   * Returns the result object. */
  routes: async (productToken, query = '', title = '', price = null, source = '') => {
    const { data } = await apiClient.post('/routes', {
      product_token: productToken,
      query,
      title,
      price,
      source,
    });
    return data;
  },
};
