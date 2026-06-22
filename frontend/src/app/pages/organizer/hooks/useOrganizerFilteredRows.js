import { useMemo } from 'react';
import {
  EXTRA_CATEGORY_BY_TAB,
  MANUAL_REVIEW_STATUSES,
  mapOrganizerItemRow,
  mapExtraRow,
  MATCHED_STATUSES,
  normalizeItemStatus,
} from '../organizerMappers';
import { isEpisodeMediaType, isMovieMediaType, isTvLikeMediaType } from '@/lib/mediaTypes';

const normalizeType = (value) => String(value || '').toLowerCase();
const isSceneType = (value) => normalizeType(value) === 'scene';
const isRegularMovieType = (value) => isMovieMediaType(value);
const isPornDbMovieMode = (scanMode) => scanMode === 'porndb_movie';

const isModeType = (item, scanMode) => {
  if (scanMode === 'scenes') return isSceneType(item.type);
  if (isPornDbMovieMode(scanMode)) return isRegularMovieType(item.type);
  return !isSceneType(item.type);
};

const isExtraForMode = (item, scanMode) => {
  if (scanMode === 'scenes' && item.category === 'video') return false;
  return isModeType({ type: item.parent_type }, scanMode);
};

export function useOrganizerFilteredRows({
  organizer,
  t,
  activeMainTab,
  activeExtrasTab,
  activeManualTab,
  dismissedRowIds,
  scanMode,
  sessionMode,
}) {
  const isAdultPath = (path) => {
    if (!path) return false;
    const p = path.toLowerCase();
    return p.includes('adult') || p.includes('porn') || p.includes('xxx') || p.includes('scenes');
  };

  const matchesSessionMode = useMemo(() => {
    return (item) => {
      const itemScanMode = item.scan_mode || '';
      
      // 1. Within NSFW mode: movies_tv vs scenes
      if (scanMode === 'scenes') {
        if (itemScanMode !== 'scenes') return false;
      } else if (scanMode === 'movies_tv') {
        if (itemScanMode !== 'movies_tv' && itemScanMode !== 'porndb_movie') return false;
      }

      // 2. SFW vs NSFW mode separation
      const isAdult = item.matches?.some(m => m.is_adult) || 
                      String(item.type).toLowerCase() === 'scene' || 
                      itemScanMode === 'porndb_movie' || 
                      itemScanMode === 'scenes' ||
                      isAdultPath(item.current_path);

      if (sessionMode === 'nsfw') {
        return isAdult;
      } else {
        return !isAdult;
      }
    };
  }, [sessionMode, scanMode]);

  const matchesSessionModeExtra = useMemo(() => {
    return (extra) => {
      const parentScanMode = extra.parent_scan_mode || '';

      // 1. Within NSFW mode: movies_tv vs scenes
      if (scanMode === 'scenes') {
        if (parentScanMode !== 'scenes') return false;
      } else if (scanMode === 'movies_tv') {
        if (parentScanMode === 'scenes') return false;
      }

      // 2. SFW vs NSFW mode separation
      const parentIsAdult = extra.parent_type === 'scene' || 
                            parentScanMode === 'scenes' || 
                            parentScanMode === 'porndb_movie' || 
                            isAdultPath(extra.path);

      if (sessionMode === 'nsfw') {
        return parentIsAdult;
      } else {
        return !parentIsAdult;
      }
    };
  }, [sessionMode, scanMode]);

  const reviewOrganizerMedia = useMemo(
    () => [
      ...(organizer.manual || []),
      ...(organizer.movies || []),
      ...(organizer.tv || []),
    ].filter(matchesSessionMode),
    [organizer, matchesSessionMode],
  );

  const matchedOrganizerMedia = useMemo(
    () => [
      ...(organizer.movies || []),
      ...(organizer.tv || []),
      ...(organizer.collisions || []),
    ].filter(matchesSessionMode),
    [organizer, matchesSessionMode],
  );

  const filteredExtras = useMemo(() => {
    return (organizer.extras || []).filter(matchesSessionModeExtra);
  }, [organizer.extras, matchesSessionModeExtra]);

  const tabCounts = useMemo(() => {
    const visibleReview = reviewOrganizerMedia.filter((item) => {
      const id = `item-${item.id}`;
      return !dismissedRowIds.has(id)
        && isModeType(item, scanMode)
        && MANUAL_REVIEW_STATUSES.has(normalizeItemStatus(item.status));
    });
    const visibleMatched = matchedOrganizerMedia.filter((item) => {
      const id = `item-${item.id}`;
      return !dismissedRowIds.has(id)
        && isModeType(item, scanMode)
        && MATCHED_STATUSES.has(normalizeItemStatus(item.status));
    });

    const manualCount = visibleReview.length;
    const manualMoviesCount = visibleReview.filter((item) => isRegularMovieType(item.type)).length;
    const manualEpisodesCount = visibleReview.filter((item) => isTvLikeMediaType(item.type)).length;
    const manualScenesCount = visibleReview.filter((item) => isSceneType(item.type)).length;
    const moviesCount = visibleMatched.filter((item) => isRegularMovieType(item.type)).length;
    const episodesCount = visibleMatched.filter((item) => isEpisodeMediaType(item.type)).length;
    const scenesCount = visibleMatched.filter((item) => isSceneType(item.type)).length;

    const extrasCount = filteredExtras.filter((item) => {
      const id = `extra-${item.id}`;
      const parentId = `item-${item.parent_id || item.parent_item_id}`;
      return isExtraForMode(item, scanMode) && !dismissedRowIds.has(id) && !dismissedRowIds.has(parentId);
    }).length;

    return {
      manualCount,
      manualMoviesCount,
      manualEpisodesCount,
      manualScenesCount,
      moviesCount,
      episodesCount,
      scenesCount,
      extrasCount,
    };
  }, [organizer, matchedOrganizerMedia, reviewOrganizerMedia, dismissedRowIds, scanMode, filteredExtras]);

  const tabFilteredRows = useMemo(() => {
    let rows = [];
    if (activeMainTab === 'manual') {
      rows = reviewOrganizerMedia
        .filter((item) => {
          const statusMatches = MANUAL_REVIEW_STATUSES.has(normalizeItemStatus(item.status));
          if (!statusMatches) return false;
          if (activeManualTab === 'movies') return isRegularMovieType(item.type);
          if (activeManualTab === 'episodes') return isTvLikeMediaType(item.type);
          if (activeManualTab === 'scenes') return isSceneType(item.type);
          return false;
        })
        .map((item) => mapOrganizerItemRow(item, t));
    } else if (activeMainTab === 'movies') {
      rows = matchedOrganizerMedia
        .filter((item) => isRegularMovieType(item.type) && MATCHED_STATUSES.has(normalizeItemStatus(item.status)))
        .map((item) => mapOrganizerItemRow(item, t));
    } else if (activeMainTab === 'episodes') {
      rows = matchedOrganizerMedia
        .filter((item) => isEpisodeMediaType(item.type) && MATCHED_STATUSES.has(normalizeItemStatus(item.status)))
        .map((item) => mapOrganizerItemRow(item, t));
    } else if (activeMainTab === 'scenes') {
      rows = matchedOrganizerMedia
        .filter((item) => isSceneType(item.type) && MATCHED_STATUSES.has(normalizeItemStatus(item.status)))
        .map((item) => mapOrganizerItemRow(item, t));
    } else if (activeMainTab === 'extras') {
      rows = filteredExtras
        .filter((item) => isExtraForMode(item, scanMode) && item.category === EXTRA_CATEGORY_BY_TAB[activeExtrasTab])
        .map((item) => mapExtraRow(item, t));
    }

    return rows.filter(
      (row) =>
        !dismissedRowIds.has(row.id) &&
        (row.rawType !== 'extra' || !dismissedRowIds.has(`item-${row.parent_id}`))
    );
  }, [activeExtrasTab, activeManualTab, activeMainTab, organizer, matchedOrganizerMedia, reviewOrganizerMedia, t, dismissedRowIds, scanMode]);

  return {
    reviewOrganizerMedia,
    matchedOrganizerMedia,
    tabCounts,
    tabFilteredRows,
  };
}
