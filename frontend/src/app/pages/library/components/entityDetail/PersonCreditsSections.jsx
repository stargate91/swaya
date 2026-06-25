import { useState, useCallback, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import PersonCreditsGridSection from './PersonCreditsGridSection';
import { usePersonCreditsQuery } from '@/queries/metadataQueries';

export default function PersonCreditsSections({ id, item, navigate, t }) {
  const hasMovies = Number(item?.total_movie_credits) > 0;
  const hasTv = Number(item?.total_tv_credits) > 0;
  const hasStashDb = !!item?.external_ids?.stashdb_id;
  const hasFansDb = !!item?.external_ids?.fansdb_id;
  const hasPornDb = !!item?.external_ids?.theporndb_id || !!item?.external_ids?.porndb_id || !!item?.external_ids?.porndb;

  const hasScenes = Number(item?.total_scene_credits) > 0 || (item?.is_adult && (hasStashDb || hasFansDb));
  const showSplitScenes = hasScenes && hasStashDb && hasFansDb;

  const fansdbQuery = usePersonCreditsQuery(id, 'scenes', 1, 12, {
    enabled: !!(item?.is_adult && hasFansDb),
    source: 'fansdb',
  });

  const stashdbQuery = usePersonCreditsQuery(id, 'scenes', 1, 12, {
    enabled: !!(item?.is_adult && hasStashDb),
    source: 'stashdb',
  });

  const porndbMoviesQuery = usePersonCreditsQuery(id, 'movies', 1, 12, {
    enabled: !!(item?.is_adult && hasPornDb),
    source: 'porndb',
  });

  const porndbScenesQuery = usePersonCreditsQuery(id, 'scenes', 1, 12, {
    enabled: !!(item?.is_adult && hasPornDb),
    source: 'porndb',
  });

  const [tabCounts, setTabCounts] = useState({
    movies: Number(item?.total_movie_credits) || 0,
    tv: Number(item?.total_tv_credits) || 0,
    scenes: Number(item?.total_scene_credits) || 0,
    scenes_stashdb: hasStashDb ? (Number(item?.total_scene_credits) || 0) : 0,
    scenes_fansdb: 0,
    movies_porndb: 0,
    scenes_porndb: 0,
  });

  useEffect(() => {
    if (item?.is_adult && hasFansDb && fansdbQuery.data?.total_items !== undefined) {
      setTabCounts((prev) => ({
        ...prev,
        scenes_fansdb: fansdbQuery.data.total_items,
        ...(!hasStashDb ? { scenes: fansdbQuery.data.total_items } : {}),
      }));
    }
  }, [item?.is_adult, hasFansDb, hasStashDb, fansdbQuery.data?.total_items]);

  useEffect(() => {
    if (item?.is_adult && hasStashDb && stashdbQuery.data?.total_items !== undefined) {
      setTabCounts((prev) => ({
        ...prev,
        scenes_stashdb: stashdbQuery.data.total_items,
        ...(!hasFansDb ? { scenes: stashdbQuery.data.total_items } : {}),
      }));
    }
  }, [item?.is_adult, hasStashDb, hasFansDb, stashdbQuery.data?.total_items]);

  useEffect(() => {
    if (item?.is_adult && hasPornDb) {
      if (porndbMoviesQuery.data?.total_items !== undefined) {
        setTabCounts((prev) => ({
          ...prev,
          movies_porndb: porndbMoviesQuery.data.total_items,
        }));
      }
      if (porndbScenesQuery.data?.total_items !== undefined) {
        setTabCounts((prev) => ({
          ...prev,
          scenes_porndb: porndbScenesQuery.data.total_items,
        }));
      }
    }
  }, [item?.is_adult, hasPornDb, porndbMoviesQuery.data?.total_items, porndbScenesQuery.data?.total_items]);

  const [activeTab, setActiveTab] = useState(() => {
    if (hasMovies) return 'movies';
    if (hasTv) return 'tv';
    if (hasScenes) {
      if (showSplitScenes) {
        return 'scenes_stashdb';
      }
      return 'scenes';
    }
    return '';
  });

  const [paginationInfo, setPaginationInfo] = useState(null);

  const tabs = [];
  if (hasMovies) {
    tabs.push({ id: 'movies', label: t('library.details.moviesTitle') || 'Movies', count: tabCounts.movies });
  }
  if (hasTv) {
    tabs.push({ id: 'tv', label: t('library.details.tvShowsTitle') || 'TV Shows', count: tabCounts.tv });
  }

  if (showSplitScenes) {
    tabs.push({ id: 'scenes_stashdb', label: t('library.details.stashdbScenes') || 'StashDB Scenes', count: tabCounts.scenes_stashdb });
    tabs.push({ id: 'scenes_fansdb', label: t('library.details.fansdbScenes') || 'FansDB Scenes', count: tabCounts.scenes_fansdb });
  } else if (hasScenes) {
    const label = hasStashDb
      ? (t('library.details.stashdbScenes') || 'StashDB Scenes')
      : hasFansDb
      ? (t('library.details.fansdbScenes') || 'FansDB Scenes')
      : (t('library.details.scenesTitle') || 'Scenes');
    tabs.push({ id: 'scenes', label, count: tabCounts.scenes });
  }

  if (item?.is_adult && hasPornDb) {
    if (tabCounts.movies_porndb > 0) {
      tabs.push({ id: 'movies_porndb', label: t('library.details.porndbMovies') || 'PornDB Movies', count: tabCounts.movies_porndb });
    }
    if (tabCounts.scenes_porndb > 0) {
      tabs.push({ id: 'scenes_porndb', label: t('library.details.porndbScenes') || 'PornDB Scenes', count: tabCounts.scenes_porndb });
    }
  }

  useEffect(() => {
    if (tabs.length > 0 && !tabs.some((t) => t.id === activeTab)) {
      setActiveTab(tabs[0].id);
    }
  }, [tabs, activeTab]);

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setPaginationInfo(null);
  };

  const handlePaginationData = useCallback((tabId, data) => {
    setPaginationInfo(data);
    if (data?.totalCount !== undefined) {
      setTabCounts((prev) => {
        if (prev[tabId] === data.totalCount) return prev;
        return { ...prev, [tabId]: data.totalCount };
      });
    }
  }, []);

  const handleMoviesPagination = useCallback((data) => handlePaginationData('movies', data), [handlePaginationData]);
  const handleTvPagination = useCallback((data) => handlePaginationData('tv', data), [handlePaginationData]);
  const handleScenesPagination = useCallback((data) => handlePaginationData('scenes', data), [handlePaginationData]);
  const handleStashDbPagination = useCallback((data) => handlePaginationData('scenes_stashdb', data), [handlePaginationData]);
  const handleFansDbPagination = useCallback((data) => handlePaginationData('scenes_fansdb', data), [handlePaginationData]);
  const handlePornDbMoviesPagination = useCallback((data) => handlePaginationData('movies_porndb', data), [handlePaginationData]);
  const handlePornDbScenesPagination = useCallback((data) => handlePaginationData('scenes_porndb', data), [handlePaginationData]);

  return (
    <div className="person-credits-section-container">
      {(tabs.length > 1 || (paginationInfo && paginationInfo.totalPages > 1)) && (
        <div className="person-credits-tabs">
          {tabs.length > 1 && tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`person-credits-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => handleTabChange(tab.id)}
            >
              {tab.label}
              {tab.count > 0 && <span className="person-credits-tab-count">{tab.count}</span>}
            </button>
          ))}

          {paginationInfo && paginationInfo.totalPages > 1 && (
            <div className="entity-detail-page__section-pager" style={{ marginLeft: 'auto' }}>
              <button
                type="button"
                className="entity-detail-page__section-pager-btn"
                onClick={() => paginationInfo.setPage((current) => Math.max(1, current - 1))}
                disabled={paginationInfo.page <= 1}
                aria-label={t('common.previous') || 'Previous'}
              >
                <ChevronLeft size={16} />
              </button>
              <button
                type="button"
                className="entity-detail-page__section-pager-btn"
                onClick={() => paginationInfo.setPage((current) => Math.min(paginationInfo.totalPages, current + 1))}
                disabled={paginationInfo.page >= paginationInfo.totalPages}
                aria-label={t('common.next') || 'Next'}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'movies' && hasMovies && (
        <PersonCreditsGridSection
          key={`${id}-movies`}
          title={t('library.details.moviesTitle') || 'Movies'}
          personId={id}
          mediaType="movies"
          totalCount={tabCounts.movies}
          initialPageData={item?.initial_movie_credits_page}
          navigate={navigate}
          t={t}
          onPaginationData={handleMoviesPagination}
        />
      )}

      {activeTab === 'tv' && hasTv && (
        <PersonCreditsGridSection
          key={`${id}-tv`}
          title={t('library.details.tvShowsTitle') || 'TV Shows'}
          personId={id}
          mediaType="tv"
          totalCount={tabCounts.tv}
          initialPageData={item?.initial_tv_credits_page}
          navigate={navigate}
          t={t}
          onPaginationData={handleTvPagination}
        />
      )}

      {activeTab === 'scenes' && hasScenes && (
        <PersonCreditsGridSection
          key={`${id}-scenes`}
          title={t('library.details.scenesTitle') || 'Scenes'}
          personId={id}
          mediaType="scenes"
          source={hasStashDb ? 'stashdb' : hasFansDb ? 'fansdb' : undefined}
          totalCount={tabCounts.scenes}
          initialPageData={item?.initial_scene_credits_page}
          navigate={navigate}
          t={t}
          onPaginationData={handleScenesPagination}
        />
      )}

      {activeTab === 'scenes_stashdb' && showSplitScenes && (
        <PersonCreditsGridSection
          key={`${id}-scenes-stashdb`}
          title={t('library.details.stashdbScenes') || 'StashDB Scenes'}
          personId={id}
          mediaType="scenes"
          source="stashdb"
          totalCount={tabCounts.scenes_stashdb}
          initialPageData={item?.initial_scene_credits_page}
          navigate={navigate}
          t={t}
          onPaginationData={handleStashDbPagination}
        />
      )}

      {activeTab === 'scenes_fansdb' && showSplitScenes && (
        <PersonCreditsGridSection
          key={`${id}-scenes-fansdb`}
          title={t('library.details.fansdbScenes') || 'FansDB Scenes'}
          personId={id}
          mediaType="scenes"
          source="fansdb"
          totalCount={tabCounts.scenes_fansdb}
          initialPageData={undefined}
          navigate={navigate}
          t={t}
          onPaginationData={handleFansDbPagination}
        />
      )}

      {activeTab === 'movies_porndb' && item?.is_adult && hasPornDb && (
        <PersonCreditsGridSection
          key={`${id}-movies-porndb`}
          title={t('library.details.porndbMovies') || 'PornDB Movies'}
          personId={id}
          mediaType="movies"
          source="porndb"
          totalCount={tabCounts.movies_porndb}
          initialPageData={undefined}
          navigate={navigate}
          t={t}
          onPaginationData={handlePornDbMoviesPagination}
        />
      )}

      {activeTab === 'scenes_porndb' && item?.is_adult && hasPornDb && (
        <PersonCreditsGridSection
          key={`${id}-scenes-porndb`}
          title={t('library.details.porndbScenes') || 'PornDB Scenes'}
          personId={id}
          mediaType="scenes"
          source="porndb"
          totalCount={tabCounts.scenes_porndb}
          initialPageData={undefined}
          navigate={navigate}
          t={t}
          onPaginationData={handlePornDbScenesPagination}
        />
      )}
    </div>
  );
}
