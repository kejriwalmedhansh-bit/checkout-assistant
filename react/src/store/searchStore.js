/**
 * Two-step search state.
 *   Step 1 (runSearch)     -> candidate products; tracked by `searchStatus`.
 *   Step 2 (selectProduct) -> full route result; tracked by `status`.
 * query + candidates + selectedToken + result are persisted (so reloads keep
 * the view); the two status fields and error are transient.
 *
 * Persisted state also carries `persistedAt` (set on every successful
 * search/select) and is discarded on rehydration once it's older than
 * STALE_AFTER_MS — a reload seconds or minutes later still keeps your place
 * (the original intent), but reopening a genuinely old tab/session no longer
 * silently resurfaces a stale product with no fresh search behind it.
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import { searchApi } from '@/api/search.api';
import { extractErrorMessage } from '@/utils/errors';
import { track } from '@/utils/analytics';
import { originalPrice, finalPrice, saving } from '@/utils/format';

const STALE_AFTER_MS = 45 * 60 * 1000; // 45 minutes

export const useSearchStore = create(
  persist(
    (set, get) => ({
      query: '',
      candidates: [],
      // True when nothing matched the search exactly and these are the closest
      // trustworthy matches instead (e.g. "AirPods Pro Max", which isn't a real
      // product). The picker says so rather than passing them off as the thing
      // that was asked for.
      approximate: false,
      // 'products' (normal picker) or 'brand_voucher' (query named a Gyftr
      // brand directly — L1 is skipped, `voucher` is the brand's raw deal).
      mode: 'products',
      voucher: null,
      selectedToken: null,
      selectedThumbnail: null,
      result: null,
      searchStatus: 'idle', // step 1: 'idle' | 'loading' | 'success' | 'error'
      status: 'idle', // step 2: 'idle' | 'loading' | 'success' | 'error'
      error: null,
      persistedAt: null, // Date.now() of the last successful search/select; see STALE_AFTER_MS above

      // Step 1 — fetch candidate products for a query.
      runSearch: async (query) => {
        const q = (query || '').trim();
        if (!q) return;
        set({
          query: q,
          candidates: [],
          approximate: false,
          mode: 'products',
          voucher: null,
          selectedToken: null,
          result: null,
          searchStatus: 'loading',
          status: 'idle',
          error: null,
        });
        try {
          const data = await searchApi.candidates(q);
          if (data.error) {
            set({ searchStatus: 'error', error: data.error });
          } else {
            set({
              candidates: data.products || [],
              approximate: Boolean(data.approximate),
              mode: data.mode || 'products',
              voucher: data.voucher || null,
              searchStatus: 'success',
              error: null,
              persistedAt: Date.now(),
            });
            track('Searched', {
              query: q,
              mode: data.mode || 'products',
              result_count: (data.products || []).length,
            });
          }
        } catch (err) {
          set({ searchStatus: 'error', error: extractErrorMessage(err) });
        }
      },

      // Step 2 — build routes for a chosen product token. `title` (the
      // candidate's own title) drives a focused re-search for that exact
      // variant server-side, rather than trusting just this one listing.
      selectProduct: async (token, title = '', price = null, source = '', thumbnail = null) => {
        if (!token) return;
        set({ selectedToken: token, selectedThumbnail: thumbnail, result: null, status: 'loading', error: null });
        track('Selected Product', { query: get().query, title, source });
        try {
          const result = await searchApi.routes(token, get().query, title, price, source);
          set({ result, status: 'success', error: null, persistedAt: Date.now() });
          const rec = result?.routes?.recommended;
          if (rec) {
            // Same original/final/discount math the results page itself
            // displays (utils/format.js), so this event always matches
            // exactly what the user was shown on screen.
            track('Viewed Deal', {
              query: get().query,
              merchant: rec.merchant,
              has_voucher: Boolean(rec.voucher),
              final_cost: rec.final_cost ?? null,
              alternatives_count: result?.routes?.alternatives?.length ?? 0,
              original_price: originalPrice(result, rec),
              final_price: finalPrice(rec),
              discount: saving(result, rec),
              // Same source label Journey.jsx shows the user ("via Maximize" /
              // "via Gyftr"); null when the route has no voucher at all.
              voucher_aggregator: rec.voucher ? (rec.voucher.voucher_source === 'maximize' ? 'Maximize' : 'Gyftr') : null,
            });
          }
        } catch (err) {
          set({ result: null, status: 'error', error: extractErrorMessage(err) });
        }
      },

      reset: () =>
        set({
          query: '',
          candidates: [],
          approximate: false,
          mode: 'products',
          voucher: null,
          selectedToken: null,
          selectedThumbnail: null,
          result: null,
          searchStatus: 'idle',
          status: 'idle',
          error: null,
          persistedAt: null,
        }),
    }),
    {
      name: 'dealo-search',
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        query: s.query,
        candidates: s.candidates,
        approximate: s.approximate,
        mode: s.mode,
        voucher: s.voucher,
        selectedToken: s.selectedToken,
        selectedThumbnail: s.selectedThumbnail,
        result: s.result,
        persistedAt: s.persistedAt,
      }),
      // A rehydrated `result`/`candidates` older than STALE_AFTER_MS is
      // reset immediately, before any page can render it — status fields
      // aren't persisted (see file header), so without this an old session
      // reopened after a long gap would otherwise render a stale product
      // with searchStatus/status back at 'idle', no fresh search behind it.
      onRehydrateStorage: () => (state) => {
        if (state?.persistedAt && Date.now() - state.persistedAt > STALE_AFTER_MS) {
          state.reset();
        }
      },
    },
  ),
);
