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
    }),
    {
      name: 'dealo-ui',
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
