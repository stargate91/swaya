import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import api from '@/lib/api';


const syncPersonProfileCaches = (queryClient, personId, data) => {
  const personKeys = [
    ['person-detail', personId],
    ['person-detail', String(personId)],
    ['person-detail', Number(personId)],
  ];

  personKeys.forEach((key) => {
    queryClient.setQueryData(key, (oldData) => {
      if (!oldData) {
        return oldData;
      }
      return {
        ...oldData,
        profile_path: data?.profile_path ?? oldData.profile_path,
        local_profile_path: data?.local_profile_path ?? oldData.local_profile_path,
        has_local_profile: data?.has_local_profile ?? oldData.has_local_profile,
      };
    });
  });

  queryClient.setQueriesData({ queryKey: ['people'] }, (oldData) => {
    if (!oldData?.items) return oldData;
    return {
      ...oldData,
      items: oldData.items.map((item) => (
        item.id === personId || String(item.id) === String(personId)
          ? {
              ...item,
              profile_path: data?.profile_path ?? item.profile_path,
              poster_path: data?.profile_path ?? item.poster_path,
              local_profile_path: data?.local_profile_path ?? item.local_profile_path,
            }
          : item
      )),
    };
  });

  queryClient.setQueriesData({ queryKey: ['people-infinite'] }, (oldData) => {
    if (!oldData?.pages) return oldData;
    return {
      ...oldData,
      pages: oldData.pages.map((page) => ({
        ...page,
        items: (page.items || []).map((item) => (
          item.id === personId || String(item.id) === String(personId)
            ? {
                ...item,
                profile_path: data?.profile_path ?? item.profile_path,
                poster_path: data?.profile_path ?? item.poster_path,
                local_profile_path: data?.local_profile_path ?? item.local_profile_path,
              }
            : item
        )),
      })),
    };
  });

  queryClient.setQueriesData({ queryKey: ['library'] }, (oldData) => {
    if (!oldData?.items) return oldData;
    return {
      ...oldData,
      items: oldData.items.map((item) => (
        item.id === personId || String(item.id) === String(personId)
          ? {
              ...item,
              profile_path: data?.profile_path ?? item.profile_path,
              poster_path: data?.profile_path ?? item.poster_path,
              local_profile_path: data?.local_profile_path ?? item.local_profile_path,
              displayPoster: data?.profile_path ?? item.displayPoster,
            }
          : item
      )),
    };
  });
};

const syncPersonBackdropCaches = (queryClient, personId, data) => {
  const personKeys = [
    ['person-detail', personId],
    ['person-detail', String(personId)],
    ['person-detail', Number(personId)],
  ];

  personKeys.forEach((key) => {
    queryClient.setQueryData(key, (oldData) => {
      if (!oldData) {
        return oldData;
      }
      return {
        ...oldData,
        backdrop_path: data?.backdrop_path ?? oldData.backdrop_path,
        local_backdrop_path: data?.local_backdrop_path ?? oldData.local_backdrop_path,
        has_local_backdrop: data?.has_local_backdrop ?? oldData.has_local_backdrop,
      };
    });
  });
};

export const useStatsQuery = () => useQuery({
  queryKey: ['stats'],
  queryFn: () => api.library.getStats(),
});

export const useLibraryQuery = (params) => useQuery({
  queryKey: ['library', params],
  queryFn: ({ signal }) => api.library.getItems(params, { signal }),
  placeholderData: (previousData, previousQuery) => {
    if (!previousData || !previousQuery) return undefined;
    const prevParams = previousQuery.queryKey[1] || {};
    const currentParams = params || {};
    if (prevParams.tab !== currentParams.tab) {
      return undefined;
    }
    return previousData;
  },
});

export const useCollectionsQuery = (params) => useQuery({
  queryKey: ['libraryCollections', params],
  queryFn: ({ signal }) => api.library.getCollections(params, { signal }),
  placeholderData: (previousData, previousQuery) => {
    if (!previousData || !previousQuery) return undefined;
    const prevParams = previousQuery.queryKey[1] || {};
    const currentParams = params || {};
    if (prevParams.tab !== currentParams.tab) {
      return undefined;
    }
    return previousData;
  },
});

export const useTagsQuery = (isAdult = false) => useQuery({
  queryKey: ['libraryTags', isAdult],
  queryFn: () => api.library.getTags(isAdult),
});

export const useAllTagsQuery = (isAdult = false) => useQuery({
  queryKey: ['allTags', isAdult],
  queryFn: () => api.tags.getAll(isAdult),
});

export const useCreateTagMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => api.tags.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraryTags'] });
      queryClient.invalidateQueries({ queryKey: ['allTags'] });
      queryClient.invalidateQueries({ queryKey: ['libraryFilters'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
};

export const useUpdateTagMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tagId, payload }) => api.tags.update(tagId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraryTags'] });
      queryClient.invalidateQueries({ queryKey: ['allTags'] });
      queryClient.invalidateQueries({ queryKey: ['libraryFilters'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
};

export const useDeleteTagMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tagId) => api.tags.delete(tagId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['libraryTags'] });
      queryClient.invalidateQueries({ queryKey: ['allTags'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
      queryClient.invalidateQueries({ queryKey: ['library-item-detail'] });
      queryClient.invalidateQueries({ queryKey: ['library-tv-detail'] });
      queryClient.invalidateQueries({ queryKey: ['full-metadata'] });
      queryClient.invalidateQueries({ queryKey: ['libraryFilters'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
};

export const useLibraryFiltersQuery = (params) => useQuery({
  queryKey: ['libraryFilters', params],
  queryFn: ({ signal }) => api.library.getFilters(params, { signal }),
  staleTime: 5 * 60 * 1000,
});

export const usePeopleQuery = (params) => useQuery({
  queryKey: ['people', params],
  queryFn: () => api.people.getAll(params),
  placeholderData: (previousData) => previousData,
});

export const usePeopleInfiniteQuery = (params) => useInfiniteQuery({
  queryKey: ['people-infinite', params],
  queryFn: ({ pageParam = 0 }) => api.people.getAll({ ...params, offset: pageParam, limit: 20 }),
  initialPageParam: 0,
  getNextPageParam: (lastPage) => {
    if (!lastPage.has_more) return undefined;
    return lastPage.offset + lastPage.limit;
  },
});

export const useAddPersonTmdbMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => api.people.addTmdb(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    },
  });
};

export const useUpdatePersonStatusMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, payload }) => api.people.updateStatus(personId, payload),
    onMutate: async ({ personId, payload }) => {
      const idStr = String(personId);
      const idNum = Number(personId);
      const isNumValid = !isNaN(idNum);

      await queryClient.cancelQueries({ queryKey: ['people'] });
      await queryClient.cancelQueries({ queryKey: ['people-infinite'] });
      await queryClient.cancelQueries({ queryKey: ['library'] });
      await queryClient.cancelQueries({ queryKey: ['person-detail', idStr] });
      if (isNumValid) {
        await queryClient.cancelQueries({ queryKey: ['person-detail', idNum] });
      }

      const previousLibraryQueries = queryClient.getQueriesData({ queryKey: ['library'] });
      const previousPeopleQueries = queryClient.getQueriesData({ queryKey: ['people'] });
      const previousPeopleInfiniteQueries = queryClient.getQueriesData({ queryKey: ['people-infinite'] });
      const previousPersonDetail = queryClient.getQueryData(['person-detail', idStr]) || queryClient.getQueryData(['person-detail', idNum]);
      const shouldAutoActivate =
        payload?.is_favorite === true
        || ('user_rating' in payload && payload.user_rating !== null && payload.user_rating !== undefined)
        || ('user_comment' in payload && payload.user_comment !== null && payload.user_comment !== undefined && String(payload.user_comment).trim() !== '');
      const effectiveIsActive = payload.is_active !== undefined ? payload.is_active : (shouldAutoActivate ? true : undefined);

      let foundPerson = null;

      for (const [, cacheData] of previousPeopleInfiniteQueries) {
        if (cacheData?.pages) {
          for (const page of cacheData.pages) {
            const item = page.items?.find(p => p.id === personId || String(p.id) === idStr);
            if (item) {
              foundPerson = { ...item, ...(effectiveIsActive !== undefined ? { is_active: effectiveIsActive } : {}) };
              break;
            }
          }
        }
        if (foundPerson) break;
      }

      if (!foundPerson) {
        for (const [, cacheData] of previousPeopleQueries) {
          const item = cacheData?.items?.find(p => p.id === personId || String(p.id) === idStr);
          if (item) {
            foundPerson = { ...item, ...(effectiveIsActive !== undefined ? { is_active: effectiveIsActive } : {}) };
            break;
          }
        }
      }

      // 1. Update people-infinite queries
      queryClient.setQueriesData({ queryKey: ['people-infinite'] }, (oldData, query) => {
        if (!oldData?.pages) return oldData;
        const queryParams = query?.queryKey?.[1] || {};
        const queryAdultOnly = queryParams.adult_only;
        const isAdultPerson = foundPerson?.is_adult || foundPerson?.is_adult_person || false;
        if (queryAdultOnly !== undefined && queryAdultOnly !== isAdultPerson) {
          return oldData;
        }
        return {
          ...oldData,
          pages: oldData.pages.map(page => ({
            ...page,
            items: page.items.map(p => (p.id === personId || String(p.id) === idStr) ? {
              ...p,
              ...(effectiveIsActive !== undefined ? { is_active: effectiveIsActive } : {}),
              ...(payload.is_favorite !== undefined ? { is_favorite: payload.is_favorite } : {}),
              ...('user_rating' in payload ? { user_rating: payload.user_rating } : {}),
              ...('user_comment' in payload ? { user_comment: payload.user_comment } : {}),
              ...('custom_tags' in payload ? { custom_tags: payload.custom_tags } : {}),
            } : p)
          }))
        };
      });

      // 2. Update people queries
      queryClient.setQueriesData({ queryKey: ['people'] }, (oldData, query) => {
        if (!oldData?.items) return oldData;
        const queryParams = query?.queryKey?.[1] || {};
        const queryAdultOnly = queryParams.adult_only;
        const isAdultPerson = foundPerson?.is_adult || foundPerson?.is_adult_person || false;
        if (queryAdultOnly !== undefined && queryAdultOnly !== isAdultPerson) {
          return oldData;
        }
        return {
          ...oldData,
          items: oldData.items.map(p => (p.id === personId || String(p.id) === idStr) ? {
            ...p,
            ...(effectiveIsActive !== undefined ? { is_active: effectiveIsActive } : {}),
            ...(payload.is_favorite !== undefined ? { is_favorite: payload.is_favorite } : {}),
            ...('user_rating' in payload ? { user_rating: payload.user_rating } : {}),
            ...('user_comment' in payload ? { user_comment: payload.user_comment } : {}),
            ...('custom_tags' in payload ? { custom_tags: payload.custom_tags } : {}),
          } : p)
        };
      });

      const updatePersonDetailData = (pId) => {
        queryClient.setQueryData(['person-detail', pId], (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            ...(effectiveIsActive !== undefined ? { is_active: effectiveIsActive } : {}),
            ...(payload.is_favorite !== undefined ? { is_favorite: payload.is_favorite } : {}),
            ...('user_rating' in payload ? { user_rating: payload.user_rating } : {}),
            ...('user_comment' in payload ? { user_comment: payload.user_comment } : {}),
            ...('custom_tags' in payload ? { custom_tags: payload.custom_tags } : {}),
          };
        });
      };
      updatePersonDetailData(idStr);
      if (isNumValid) {
        updatePersonDetailData(idNum);
      }

      // 3. Update library queries (which renders the active people grid)
      queryClient.setQueriesData({ queryKey: ['library'] }, (oldData, query) => {
        if (!oldData?.items) return oldData;
        const queryParams = query?.queryKey?.[1] || {};
        const queryTab = queryParams.tab;

        // Only modify people lists
        const isPeopleTab = queryTab === 'people' || queryTab === 'adult_people';
        if (!isPeopleTab) return oldData;

        const hasFilters = queryParams.search || (queryParams.people_role && queryParams.people_role !== 'all') || (queryParams.filter_gender && queryParams.filter_gender !== 'all');

        const updatedItems = oldData.items.map(p => {
          if (p.id === personId || String(p.id) === idStr) {
            return {
              ...p,
              ...(effectiveIsActive !== undefined ? { is_active: effectiveIsActive } : {}),
              ...(payload.is_favorite !== undefined ? { is_favorite: payload.is_favorite } : {}),
              ...('user_rating' in payload ? { user_rating: payload.user_rating } : {}),
              ...('user_comment' in payload ? { user_comment: payload.user_comment } : {}),
            };
          }
          return p;
        });

        if (effectiveIsActive === false) {
          return {
            ...oldData,
            items: updatedItems.filter(p => p.id !== personId && String(p.id) !== idStr)
          };
        } else if (effectiveIsActive === true && foundPerson) {
          const isAdultPerson = foundPerson.is_adult || foundPerson.is_adult_person || false;
          const targetTab = isAdultPerson ? 'adult_people' : 'people';
          if (queryTab !== targetTab) {
            return oldData;
          }

          if (hasFilters) {
            return {
              ...oldData,
              items: updatedItems
            };
          }

          if (updatedItems.some(p => p.id === personId || String(p.id) === idStr)) {
            return {
              ...oldData,
              items: updatedItems
            };
          }

          const libraryPerson = {
            id: foundPerson.id,
            name: foundPerson.name,
            title: foundPerson.name,
            profile_path: foundPerson.profile_path,
            poster_path: foundPerson.profile_path,
            people_role: foundPerson.known_for || foundPerson.people_role || 'Actor',
            gender: foundPerson.gender,
            is_active: true,
            is_favorite: payload.is_favorite,
            user_rating: payload.user_rating,
          };

          return {
            ...oldData,
            items: [...updatedItems, libraryPerson]
          };
        }
        return {
          ...oldData,
          items: updatedItems
        };
      });

      return { previousLibraryQueries, previousPeopleQueries, previousPeopleInfiniteQueries, previousPersonDetail, personId };
    },
    onError: (err, variables, context) => {
      const idStr = String(context.personId);
      const idNum = Number(context.personId);
      const isNumValid = !isNaN(idNum);

      if (context?.previousLibraryQueries) {
        context.previousLibraryQueries.forEach(([key, value]) => {
          queryClient.setQueryData(key, value);
        });
      }
      if (context?.previousPeopleQueries) {
        context.previousPeopleQueries.forEach(([key, value]) => {
          queryClient.setQueryData(key, value);
        });
      }
      if (context?.previousPeopleInfiniteQueries) {
        context.previousPeopleInfiniteQueries.forEach(([key, value]) => {
          queryClient.setQueryData(key, value);
        });
      }
      if (context && 'previousPersonDetail' in context) {
        queryClient.setQueryData(['person-detail', idStr], context.previousPersonDetail);
        if (isNumValid) {
          queryClient.setQueryData(['person-detail', idNum], context.previousPersonDetail);
        }
      }
    },
    onSuccess: (data, variables) => {
      const idStr = String(variables.personId);
      const idNum = Number(variables.personId);
      const isNumValid = !isNaN(idNum);

      const updateSuccessData = (pId) => {
        queryClient.setQueryData(['person-detail', pId], (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            is_active: data.is_active !== undefined ? data.is_active : oldData.is_active,
            is_favorite: data.is_favorite !== undefined ? data.is_favorite : oldData.is_favorite,
            user_rating: data.user_rating !== undefined ? data.user_rating : oldData.user_rating,
            user_comment: data.user_comment !== undefined ? data.user_comment : oldData.user_comment,
            custom_tags: data.custom_tags !== undefined ? data.custom_tags : oldData.custom_tags,
            tags: data.tags !== undefined ? data.tags : oldData.tags,
          };
        });
      };
      updateSuccessData(idStr);
      if (isNumValid) {
        updateSuccessData(idNum);
      }
    },
    onSettled: (data, error, variables) => {
      const idStr = String(variables.personId);
      const idNum = Number(variables.personId);
      const isNumValid = !isNaN(idNum);
      const payload = variables?.payload || {};
      
      if (error) {
        queryClient.invalidateQueries({ queryKey: ['people'] });
        queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
        queryClient.invalidateQueries({ queryKey: ['library'] });
        queryClient.invalidateQueries({ queryKey: ['person-detail', idStr] });
        if (isNumValid) {
          queryClient.invalidateQueries({ queryKey: ['person-detail', idNum] });
        }
        queryClient.invalidateQueries({ queryKey: ['stats'] });
        return;
      }

      if ('is_active' in payload || 'is_favorite' in payload || 'user_rating' in payload) {
        queryClient.invalidateQueries({ queryKey: ['people'] });
        queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
        queryClient.invalidateQueries({ queryKey: ['library'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
      }

      if ('custom_tags' in payload) {
        queryClient.invalidateQueries({ queryKey: ['libraryTags'] });
        queryClient.invalidateQueries({ queryKey: ['allTags'] });
      }
    },
  });
};

export const useOverridePersonBackdropMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, backdropPath }) => api.people.overrideBackdrop(personId, backdropPath),
    onSuccess: (data, variables) => {
      const personKeys = [
        ['person-detail', variables.personId],
        ['person-detail', String(variables.personId)],
        ['person-detail', Number(variables.personId)],
      ];
      personKeys.forEach((key) => {
        queryClient.setQueryData(key, (oldData) => {
          if (!oldData) {
            return oldData;
          }
          return {
            ...oldData,
            backdrop_path: data && data.backdrop_path !== undefined ? data.backdrop_path : null,
            has_local_backdrop: data && data.has_local_backdrop !== undefined ? data.has_local_backdrop : false,
          };
        });
      });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useUploadPersonBackdropMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, file }) => api.people.uploadBackdrop(personId, file),
    onSuccess: (data, variables) => {
      syncPersonBackdropCaches(queryClient, variables.personId, data);
      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useOverridePersonProfileMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, profilePath }) => api.people.overrideProfile(personId, profilePath),
    onSuccess: (data, variables) => {
      syncPersonProfileCaches(queryClient, variables.personId, data);
      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useUploadPersonProfileMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, file }) => api.people.uploadProfile(personId, file),
    onSuccess: (data, variables) => {
      syncPersonProfileCaches(queryClient, variables.personId, data);
      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useLinkPersonSourceMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, source, externalId, overrides, profileUrl }) => api.people.linkSource(personId, source, externalId, overrides, profileUrl),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail', String(variables.personId)] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['person-credits', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-credits', String(variables.personId)] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useDeletePersonMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (personId) => api.people.delete(personId),
    onSuccess: (data, personId) => {
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      queryClient.removeQueries({ queryKey: ['person-detail', personId] });
      queryClient.removeQueries({ queryKey: ['person-detail', String(personId)] });
      queryClient.removeQueries({ queryKey: ['person-credits', personId] });
      queryClient.removeQueries({ queryKey: ['person-credits', String(personId)] });
    },
  });
};

export const useUnlinkPersonSourceMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, source, action }) => api.people.unlinkSource(personId, source, action),
    onMutate: async ({ personId, source }) => {
      const idStr = String(personId);
      const idNum = Number(personId);
      const isNumValid = !isNaN(idNum);

      const personKeys = [
        ['person-detail', personId],
        ['person-detail', idStr],
      ];
      if (isNumValid) {
        personKeys.push(['person-detail', idNum]);
      }

      for (const key of personKeys) {
        await queryClient.cancelQueries({ queryKey: key });
      }

      const previousPersonDetail = queryClient.getQueryData(['person-detail', idStr]) || queryClient.getQueryData(['person-detail', personId]);

      const dbNames = [source];
      if (source === 'theporndb') dbNames.push('porndb');
      if (source === 'porndb') dbNames.push('theporndb');

      const updateData = (oldData) => {
        if (!oldData) return oldData;
        const newExternalLinks = (oldData.external_links || []).filter(
          (l) => !dbNames.includes(l.provider)
        );
        const newExternalIds = { ...(oldData.external_ids || {}) };
        dbNames.forEach((dbName) => {
          delete newExternalIds[dbName];
          delete newExternalIds[`${dbName}_id`];
        });
        
        let newPrimaryProvider = oldData.primary_provider;
        if (dbNames.includes(oldData.primary_provider)) {
          newPrimaryProvider = null;
        }

        return {
          ...oldData,
          external_links: newExternalLinks,
          external_ids: newExternalIds,
          primary_provider: newPrimaryProvider,
        };
      };

      personKeys.forEach((key) => {
        queryClient.setQueryData(key, updateData);
      });

      return { previousPersonDetail, personId };
    },
    onError: (err, variables, context) => {
      if (context && 'previousPersonDetail' in context) {
        const idStr = String(context.personId);
        const idNum = Number(context.personId);
        const isNumValid = !isNaN(idNum);

        queryClient.setQueryData(['person-detail', context.personId], context.previousPersonDetail);
        queryClient.setQueryData(['person-detail', idStr], context.previousPersonDetail);
        if (isNumValid) {
          queryClient.setQueryData(['person-detail', idNum], context.previousPersonDetail);
        }
      }
    },
    onSuccess: (data, variables) => {
      // onSuccess can still fire, but the actual invalidation happens in onSettled
    },
    onSettled: (data, error, variables) => {
      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail', String(variables.personId)] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['person-credits', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-credits', String(variables.personId)] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useSetPrimaryPersonSourceMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, source }) => api.people.setPrimarySource(personId, source),
    onSuccess: (data, variables) => {
      const idStr = String(variables.personId);
      const idNum = Number(variables.personId);
      const isNumValid = !isNaN(idNum);

      const personKeys = [
        ['person-detail', variables.personId],
        ['person-detail', idStr],
      ];
      if (isNumValid) {
        personKeys.push(['person-detail', idNum]);
      }

      personKeys.forEach((key) => {
        queryClient.setQueryData(key, (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            primary_provider: variables.source,
          };
        });
      });

      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail', String(variables.personId)] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useSetPersonFieldRoutingMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, routing }) => api.people.setFieldRouting(personId, routing),
    onSuccess: (data, variables) => {
      const idStr = String(variables.personId);
      const idNum = Number(variables.personId);
      const isNumValid = !isNaN(idNum);

      const personKeys = [
        ['person-detail', variables.personId],
        ['person-detail', idStr],
      ];
      if (isNumValid) {
        personKeys.push(['person-detail', idNum]);
      }

      personKeys.forEach((key) => {
        queryClient.setQueryData(key, (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            field_routing: variables.routing,
          };
        });
      });

      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail', String(variables.personId)] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};

export const useSavePersonCustomFieldsMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ personId, fields }) => api.people.saveCustomFields(personId, fields),
    onSuccess: (data, variables) => {
      const idStr = String(variables.personId);
      const idNum = Number(variables.personId);
      const isNumValid = !isNaN(idNum);

      const personKeys = [
        ['person-detail', variables.personId],
        ['person-detail', idStr],
      ];
      if (isNumValid) {
        personKeys.push(['person-detail', idNum]);
      }

      personKeys.forEach((key) => {
        queryClient.setQueryData(key, (oldData) => {
          if (!oldData) return oldData;
          
          let externalLinks = oldData.external_links ? [...oldData.external_links] : [];
          const manualLinkIndex = externalLinks.findIndex(l => l.provider === 'manual');
          
          const updatedManualData = {
            ...(manualLinkIndex > -1 ? externalLinks[manualLinkIndex].source_data : {}),
            ...variables.fields,
          };

          const newManualLink = {
            provider: 'manual',
            external_id: 'manual',
            profile_url: null,
            ...(manualLinkIndex > -1 ? externalLinks[manualLinkIndex] : {}),
            source_data: updatedManualData,
          };

          if (manualLinkIndex > -1) {
            externalLinks[manualLinkIndex] = newManualLink;
          } else {
            externalLinks.push(newManualLink);
          }

          return {
            ...oldData,
            external_links: externalLinks,
          };
        });
      });

      queryClient.invalidateQueries({ queryKey: ['person-detail', variables.personId] });
      queryClient.invalidateQueries({ queryKey: ['person-detail', String(variables.personId)] });
      queryClient.invalidateQueries({ queryKey: ['person-detail'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['people-infinite'] });
      queryClient.invalidateQueries({ queryKey: ['library'] });
    },
  });
};


