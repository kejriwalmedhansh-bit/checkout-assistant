/**
 * Two-step search state.
 *   Step 1 (runSearch)     -> candidate products; tracked by `searchStatus`.
 *   Step 2 (selectProduct) -> full route result; tracked by `status`.
 * query + candidates + selectedToken + result are persisted (so reloads keep
 * the view); the two status fields and error are transient.
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import { searchApi } from '@/api/search.api';
import { extractErrorMessage } from '@/utils/errors';

export const useSearchStore = create(
  persist(
    (set, get) => ({
      query: '',
      candidates: [],
      selectedToken: null,
      result: null,
      searchStatus: 'idle', // step 1: 'idle' | 'loading' | 'success' | 'error'
      status: 'idle', // step 2: 'idle' | 'loading' | 'success' | 'error'
      error: null,

      // Step 1 — fetch candidate products for a query.
      runSearch: async (query) => {
        const q = (query || '').trim();
        if (!q) return;
        set({
          query: q,
          candidates: [],
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
            set({ candidates: data.products || [], searchStatus: 'success', error: null });
          }
        } catch (err) {
          set({ searchStatus: 'error', error: extractErrorMessage(err) });
        }
      },

      // Step 2 — build routes for a chosen product token. `title` (the
      // candidate's own title) drives a focused re-search for that exact
      // variant server-side, rather than trusting just this one listing.
      selectProduct: async (token, title = '') => {
        if (!token) return;
        set({ selectedToken: token, result: null, status: 'loading', error: null });
        try {
          const result = await searchApi.routes(token, get().query, title);
          set({ result, status: 'success', error: null });
        } catch (err) {
          set({ result: null, status: 'error', error: extractErrorMessage(err) });
        }
      },

      reset: () =>
        set({
          query: '',
          candidates: [],
          selectedToken: null,
          result: null,
          searchStatus: 'idle',
          status: 'idle',
          error: null,
        }),
    }),
    {
      name: 'dealo-search',
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        query: s.query,
        candidates: s.candidates,
        selectedToken: s.selectedToken,
        result: s.result,
      }),
    },
  ),
);
