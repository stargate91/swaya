import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';

export const useContinueWatchingQuery = (params) => useQuery({
  queryKey: ['continue-watching', params],
  queryFn: () => api.library.getContinueWatching(params),
});

export const useRecommendationsQuery = (language) => useQuery({
  queryKey: ['recommendations', language],
  queryFn: () => api.recommendations.get(language),
});

export const useAddToWatchlistMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tmdbId, type }) => api.recommendations.addToWatchlist(tmdbId, type),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
    },
  });
};

export const useRemoveFromWatchlistMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tmdbId) => api.recommendations.removeFromWatchlist(tmdbId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
    },
  });
};
