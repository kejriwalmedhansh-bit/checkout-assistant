/**
 * Client-only UI state (layout preferences). Persisted so the user's sidebar
 * choice survives reloads.
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export const useUiStore = create(
  persist(
    (set, get) => ({
      sidebarCollapsed: false,
      toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
      setSidebarCollapsed: (value) => set({ sidebarCollapsed: value }),

      // The "do this next" bubbles on the results page. On by default and shown
      // every visit — the voucher-then-checkout order catches out repeat users
      // too. Off is remembered for people who find them repetitive, which is
      // the honest answer to that rather than making them sit through it.
      hintsEnabled: true,
      toggleHints: () => set({ hintsEnabled: !get().hintsEnabled }),

      // First-visit walkthrough (see components/onboarding). Persisted so it
      // auto-shows exactly once per browser, ever — reopening it later from
      // the sidebar's "How it works" link doesn't touch this flag.
      onboardingSeen: false,
      markOnboardingSeen: () => set({ onboardingSeen: true }),
    }),
    {
      name: 'dealo-ui',
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
