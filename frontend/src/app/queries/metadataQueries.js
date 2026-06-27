import { useQuery, useMutation, useInfiniteQuery } from '@tanstack/react-query';
import api from '@/lib/api';

export const useSearchMetadataQuery = (query, itemType, year, season, episode, includeAdult, provider, options = {}) => useQuery({
  queryKey: ['metadata-search', query, itemType, year, season, episode, includeAdult, provider],
  queryFn: () => api.metadata.search({ query, itemType, year, season, episode, includeAdult, provider }),
  ...options,
});

export const useTvSeasonsQuery = (tvId, options = {}) => {
  const { language = 'en-US', ...queryOptions } = options;
  return useQuery({
    queryKey: ['tv-seasons', tvId, language],
    queryFn: () => api.tv.getSeasons(tvId, { language }),
    ...queryOptions,
  });
};

export const useTvEpisodesQuery = (tvId, seasonNumber, options = {}) => {
  const { language = 'en-US', ...queryOptions } = options;
  return useQuery({
    queryKey: ['tv-episodes', tvId, seasonNumber, language],
    queryFn: () => api.tv.getEpisodes(tvId, seasonNumber, { language }),
    ...queryOptions,
  });
};

export const useResolveMetadataMutation = () => useMutation({
  mutationFn: (payload) => api.metadata.resolve(payload),
});

export const useBulkResolveMetadataMutation = () => useMutation({
  mutationFn: (payload) => api.metadata.bulkResolve(payload),
});

export const useFullMetadataQuery = (itemId, mediaType, options = {}) => {
  const { language, ...queryOptions } = options;
  return useQuery({
    queryKey: ['full-metadata', itemId, mediaType || null, language || null],
    queryFn: () => api.metadata.getItemFullMetadata(itemId, mediaType, { language }),
    ...queryOptions,
  });
};

export const useSyncLanguageMutation = () => useMutation({
  mutationFn: () => api.metadata.syncLanguage(),
});

export const useLibraryItemDetailQuery = (itemId, options = {}) => {
  const { mediaType, ...queryOptions } = options;
  return useQuery({
    queryKey: ['library-item-detail', itemId, mediaType || null],
    queryFn: () => api.library.getItemDetail(itemId, { mediaType }),
    ...queryOptions,
  });
};

export const useLibraryTvDetailQuery = (tvId, options = {}) => {
  const { seasonsLimit = 5, initialEpisodesLimit = 4, language, ...queryOptions } = options;
  return useQuery({
    queryKey: ['library-tv-detail', tvId, language || null],
    queryFn: () => api.library.getTvDetail(tvId, { seasonsLimit, initialEpisodesLimit, language }),
    ...queryOptions,
  });
};

export const useLibraryCollectionDetailQuery = (collectionId, options = {}) => {
  const { language, ...queryOptions } = options;
  return useQuery({
    queryKey: ['library-collection-detail', collectionId, language || null],
    queryFn: () => api.library.getCollectionDetail(collectionId, { language }),
    ...queryOptions,
  });
};

export const usePersonDetailQuery = (personId, options = {}) => useQuery({
  queryKey: ['person-detail', personId],
  queryFn: () => api.people.getDetail(personId),
  ...options,
});

export const usePersonCreditsQuery = (personId, mediaType, page, pageSize, options = {}) => {
  const { excludeKnownFor = false, source, ...queryOptions } = options;
  return useQuery({
    queryKey: ['person-credits', personId, mediaType, page, pageSize, excludeKnownFor, source || null],
    queryFn: () => api.people.getCredits(personId, mediaType, { page, pageSize, excludeKnownFor, source }),
    placeholderData: (previousData) => previousData,
    ...queryOptions,
  });
};

export const usePersonCreditsInfiniteQuery = (personId, mediaType, pageSize, options = {}) => {
  const { excludeKnownFor = false, source, ...queryOptions } = options;
  return useInfiniteQuery({
    queryKey: ['person-credits-infinite', personId, mediaType, pageSize, excludeKnownFor, source || null],
    queryFn: ({ pageParam = 1 }) => api.people.getCredits(personId, mediaType, { page: pageParam, pageSize, excludeKnownFor, source }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil((lastPage.total_items || 0) / pageSize);
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
    ...queryOptions,
  });
};

export const usePersonCreditBackdropsQuery = (personId, tmdbId, mediaType, options = {}) => useQuery({
  queryKey: ['person-credit-backdrops', personId, tmdbId, mediaType],
  queryFn: () => api.people.getCreditBackdrops(personId, tmdbId, mediaType),
  ...options,
});
