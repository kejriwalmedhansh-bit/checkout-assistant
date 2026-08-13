/** POST /card-options {route} -> { options: [{card_name, voucher_discount, cashback, apply_url}] }
 *  The frontend already holds the full route object from /routes, so it's
 *  sent back as-is rather than looked up by a token — Dealo keeps no route
 *  state server-side between requests.
 */
import { apiClient } from './client';

export const cardOptionsApi = {
  forRoute: async (route) => {
    const { data } = await apiClient.post('/card-options', route);
    return data;
  },
};
