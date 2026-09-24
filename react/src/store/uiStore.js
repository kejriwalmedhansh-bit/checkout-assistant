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

      // The tutorial video popup (see onboarding/TutorialVideoModal). Shown
      // automatically once per first-time visitor on the home page; "How it
      // works" in the sidebar/header (AppLayout.jsx) reopens it manually from
      // any page. `tutorialOpen` itself isn't persisted (see partialize below)
      // — a reload should never resume with the popup still open.
      onboardingSeen: false,
      markOnboardingSeen: () => set({ onboardingSeen: true }),
      tutorialOpen: false,
      openTutorial: () => set({ tutorialOpen: true }),
      closeTutorial: () => {
        set({ tutorialOpen: false });
        get().markOnboardingSeen();
      },

      // Set the first time a Buy button on the steps is tapped this visit.
      // Anyone who tapped one isn't a drop-off, so DropOffQuestion never asks
      // them. Not persisted: it describes this visit only.
      buyLinkClicked: false,
      markBuyLinkClicked: () => set({ buyLinkClicked: true }),
    }),
    {
      name: 'dealo-ui',
      storage: createJSONStorage(() => localStorage),
      // `tutorialOpen`/`buyLinkClicked` are intentionally excluded — see the comments above.
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        hintsEnabled: state.hintsEnabled,
        onboardingSeen: state.onboardingSeen,
      }),
    },
  ),
);
