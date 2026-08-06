/**
 * Client-only UI state (layout preferences). Persisted so the user's sidebar
 * choice survives reloads.
 */
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

import { TOUR_STEPS } from '@/components/onboarding/tourSteps';

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

      // Live guided tour (see components/onboarding/Spotlight + tourSteps).
      // Deliberately NOT persisted (see partialize below) — a reload should
      // never resume mid-tour in a stale state; it just quietly stops.
      onboardingSeen: false,
      markOnboardingSeen: () => set({ onboardingSeen: true }),
      tourActive: false,
      tourStep: 0,
      startTour: () => set({ tourActive: true, tourStep: 0 }),
      // "How it works" from the sidebar/header jumps straight to whichever
      // tour step belongs to the page the user is already on (see
      // AppLayout.jsx), instead of always restarting from step 0 on the
      // homepage — this is what keeps it contextual rather than a detour.
      startTourAtStep: (index) => set({ tourActive: true, tourStep: index }),
      advanceTour: () => {
        const next = get().tourStep + 1;
        if (next >= TOUR_STEPS.length) {
          set({ tourActive: false, tourStep: 0 });
          get().markOnboardingSeen();
        } else {
          set({ tourStep: next });
        }
      },
      skipTour: () => {
        set({ tourActive: false, tourStep: 0 });
        get().markOnboardingSeen();
      },
    }),
    {
      name: 'dealo-ui',
      storage: createJSONStorage(() => localStorage),
      // Tour state is intentionally excluded — see the comment above.
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        hintsEnabled: state.hintsEnabled,
        onboardingSeen: state.onboardingSeen,
      }),
    },
  ),
);
