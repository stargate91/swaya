import { create } from 'zustand';

const createDefaultSession = (initialBackdropPath = '') => ({
  activeTab: 'movies',
  selectedBackdropPath: initialBackdropPath || '',
  currentSourceCreditKey: '',
  selectedCredit: null,
  moviePages: [],
  tvPages: [],
  movieNextPage: 2,
  tvNextPage: 2,
  movieLoadingMore: false,
  tvLoadingMore: false,
  creditValidationByKey: {},
  gridScrollTop: 0,
});

export const createPersonBackdropChooserSession = createDefaultSession;

export const usePersonBackdropChooserStore = create(
  (set) => ({
    sessions: {},
    ensureSession: (personId, initialBackdropPath = '') => set((state) => {
      const key = String(personId || '');
      if (!key || state.sessions[key]) {
        return state;
      }
      return {
        sessions: {
          ...state.sessions,
          [key]: createDefaultSession(initialBackdropPath),
        },
      };
    }),
    patchSession: (personId, patch) => set((state) => {
      const key = String(personId || '');
      if (!key) {
        return state;
      }
      const current = state.sessions[key] || createDefaultSession();
      const nextPatch = typeof patch === 'function' ? patch(current) : patch;
      return {
        sessions: {
          ...state.sessions,
          [key]: {
            ...current,
            ...nextPatch,
          },
        },
      };
    }),
    resetSession: (personId, initialBackdropPath = '') => set((state) => {
      const key = String(personId || '');
      if (!key) {
        return state;
      }
      return {
        sessions: {
          ...state.sessions,
          [key]: createDefaultSession(initialBackdropPath),
        },
      };
    }),
  })
);

