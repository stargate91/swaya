import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { getOrganizerQueryKey } from './organizerQueries';

const matchesLibraryEntity = (item, rawItemId, cleanId) => {
  if (!item || typeof item !== 'object') return false;
  const itemId = String(item.id ?? '');
  const tmdbId = String(item.tmdb_id ?? '');
  const tvTmdbId = String(item.tv_tmdb_id ?? '');
  return (
    itemId === String(rawItemId)
    || itemId === String(cleanId)
    || itemId === `tv_${cleanId}`
    || itemId === `collection_${cleanId}`
    || tmdbId === String(cleanId)
    || tvTmdbId === String(cleanId)
  );
};

const normalizeLocalPosterPath = (path) => {
  if (!path || typeof path !== 'string') return path;
  const cleanPath = path.replace(/\\/g, '/');
  const marker = 'media/images/posters/';
  if (cleanPath.includes(marker)) {
    return cleanPath.split(marker).pop();
  }
  return path;
};

const applyPosterFields = (item, data, rawItemId) => {
  if (!item || typeof item !== 'object') return item;
  const nextPosterPath = data?.poster_path ?? item.poster_path;
  const nextLocalPosterPath = normalizeLocalPosterPath(data?.local_poster_path ?? item.local_poster_path);
  const nextDisplayPoster = nextLocalPosterPath || nextPosterPath || item.displayPoster;

  const nextItem = {
    ...item,
    poster_path: nextPosterPath,
    local_poster_path: nextLocalPosterPath,
    displayPoster: nextDisplayPoster,
  };

  if (String(rawItemId).startsWith('tv_')) {
    nextItem.tv_poster_path = nextPosterPath;
  }

  return nextItem;
};

const updatePosterInCacheData = (cacheData, rawItemId, cleanId, data) => {
  if (!cacheData || typeof cacheData !== 'object') return cacheData;

  if (Array.isArray(cacheData)) {
    let changed = false;
    const nextArray = cacheData.map((entry) => {
      const nextEntry = updatePosterInCacheData(entry, rawItemId, cleanId, data);
      if (nextEntry !== entry) changed = true;
      return nextEntry;
    });
    return changed ? nextArray : cacheData;
  }

  if (matchesLibraryEntity(cacheData, rawItemId, cleanId)) {
    return applyPosterFields(cacheData, data, rawItemId);
  }

  let changed = false;
  const nextObject = {};
  for (const [key, value] of Object.entries(cacheData)) {
    const nextValue = updatePosterInCacheData(value, rawItemId, cleanId, data);
    if (nextValue !== value) changed = true;
    nextObject[key] = nextValue;
  }

  return changed ? nextObject : cacheData;
};

const prettifyOrganizerLanguage = (value) => String(value || '')
  .replace(/[_-]+/g, ' ')
  .replace(/\b\w/g, (char) => char.toUpperCase());

const applyOrganizerItemUpdates = (item, variables) => {
  if (!item || typeof item !== 'object') return item;
  
  const nextItem = { ...item };
  
  if (variables.custom_language !== undefined) {
    nextItem.target_language = variables.custom_language;
    nextItem.language = prettifyOrganizerLanguage(variables.custom_language);
  }
  if (variables.custom_audio_type !== undefined) {
    nextItem.custom_audio_type = variables.custom_audio_type;
  }
  if (variables.custom_source !== undefined) {
    nextItem.custom_source = variables.custom_source;
  }
  if (variables.custom_edition !== undefined) {
    nextItem.custom_edition = variables.custom_edition;
  }
  if (variables.main_type !== undefined) {
    nextItem.type = variables.main_type;
  }
  if (variables.season !== undefined) {
    nextItem.season = variables.season != null ? String(variables.season) : null;
  }
  if (variables.episode !== undefined) {
    nextItem.episode = variables.episode != null ? String(variables.episode) : null;
  }
  if (variables.parent_id !== undefined) {
    nextItem.parent_id = variables.parent_id;
  }
  
  return nextItem;
};

const updateOrganizerItemsOptimistic = (organizerData, itemIds, variables) => {
  if (!organizerData || typeof organizerData !== 'object' || !variables) return organizerData;

  const targetIds = new Set((itemIds || []).map((itemId) => String(itemId)));
  let changed = false;

  const updateList = (items = []) => items.map((item) => {
    if (!targetIds.has(String(item?.id))) return item;
    changed = true;
    return applyOrganizerItemUpdates(item, variables);
  });

  const nextData = {
    ...organizerData,
    manual: updateList(organizerData.manual || []),
    movies: updateList(organizerData.movies || []),
    tv: updateList(organizerData.tv || []),
    collisions: updateList(organizerData.collisions || []),
  };

  return changed ? nextData : organizerData;
};

const syncPosterCaches = (queryClient, rawItemId, data) => {
  const cleanId = String(rawItemId).replace('tv_', '').replace('collection_', '');

  queryClient.setQueriesData({ queryKey: ['library'] }, (oldData) => (
    updatePosterInCacheData(oldData, rawItemId, cleanId, data)
  ));
  queryClient.setQueriesData({ queryKey: ['libraryCollections'] }, (oldData) => (
    updatePosterInCacheData(oldData, rawItemId, cleanId, data)
  ));

  const detailKeys = [
    ['library-item-detail', rawItemId],
    ['library-item-detail', cleanId],
    ['library-tv-detail', rawItemId],
    ['library-tv-detail', cleanId],
  ];

  if (String(rawItemId).startsWith('collection_')) {
    detailKeys.push(['library-collection-detail', rawItemId]);
    detailKeys.push(['library-collection-detail', cleanId]);
  }

  detailKeys.forEach((key) => {
    queryClient.setQueryData(key, (oldData) => updatePosterInCacheData(oldData, rawItemId, cleanId, data));
  });
};

export const useUpdateMediaMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => api.media.update(payload),
    onMutate: async (variables) => {
      const scanMode = variables?.scanMode;
      const sessionMode = variables?.sessionMode;
      if (scanMode === undefined && sessionMode === undefined) {
        return {};
      }

      const organizerKey = getOrganizerQueryKey(scanMode, sessionMode);
      await queryClient.cancelQueries({ queryKey: organizerKey });
      const previousOrganizer = queryClient.getQueryData(organizerKey);
      queryClient.setQueryData(organizerKey, (oldData) => updateOrganizerItemsOptimistic(oldData, [variables?.id], variables));
      return { organizerKey, previousOrganizer };
    },
    onError: (err, variables, context) => {
      if (context?.organizerKey && context.previousOrganizer) {
        queryClient.setQueryData(context.organizerKey, context.previousOrganizer);
      }
    },
    onSuccess: async (data, variables) => {
      const scanMode = variables?.scanMode;
      const sessionMode = variables?.sessionMode;
      if (scanMode !== undefined || sessionMode !== undefined) {
        const organizerData = await api.organizer.get({ scanMode, sessionMode });
        queryClient.setQueryData(getOrganizerQueryKey(scanMode, sessionMode), organizerData);
      } else {
        await queryClient.invalidateQueries({ queryKey: ['organizer'] });
      }
      queryClient.invalidateQueries({ queryKey: ['organizer-count'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
};

export const useBulkUpdateMediaMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => api.media.bulkUpdate(payload),
    onMutate: async (variables) => {
      const scanMode = variables?.scanMode;
      const sessionMode = variables?.sessionMode;
      const itemIds = variables?.ids || variables?.item_ids || [];
      if ((scanMode === undefined && sessionMode === undefined) || itemIds.length === 0) {
        return {};
      }

      const organizerKey = getOrganizerQueryKey(scanMode, sessionMode);
      await queryClient.cancelQueries({ queryKey: organizerKey });
      const previousOrganizer = queryClient.getQueryData(organizerKey);
      queryClient.setQueryData(organizerKey, (oldData) => updateOrganizerItemsOptimistic(oldData, itemIds, variables));
      return { organizerKey, previousOrganizer };
    },
    onError: (err, variables, context) => {
      if (context?.organizerKey && context.previousOrganizer) {
        queryClient.setQueryData(context.organizerKey, context.previousOrganizer);
      }
    },
    onSuccess: async (data, variables) => {
      const scanMode = variables?.scanMode;
      const sessionMode = variables?.sessionMode;
      if (scanMode !== undefined || sessionMode !== undefined) {
        const organizerData = await api.organizer.get({ scanMode, sessionMode });
        queryClient.setQueryData(getOrganizerQueryKey(scanMode, sessionMode), organizerData);
      } else {
        await queryClient.invalidateQueries({ queryKey: ['organizer'] });
      }
      queryClient.invalidateQueries({ queryKey: ['organizer-count'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
};

export const useUpdateMediaStatusMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, payload }) => api.media.updateStatus(itemId, payload),
    onMutate: async ({ itemId, payload, tvId }) => {
      const targetId = tvId || itemId;

      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['library-tv-detail', targetId] });
      await queryClient.cancelQueries({ queryKey: ['library-item-detail', targetId] });
      await queryClient.cancelQueries({ queryKey: ['library'] });

      // Snapshot previous values
      const prevTvQueries = queryClient.getQueriesData({ queryKey: ['library-tv-detail', targetId] });
      const prevItemQueries = queryClient.getQueriesData({ queryKey: ['library-item-detail', targetId] });
      const prevLibraryList = queryClient.getQueriesData({ queryKey: ['library'] });

      const updates = {};
      if (payload) {
        if ('user_rating' in payload) updates.user_rating = payload.user_rating;
        if ('is_watched' in payload) updates.is_watched = payload.is_watched;
      }

      // Optimistically update details
      if (Object.keys(updates).length > 0) {
        prevTvQueries.forEach(([queryKey, queryData]) => {
          if (queryData) {
            let updatedSeasons = queryData.seasons;
            if (queryData.seasons && 'is_watched' in updates) {
              updatedSeasons = queryData.seasons.map(season => {
                if (!season.episodes) return season;
                const updatedEpisodes = season.episodes.map(ep => {
                  if (String(ep.id) === String(itemId)) {
                    return { ...ep, is_watched: updates.is_watched };
                  }
                  return ep;
                });
                const isSeasonWatched = updatedEpisodes.length > 0 && updatedEpisodes.every(ep => ep.is_watched);
                return { ...season, episodes: updatedEpisodes, is_watched: isSeasonWatched };
              });
            }
            queryClient.setQueryData(queryKey, {
              ...queryData,
              ...updates,
              seasons: updatedSeasons
            });
          }
        });
        prevItemQueries.forEach(([queryKey, queryData]) => {
          if (queryData) {
            queryClient.setQueryData(queryKey, {
              ...queryData,
              ...updates
            });
          }
        });

        // Optimistically update lists
        prevLibraryList.forEach(([queryKey, queryData]) => {
          if (!queryData) return;
          let changed = false;

          const updateItem = (obj) => {
            if (!obj || typeof obj !== 'object') return obj;
            if (Array.isArray(obj)) {
              return obj.map(x => {
                if (x && (String(x.id) === String(targetId) || String(x.id) === `tv_${targetId}`)) {
                  changed = true;
                  return { ...x, ...updates };
                }
                return updateItem(x);
              });
            }
            const nextObj = {};
            for (const key in obj) {
              nextObj[key] = updateItem(obj[key]);
            }
            return nextObj;
          };

          const updatedData = updateItem(queryData);
          if (changed) {
            queryClient.setQueryData(queryKey, updatedData);
          }
        });
      }

      return { prevTvQueries, prevItemQueries, prevLibraryList, targetId };
    },
    onError: (err, variables, context) => {
      if (context?.prevTvQueries) {
        context.prevTvQueries.forEach(([queryKey, queryData]) => {
          queryClient.setQueryData(queryKey, queryData);
        });
      }
      if (context?.prevItemQueries) {
        context.prevItemQueries.forEach(([queryKey, queryData]) => {
          queryClient.setQueryData(queryKey, queryData);
        });
      }
      if (context?.prevLibraryList) {
        context.prevLibraryList.forEach(([queryKey, queryData]) => {
          queryClient.setQueryData(queryKey, queryData);
        });
      }
    },
    onSuccess: (data, variables) => {
      const updateDetailCache = (oldData) => {
        if (!oldData) return oldData;
        return {
          ...oldData,
          user_rating: data.user_rating !== undefined ? data.user_rating : oldData.user_rating,
          user_comment: data.user_comment !== undefined ? data.user_comment : oldData.user_comment,
          is_watched: data.is_watched !== undefined ? data.is_watched : oldData.is_watched,
          custom_tags: data.custom_tags !== undefined ? data.custom_tags : oldData.custom_tags,
          tags: data.tags !== undefined ? data.tags : oldData.tags,
        };
      };

      queryClient.setQueryData(['full-metadata', variables.itemId], updateDetailCache);
      queryClient.setQueryData(['library-item-detail', variables.itemId], updateDetailCache);
      queryClient.setQueryData(['library-tv-detail', variables.itemId], updateDetailCache);

      queryClient.invalidateQueries({ queryKey: ['full-metadata', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.itemId] });

      const cleanId = String(variables.itemId).replace('tv_', '');
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });

      if (variables.tvId) {
        const updateTvCacheWithEpisode = (oldData) => {
          if (!oldData) return oldData;
          let updatedSeasons = oldData.seasons;
          if (oldData.seasons && data.is_watched !== undefined) {
            updatedSeasons = oldData.seasons.map(season => {
              if (!season.episodes) return season;
              const updatedEpisodes = season.episodes.map(ep => {
                if (String(ep.id) === String(variables.itemId)) {
                  return { ...ep, is_watched: data.is_watched };
                }
                return ep;
              });
              const isSeasonWatched = updatedEpisodes.length > 0 && updatedEpisodes.every(ep => ep.is_watched);
              return { ...season, episodes: updatedEpisodes, is_watched: isSeasonWatched };
            });
          }
          return {
            ...oldData,
            seasons: updatedSeasons,
          };
        };

        queryClient.setQueryData(['library-tv-detail', variables.tvId], updateTvCacheWithEpisode);
        queryClient.setQueryData(['library-tv-detail', `tv_${variables.tvId}`], updateTvCacheWithEpisode);
        queryClient.setQueryData(['library-item-detail', variables.tvId], updateDetailCache);
        queryClient.setQueryData(['library-item-detail', `tv_${variables.tvId}`], updateDetailCache);
        queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.tvId] });
        queryClient.invalidateQueries({ queryKey: ['library-tv-detail', `tv_${variables.tvId}`] });
        queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.tvId] });
        queryClient.invalidateQueries({ queryKey: ['library-item-detail', `tv_${variables.tvId}`] });
      }

      // Update matching items in the library query cache instead of invalidating everything
      queryClient.setQueriesData({ queryKey: ['library'] }, (oldData) => {
        if (!oldData) return oldData;
        let changed = false;

        const updateItem = (obj) => {
          if (!obj || typeof obj !== 'object') return obj;
          if (Array.isArray(obj)) {
            return obj.map(x => {
              const isMatch = x && (
                String(x.id) === String(variables.itemId) ||
                String(x.id) === `tv_${variables.itemId}` ||
                (variables.tvId && String(x.id) === String(variables.tvId))
              );
              if (isMatch) {
                changed = true;
                return {
                  ...x,
                  user_rating: data.user_rating !== undefined ? data.user_rating : x.user_rating,
                  is_watched: data.is_watched !== undefined ? data.is_watched : x.is_watched,
                  custom_tags: data.custom_tags !== undefined ? data.custom_tags : x.custom_tags,
                  tags: data.tags !== undefined ? data.tags : x.tags,
                };
              }
              return updateItem(x);
            });
          }
          const nextObj = {};
          for (const key in obj) {
            nextObj[key] = updateItem(obj[key]);
          }
          return nextObj;
        };

        const nextData = updateItem(oldData);
        return changed ? nextData : oldData;
      });

      const payload = variables.payload || {};
      if ('user_rating' in payload || 'is_watched' in payload) {
        queryClient.invalidateQueries({ queryKey: ['stats'] });
      }
      if ('custom_tags' in payload) {
        queryClient.invalidateQueries({ queryKey: ['libraryTags'] });
        queryClient.invalidateQueries({ queryKey: ['allTags'] });
        queryClient.invalidateQueries({ queryKey: ['libraryFilters'] });
      }
    },
  });
};

export const useBulkUpdateWatchedMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemIds, isWatched }) => api.media.bulkWatched(itemIds, isWatched),
    onSuccess: (data, variables) => {
      if (variables.tvId) {
        queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.tvId] });
      }
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const usePlayMediaMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId) => api.media.play(itemId),
    onSuccess: (data, itemId) => {
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', itemId] });
      queryClient.invalidateQueries({ queryKey: ['watched-history'] });
      queryClient.invalidateQueries({ queryKey: ['continue-watching'] });
    },
  });
};

export const useResetProgressMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (itemId) => api.media.resetProgress(itemId),
    onSuccess: (data, itemId) => {
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', itemId] });
      queryClient.invalidateQueries({ queryKey: ['continue-watching'] });
    },
  });
};

export const usePreviewMediaMutation = () => {
  return useMutation({
    mutationFn: (filePath) => api.media.preview(filePath),
  });
};

export const useOverrideBackdropMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, backdropPath, mediaType }) => api.media.overrideBackdrop(itemId, backdropPath, mediaType),
    onSuccess: (data, variables) => {
      const cleanId = String(variables.itemId).replace('tv_', '');
      const isCollection = String(variables.itemId).startsWith('collection_');
      queryClient.invalidateQueries({ queryKey: ['full-metadata', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });
      if (isCollection) {
        const collectionId = String(variables.itemId).replace('collection_', '');
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', collectionId] });
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', variables.itemId] });
      }
    },
  });
};

export const useUploadBackdropMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, file, mediaType }) => api.media.uploadBackdrop(itemId, file, mediaType),
    onSuccess: (data, variables) => {
      const cleanId = String(variables.itemId).replace('tv_', '').replace('collection_', '');
      const isCollection = String(variables.itemId).startsWith('collection_');
      queryClient.invalidateQueries({ queryKey: ['full-metadata', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });
      if (isCollection) {
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', cleanId] });
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', variables.itemId] });
      }
      queryClient.invalidateQueries({ queryKey: ['library'] });
      queryClient.invalidateQueries({ queryKey: ['libraryCollections'] });
    },
  });
};

export const useOverridePosterMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, posterPath, mediaType }) => api.media.overridePoster(itemId, posterPath, mediaType),
    onSuccess: (data, variables) => {
      const cleanId = String(variables.itemId).replace('tv_', '');
      const isCollection = String(variables.itemId).startsWith('collection_');
      syncPosterCaches(queryClient, variables.itemId, data);
      queryClient.invalidateQueries({ queryKey: ['full-metadata', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });
      if (isCollection) {
        const collectionId = String(variables.itemId).replace('collection_', '');
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', collectionId] });
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', variables.itemId] });
      }
      queryClient.invalidateQueries({ queryKey: ['library'] });
      queryClient.invalidateQueries({ queryKey: ['libraryCollections'] });
    },
  });
};

export const useUploadPosterMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, file, mediaType }) => api.media.uploadPoster(itemId, file, mediaType),
    onSuccess: (data, variables) => {
      const cleanId = String(variables.itemId).replace('tv_', '');
      const isCollection = String(variables.itemId).startsWith('collection_');
      syncPosterCaches(queryClient, variables.itemId, data);
      queryClient.invalidateQueries({ queryKey: ['full-metadata', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });
      if (isCollection) {
        const collectionId = String(variables.itemId).replace('collection_', '');
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', collectionId] });
        queryClient.invalidateQueries({ queryKey: ['library-collection-detail', variables.itemId] });
      }
      queryClient.invalidateQueries({ queryKey: ['library'] });
      queryClient.invalidateQueries({ queryKey: ['libraryCollections'] });
    },
  });
};

export const useOverrideLogoMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, logoPath, mediaType }) => api.media.overrideLogo(itemId, logoPath, mediaType),
    onSuccess: (data, variables) => {
      const cleanId = String(variables.itemId).replace('tv_', '');
      queryClient.invalidateQueries({ queryKey: ['full-metadata', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useUploadLogoMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, file, mediaType }) => api.media.uploadLogo(itemId, file, mediaType),
    onSuccess: (data, variables) => {
      const cleanId = String(variables.itemId).replace('tv_', '');
      queryClient.invalidateQueries({ queryKey: ['full-metadata', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', variables.itemId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};


export const useToggleTrackedMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tmdbId, mediaType, isTracked }) => (
      isTracked
        ? api.media.untrackItem(tmdbId, mediaType)
        : api.media.trackItem(tmdbId, mediaType)
    ),
    onSuccess: (data, variables) => {
      const rawId = String(variables.tmdbId).replace('stash_', '').replace('tmdb_', '').replace('tv_', '');
      const cleanId = rawId;
      const tvId = `tv_${rawId}`;
      const trackedId = `tmdb_${rawId}`;
      const stashId = `stash_${rawId}`;
      queryClient.invalidateQueries({ queryKey: ['library'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', tvId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', trackedId] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata', stashId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', trackedId] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail', stashId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', cleanId] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail', tvId] });
    },
  });
};

export const useAddPeakMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (variables) => {
      const itemId = typeof variables === 'object' ? variables.itemId : variables;
      return api.media.addPeak(itemId);
    },
    onMutate: async (variables) => {
      const { itemId, tvId } = typeof variables === 'object' ? variables : { itemId: variables, tvId: null };
      const targets = [itemId, tvId].filter(Boolean);
      
      for (const id of targets) {
        const clean = String(id).replace('tv_', '');
        await queryClient.cancelQueries({ queryKey: ['library-item-detail', id] });
        await queryClient.cancelQueries({ queryKey: ['library-item-detail', clean] });
      }

      const contextSnapshot = {};
      targets.forEach(id => {
        const clean = String(id).replace('tv_', '');
        contextSnapshot[id] = queryClient.getQueryData(['library-item-detail', id]);
        contextSnapshot[clean] = queryClient.getQueryData(['library-item-detail', clean]);
      });

      const optimisticUpdate = (oldData) => {
        if (!oldData) return oldData;
        const currentCount = oldData.peaks_count || 0;
        const currentHistory = oldData.peaks_history || [];
        const tempPeak = {
          id: 'temp-' + Date.now(),
          video_position: 0,
          watched_at: new Date().toISOString(),
          isOptimistic: true,
        };
        return {
          ...oldData,
          peaks_count: currentCount + 1,
          peaks_history: [...currentHistory, tempPeak].sort((a, b) => a.video_position - b.video_position),
        };
      };

      targets.forEach(id => {
        const clean = String(id).replace('tv_', '');
        queryClient.setQueryData(['library-item-detail', id], optimisticUpdate);
        queryClient.setQueryData(['library-item-detail', clean], optimisticUpdate);
      });

      return { contextSnapshot };
    },
    onError: (err, variables, context) => {
      if (context?.contextSnapshot) {
        Object.entries(context.contextSnapshot).forEach(([key, val]) => {
          queryClient.setQueryData(['library-item-detail', key], val);
        });
      }
    },
    onSuccess: (data, variables) => {
      const { itemId, tvId } = typeof variables === 'object' ? variables : { itemId: variables, tvId: null };
      const updateData = (oldData) => {
        if (!oldData) return oldData;
        return {
          ...oldData,
          peaks_count: data.peaks_count,
          peaks_history: data.peaks_history,
        };
      };
      const targets = [itemId, tvId].filter(Boolean);
      targets.forEach(id => {
        const clean = String(id).replace('tv_', '');
        queryClient.setQueryData(['library-item-detail', id], updateData);
        queryClient.setQueryData(['library-item-detail', clean], updateData);
        queryClient.setQueryData(['library-tv-detail', id], updateData);
        queryClient.invalidateQueries({ queryKey: ['library-item-detail', id] });
        queryClient.invalidateQueries({ queryKey: ['library-item-detail', clean] });
      });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail'] });
    },
  });
};

export const useDeletePeakMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, logId }) => api.media.deletePeak(itemId, logId),
    onSuccess: (data, variables) => {
      const { itemId, tvId } = variables;
      const updateData = (oldData) => {
        if (!oldData) return oldData;
        return {
          ...oldData,
          peaks_count: data.peaks_count,
          peaks_history: data.peaks_history,
        };
      };
      const targets = [itemId, tvId].filter(Boolean);
      targets.forEach(id => {
        const clean = String(id).replace('tv_', '');
        queryClient.setQueryData(['library-item-detail', id], updateData);
        queryClient.setQueryData(['library-item-detail', clean], updateData);
        queryClient.setQueryData(['library-tv-detail', id], updateData);
        queryClient.invalidateQueries({ queryKey: ['library-item-detail', id] });
        queryClient.invalidateQueries({ queryKey: ['library-item-detail', clean] });
      });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail'] });
    },
  });
};
