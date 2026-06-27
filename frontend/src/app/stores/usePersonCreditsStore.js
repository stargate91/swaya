import { create } from 'zustand';

export const usePersonCreditsStore = create((set) => ({
  activeDiscoverTab: (() => {
    try {
      return localStorage.getItem('person_credits_discover_tab') || '';
    } catch {
      return '';
    }
  })(),
  setActiveDiscoverTab: (tab) => {
    try {
      if (tab) {
        localStorage.setItem('person_credits_discover_tab', tab);
      } else {
        localStorage.removeItem('person_credits_discover_tab');
      }
    } catch {
      // Ignore
    }
    set({ activeDiscoverTab: tab });
  },
}));
