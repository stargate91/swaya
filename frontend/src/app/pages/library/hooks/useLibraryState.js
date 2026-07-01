import { useEffect, useState, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { useSettingsQuery } from '@/queries/settingsQueries';
import { useLibraryQuery, useCollectionsQuery, useLibraryFiltersQuery } from '@/queries/libraryQueries';
import { useLibraryTags } from './useLibraryTags';
import { usePaginationVisibility } from '../../../hooks/usePaginationVisibility';
import { useTranslation } from '@/providers/LanguageContext';
import { useLocalListSearch } from '../../../hooks/useLocalListSearch';
import { Clapperboard, Tv, Users, Tag, Layers, Video } from 'lucide-react';
import {
  getLibraryEmptyStateKey,
  getLibraryTabTranslationKey,
  isLibraryCollectionTab,
  isLibraryPeopleTab,
  isLibraryTagsTab,
  resolveLibraryBackendTab,
} from '@/lib/libraryTabs';
import { sortLibraryItems } from '../utils/librarySort';

import { useLibraryModeStore } from '@/stores/useLibraryModeStore';

export function useLibraryState({ initialTab = 'movies', lockTab = false, includeTagsTab = false } = {}) {
  const { data: settings, isLoading } = useSettingsQuery();
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState(initialTab);
  const [searchQuery, setSearchQuery] = useState('');
  const [ownershipFilter, setOwnershipFilter] = useState('owned');
  const [watchedFilter, setWatchedFilter] = useState('all');
  const [genreFilter, setGenreFilter] = useState('');
  const [collectionStatusFilter, setCollectionStatusFilter] = useState('all');
  const [peopleRoleFilter, setPeopleRoleFilter] = useState('all');
  const [genderFilter, setGenderFilter] = useState('all');
  const [favoriteFilter, setFavoriteFilter] = useState('all');
  const [decadeFilter, setDecadeFilter] = useState('all');
  const [yearFilter, setYearFilter] = useState('');
  const [performerFilter, setPerformerFilter] = useState('');
  const [studioFilter, setStudioFilter] = useState('');
  const [hairColorFilter, setHairColorFilter] = useState('');
  const [ethnicityFilter, setEthnicityFilter] = useState('');
  const [eyeColorFilter, setEyeColorFilter] = useState('');
  const [tattoosFilter, setTattoosFilter] = useState('');
  const [piercingsFilter, setPiercingsFilter] = useState('');
  const [breastTypeFilter, setBreastTypeFilter] = useState('');
  const [timeFilterMode, setTimeFilterMode] = useState('decade'); // 'decade' or 'year'
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(40);
  const [sortKey, setSortKey] = useState('title');
  const [sortDirection, setSortDirection] = useState('asc');

  const { sessionMode, setSessionMode } = useLibraryModeStore();

  const hasAdultSupport = settings?.include_adult;
  const activeSessionMode = hasAdultSupport ? sessionMode : (settings ? 'sfw' : null);

  const handleSetSessionMode = (mode) => {
    setSessionMode(mode);
    setActiveTab('movies');
    setCurrentPage(1);
    setSearchQuery('');
    setGenreFilter('');
    setCollectionStatusFilter('all');
    setPeopleRoleFilter('all');
    setGenderFilter('all');
    setFavoriteFilter('all');
    setDecadeFilter('all');
    setYearFilter('');
    setPerformerFilter('');
    setStudioFilter('');
    setHairColorFilter('');
    setEthnicityFilter('');
    setEyeColorFilter('');
    setTattoosFilter('');
    setPiercingsFilter('');
    setBreastTypeFilter('');
  };

  const isCollections = isLibraryCollectionTab(activeTab);
  const isTags = isLibraryTagsTab(activeTab);
  const isPeople = isLibraryPeopleTab(activeTab);

  const backendTab = useMemo(
    () => resolveLibraryBackendTab(activeTab, activeSessionMode),
    [activeTab, activeSessionMode]
  );

  const resolvedGenderFilter = isPeople
    ? (activeSessionMode === 'nsfw' && settings?.adult_gender_preference && settings.adult_gender_preference !== 'all'
      ? settings.adult_gender_preference
      : genderFilter)
    : undefined;

  const libraryQueryParams = useMemo(() => {
    if (isCollections || isTags || !activeSessionMode) return null;
    return {
      tab: backendTab,
      page: currentPage,
      pageSize: pageSize,
      search: searchQuery || undefined,
      sortBy: `${sortKey}_${sortDirection}`,
      filter_ownership: ownershipFilter,
      filter_watched: watchedFilter,
      selected_genre: genreFilter || undefined,
      people_role: isPeople ? peopleRoleFilter : undefined,
      filter_gender: resolvedGenderFilter,
      filter_favorite: isPeople ? favoriteFilter : undefined,
      selected_decade: decadeFilter !== 'all' ? decadeFilter : undefined,
      selected_year: yearFilter !== '' ? Number(yearFilter) : undefined,
      include_adult: activeSessionMode === 'nsfw',
      selected_performer_id: performerFilter !== '' ? Number(performerFilter) : undefined,
      selected_studio_id: studioFilter !== '' ? Number(studioFilter) : undefined,
      filter_hair_color: hairColorFilter !== '' ? hairColorFilter : undefined,
      filter_ethnicity: ethnicityFilter !== '' ? ethnicityFilter : undefined,
      filter_eye_color: eyeColorFilter !== '' ? eyeColorFilter : undefined,
      filter_tattoos: tattoosFilter !== '' ? tattoosFilter : undefined,
      filter_piercings: piercingsFilter !== '' ? piercingsFilter : undefined,
      filter_breast_type: breastTypeFilter !== '' ? breastTypeFilter : undefined,
    };
  }, [
    isCollections,
    isTags,
    activeSessionMode,
    backendTab,
    currentPage,
    pageSize,
    searchQuery,
    sortKey,
    sortDirection,
    ownershipFilter,
    watchedFilter,
    genreFilter,
    isPeople,
    peopleRoleFilter,
    resolvedGenderFilter,
    favoriteFilter,
    decadeFilter,
    yearFilter,
    performerFilter,
    studioFilter,
    hairColorFilter,
    ethnicityFilter,
    eyeColorFilter,
    tattoosFilter,
    piercingsFilter,
    breastTypeFilter
  ]);

  const { data: libraryData, isLoading: isLibraryLoading } = useLibraryQuery(
    libraryQueryParams || { tab: 'movies', page: 1, pageSize: 1, include_adult: activeSessionMode === 'nsfw' }
  );

  const { data: filterData } = useLibraryFiltersQuery(
    !isCollections && !isTags && activeSessionMode
      ? { tab: backendTab, filter_ownership: ownershipFilter, include_adult: activeSessionMode === 'nsfw' }
      : null
  );

  const { data: collectionsData, isLoading: isCollectionsLoading } = useCollectionsQuery(
    isCollections && activeSessionMode
      ? { page: 1, pageSize: 10000, tab: activeSessionMode === 'nsfw' ? 'adult' : 'movies', include_adult: activeSessionMode === 'nsfw' }
      : null
  );

  const { processedTags, isTagsLoading } = useLibraryTags({ activeSessionMode });

  const counts = libraryData?.counts || {};
  const movieCountKey = resolveLibraryBackendTab('movies', activeSessionMode);
  const tvCountKey = resolveLibraryBackendTab('tv', activeSessionMode);
  const collectionCountKey = resolveLibraryBackendTab('collections', activeSessionMode);
  const peopleCountKey = resolveLibraryBackendTab('people', activeSessionMode);
  const scenesCountKey = resolveLibraryBackendTab('scenes', activeSessionMode);

  const tabs = [
    { value: 'movies', label: t('library.tabs.movies'), count: counts[movieCountKey], icon: Clapperboard },
    ...(settings?.folder_collection_mode !== 'never' ? [
      { value: 'collections', label: t('library.tabs.collections'), count: counts[collectionCountKey], icon: Layers }
    ] : []),
    { value: 'tv', label: t('library.tabs.tv'), count: counts[tvCountKey], icon: Tv },
    ...(activeSessionMode === 'nsfw' ? [
      { value: 'scenes', label: t('library.tabs.scenes') || 'Scenes', count: counts[scenesCountKey] ?? 0, icon: Video }
    ] : []),
    { value: 'people', label: t('library.tabs.people'), count: counts[peopleCountKey], icon: Users },
    ...(includeTagsTab ? [
      { value: 'tags', label: t('library.tabs.tags'), count: processedTags.length, icon: Tag },
    ] : []),
  ];

  const fallbackTab = initialTab === 'tags' ? 'tags' : 'movies';
  const resolvedTab = tabs.some(tab => tab.value === activeTab) ? activeTab : fallbackTab;

  useEffect(() => {
    if (lockTab && activeTab !== initialTab) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setActiveTab(initialTab);
    }
  }, [activeTab, initialTab, lockTab]);

  const handleTabChange = (newTab) => {
    if (lockTab) return;
    setActiveTab(newTab);
    const tabToUse = tabs.some(tab => tab.value === newTab) ? newTab : fallbackTab;
    if (tabToUse === 'collections') {
      setSortKey('owned_count');
      setSortDirection('desc');
    } else if (tabToUse === 'tags') {
      setSortKey('total_count');
      setSortDirection('desc');
    } else if (tabToUse === 'people') {
      setSortKey('library_count');
      setSortDirection('desc');
      setPageSize(40);
    } else {
      setSortKey('title');
      setSortDirection('asc');
      setPageSize(40);
    }
    setCurrentPage(1);
    setSearchQuery('');
    setGenreFilter('');
    setCollectionStatusFilter('all');
    setPeopleRoleFilter('all');
    setGenderFilter('all');
    setFavoriteFilter('all');
    setDecadeFilter('all');
    setYearFilter('');
    setPerformerFilter('');
    setStudioFilter('');
    setHairColorFilter('');
    setEthnicityFilter('');
    setEyeColorFilter('');
    setTattoosFilter('');
    setPiercingsFilter('');
    setBreastTypeFilter('');
  };

  const handleOwnershipFilterChange = (newOwnership) => {
    setOwnershipFilter(newOwnership);
    if (newOwnership === 'unowned' && (sortKey === 'file_size' || sortKey === 'last_watched')) {
      setSortKey('title');
    }
    setCurrentPage(1);
    setSearchQuery('');
    setGenreFilter('');
    setCollectionStatusFilter('all');
    setPeopleRoleFilter('all');
    setGenderFilter('all');
    setFavoriteFilter('all');
    setDecadeFilter('all');
    setYearFilter('');
    setPerformerFilter('');
    setStudioFilter('');
    setHairColorFilter('');
    setEthnicityFilter('');
    setEyeColorFilter('');
    setTattoosFilter('');
    setPiercingsFilter('');
    setBreastTypeFilter('');
  };

  const handleFilterChange = (setter) => (val) => {
    setter(val);
    setCurrentPage(1);
  };

  const handleSearchQueryChange = (val) => {
    setSearchQuery(val);
    setCurrentPage(1);
  };

  const handlePageChange = (page) => {
    setCurrentPage(Math.max(1, Number(page) || 1));
  };

  const handlePageSizeChange = (size) => {
    setPageSize(size);
    setCurrentPage(1);
  };

  const getEmptyStateIcon = () => {
    switch (resolvedTab) {
      case 'movies': return Clapperboard;
      case 'collections': return Layers;
      case 'tv': return Tv;
      case 'people': return Users;
      case 'tags': return Tag;
      case 'scenes': return Video;
      default: return initialTab === 'tags' ? Tag : Clapperboard;
    }
  };

  const isServerPaged = !isCollections && !isTags;

  const allItems = useMemo(() => {
    return isCollections
      ? (collectionsData?.items || [])
      : isTags
        ? processedTags
        : (libraryData?.items || []);
  }, [isCollections, collectionsData?.items, isTags, processedTags, libraryData?.items]);

  const localFilteredItems = useLocalListSearch(allItems, searchQuery);

  const { sortedItems, paginatedItems, totalItems, totalPages } = useMemo(() => {
    if (isServerPaged) {
      return {
        sortedItems: allItems,
        paginatedItems: allItems,
        totalItems: libraryData?.total_items || 0,
        totalPages: libraryData?.total_pages || 1,
      };
    }

    let filtered = localFilteredItems;
    if (isCollections) {
      filtered = filtered.filter(item => {
        const owned = Number(item.owned_count) || 0;
        const total = Number(item.total_count) || 0;
        if (collectionStatusFilter === 'complete') return owned === total;
        if (collectionStatusFilter === 'in_progress') return owned > 0 && owned < total;
        return true;
      });
    }

    const sorted = sortLibraryItems(filtered, resolvedTab, sortKey, sortDirection);
    const total = sorted.length;
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const paginated = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    return {
      sortedItems: sorted,
      paginatedItems: paginated,
      totalItems: total,
      totalPages: pages,
    };
  }, [
    isServerPaged,
    allItems,
    libraryData?.total_items,
    libraryData?.total_pages,
    localFilteredItems,
    isCollections,
    collectionStatusFilter,
    resolvedTab,
    sortKey,
    sortDirection,
    currentPage,
    pageSize,
  ]);

  // Background Prefetch next/prev pages
  useEffect(() => {
    if (isServerPaged && libraryQueryParams) {
      if (currentPage < totalPages) {
        const nextParams = { ...libraryQueryParams, page: currentPage + 1 };
        queryClient.prefetchQuery({
          queryKey: ['library', nextParams],
          queryFn: ({ signal }) => api.library.getItems(nextParams, { signal }),
        });
      }
      if (currentPage > 1) {
        const prevParams = { ...libraryQueryParams, page: currentPage - 1 };
        queryClient.prefetchQuery({
          queryKey: ['library', prevParams],
          queryFn: ({ signal }) => api.library.getItems(prevParams, { signal }),
        });
      }
    }
  }, [isServerPaged, libraryQueryParams, currentPage, totalPages, queryClient]);

  const translationKey = getLibraryTabTranslationKey(resolvedTab, activeSessionMode);
  const emptyStateTranslationKey = getLibraryEmptyStateKey(resolvedTab, activeSessionMode);

  const tabTotalCount = counts[backendTab] ?? allItems.length;
  const tabLabel = t(`library.tabs.${translationKey}`);
  const searchPlaceholder = t('library.searchPlaceholder').replace('{{tab}}', tabLabel);
  const hasSearchQuery = searchQuery.trim().length > 0;
  const hasFilterSelection = Boolean(
    (isCollections && collectionStatusFilter !== 'all') ||
    (isPeople && peopleRoleFilter !== 'all') ||
    (isPeople && genderFilter !== 'all') ||
    (isPeople && favoriteFilter !== 'all') ||
    (!isCollections && !isTags && !isPeople && (
      ownershipFilter !== 'owned' ||
      watchedFilter !== 'all' ||
      genreFilter !== '' ||
      decadeFilter !== 'all' ||
      yearFilter !== ''
    ))
  );
  const hasActiveFilters = tabTotalCount > 0 && totalItems === 0 && (hasSearchQuery || hasFilterSelection);
  const emptyStateVariant = hasSearchQuery
    ? 'page-search'
    : hasFilterSelection
      ? 'page-filter'
      : 'default';
  const emptyTitle = hasSearchQuery
    ? (t('library.emptyStates.search.title', { tab: tabLabel }) || `No matching ${tabLabel} found`)
    : hasFilterSelection
      ? (t('library.emptyStates.filter.title', { tab: tabLabel }) || 'Nothing fits these filters')
      : t(`library.emptyStates.${emptyStateTranslationKey}.title`);
  const emptyDescription = hasSearchQuery
    ? (t('library.emptyStates.search.description', { tab: tabLabel }) || 'Try a different search term or check the spelling.')
    : hasFilterSelection
      ? (t('library.emptyStates.filter.description', { tab: tabLabel }) || `Try clearing or relaxing a few filters to bring ${tabLabel} back into view.`)
      : t(`library.emptyStates.${emptyStateTranslationKey}.description`);
  const emptyIcon = getEmptyStateIcon();
  const shouldShowPagination = usePaginationVisibility(totalItems, pageSize);

  const summaryText = totalItems > 0
    ? `${(currentPage - 1) * pageSize + 1}-${Math.min(currentPage * pageSize, totalItems)} / ${totalItems}`
    : '0-0 / 0';

  const isDataLoading = (!isCollections && !isTags && isLibraryLoading) ||
    (isCollections && isCollectionsLoading) ||
    (isTags && isTagsLoading);

  return {
    settings,
    isLoading,
    t,
    activeTab,
    setActiveTab: handleTabChange,
    searchQuery,
    setSearchQuery: handleSearchQueryChange,
    ownershipFilter,
    setOwnershipFilter: handleOwnershipFilterChange,
    watchedFilter,
    setWatchedFilter: handleFilterChange(setWatchedFilter),
    genreFilter,
    setGenreFilter: handleFilterChange(setGenreFilter),
    collectionStatusFilter,
    setCollectionStatusFilter: handleFilterChange(setCollectionStatusFilter),
    peopleRoleFilter,
    setPeopleRoleFilter: handleFilterChange(peopleRoleFilter ? setPeopleRoleFilter : null),
    genderFilter,
    setGenderFilter: handleFilterChange(setGenderFilter),
    favoriteFilter,
    setFavoriteFilter: handleFilterChange(setFavoriteFilter),
    decadeFilter,
    setDecadeFilter: handleFilterChange(setDecadeFilter),
    yearFilter,
    setYearFilter: handleFilterChange(setYearFilter),
    timeFilterMode,
    setTimeFilterMode,
    currentPage,
    setCurrentPage: handlePageChange,
    pageSize,
    setPageSize: handlePageSizeChange,
    sortKey,
    setSortKey,
    sortDirection,
    setSortDirection,
    performerFilter,
    setPerformerFilter: handleFilterChange(setPerformerFilter),
    studioFilter,
    setStudioFilter: handleFilterChange(setStudioFilter),
    hairColorFilter,
    setHairColorFilter: handleFilterChange(setHairColorFilter),
    ethnicityFilter,
    setEthnicityFilter: handleFilterChange(setEthnicityFilter),
    eyeColorFilter,
    setEyeColorFilter: handleFilterChange(setEyeColorFilter),
    tattoosFilter,
    setTattoosFilter: handleFilterChange(setTattoosFilter),
    piercingsFilter,
    setPiercingsFilter: handleFilterChange(setPiercingsFilter),
    breastTypeFilter,
    setBreastTypeFilter: handleFilterChange(setBreastTypeFilter),
    isCollections,
    isTags,
    isPeople,
    tabs,
    resolvedTab,
    filterData,
    emptyTitle,
    emptyDescription,
    emptyStateVariant,
    emptyIcon,
    hasActiveFilters,
    searchPlaceholder,
    sortedItems,
    paginatedItems,
    totalPages,
    shouldShowPagination,
    summaryText,
    isDataLoading,
    sessionMode,
    activeSessionMode,
    setSessionMode: handleSetSessionMode,
  };
}

