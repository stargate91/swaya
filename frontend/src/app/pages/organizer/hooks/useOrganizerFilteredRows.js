import { useMemo } from 'react';
import {
  EXTRA_CATEGORY_BY_TAB,
  MANUAL_REVIEW_STATUSES,
  mapOrganizerItemRow,
  mapExtraRow,
  MATCHED_STATUSES,
  normalizeItemStatus,
} from '../organizerMappers';
import { isMovieMediaType, isTvLikeMediaType } from '@/lib/mediaTypes';

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
  if (scanMode === 'scenes') return isModeType({ type: item.parent_type }, scanMode);
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
  const matchesSessionMode = useMemo(() => {
    return (item) => {
      const itemScanMode = item.scan_mode || '';
      const isAdultScanModeOrType = (
        String(item.type).toLowerCase() === 'scene'
        || itemScanMode === 'porndb_movie'
        || itemScanMode === 'scenes'
      );

      let isAdult = false;
      if (isAdultScanModeOrType) {
        isAdult = true;
      } else {
        const activeMatch = item.matches?.find((m) => m.is_active) || item.matches?.[0];
        if (activeMatch) {
          isAdult = activeMatch.is_adult;
        }
      }

      return sessionMode === 'nsfw' ? isAdult : !isAdult;
    };
  }, [sessionMode]);

  const matchesSessionModeExtra = useMemo(() => {
    return (extra) => {
      const parentIsAdult = (extra.parent_is_adult !== undefined && extra.parent_is_adult !== null)
        ? extra.parent_is_adult
        : (extra.parent_type === 'scene' || (extra.parent_scan_mode || '') === 'scenes' || (extra.parent_scan_mode || '') === 'porndb_movie');

      return sessionMode === 'nsfw' ? parentIsAdult : !parentIsAdult;
    };
  }, [sessionMode]);

  const matchesCurrentScanMode = useMemo(() => {
    return (item) => {
      const itemScanMode = item.scan_mode || '';
      if (scanMode === 'scenes') return itemScanMode === 'scenes';
      if (scanMode === 'movies_tv') return itemScanMode === 'movies_tv' || itemScanMode === 'porndb_movie';
      return true;
    };
  }, [scanMode]);

  const matchesCurrentScanModeExtra = useMemo(() => {
    return (extra) => {
      const parentScanMode = extra.parent_scan_mode || '';
      if (scanMode === 'scenes') return parentScanMode === 'scenes';
      if (scanMode === 'movies_tv') return parentScanMode !== 'scenes';
      return true;
    };
  }, [scanMode]);

  const sessionReviewOrganizerMedia = useMemo(
    () => [
      ...(organizer.manual || []),
      ...(organizer.movies || []),
      ...(organizer.tv || []),
    ].filter(matchesSessionMode),
    [organizer, matchesSessionMode],
  );

  const sessionMatchedOrganizerMedia = useMemo(
    () => [
      ...(organizer.movies || []),
      ...(organizer.tv || []),
      ...(organizer.collisions || []),
    ].filter(matchesSessionMode),
    [organizer, matchesSessionMode],
  );

  const reviewOrganizerMedia = useMemo(
    () => sessionReviewOrganizerMedia.filter(matchesCurrentScanMode),
    [matchesCurrentScanMode, sessionReviewOrganizerMedia],
  );

  const matchedOrganizerMedia = useMemo(
    () => sessionMatchedOrganizerMedia.filter(matchesCurrentScanMode),
    [matchesCurrentScanMode, sessionMatchedOrganizerMedia],
  );

  const sessionFilteredExtras = useMemo(
    () => (organizer.extras || []).filter(matchesSessionModeExtra),
    [organizer.extras, matchesSessionModeExtra],
  );

  const filteredExtras = useMemo(
    () => sessionFilteredExtras.filter(matchesCurrentScanModeExtra),
    [matchesCurrentScanModeExtra, sessionFilteredExtras],
  );

  const sessionVisibleMediaCount = useMemo(() => {
    const ids = new Set([
      ...sessionReviewOrganizerMedia.map((item) => item.id),
      ...sessionMatchedOrganizerMedia.map((item) => item.id),
    ]);
    return ids.size;
  }, [sessionMatchedOrganizerMedia, sessionReviewOrganizerMedia]);

  const visibleMediaCount = useMemo(() => {
    const ids = new Set([
      ...reviewOrganizerMedia.map((item) => item.id),
      ...matchedOrganizerMedia.map((item) => item.id),
    ]);
    return ids.size;
  }, [matchedOrganizerMedia, reviewOrganizerMedia]);

  const modeVisibleMatchedItems = useMemo(() => (
    matchedOrganizerMedia.filter((item) => {
      const id = `item-${item.id}`;
      return !dismissedRowIds.has(id)
        && isModeType(item, scanMode)
        && MATCHED_STATUSES.has(normalizeItemStatus(item.status));
    })
  ), [dismissedRowIds, matchedOrganizerMedia, scanMode]);

  const modeVisibleMatchedItemIds = useMemo(
    () => new Set(modeVisibleMatchedItems.map((item) => item.id)),
    [modeVisibleMatchedItems],
  );

  const modeVisibleExtrasForRename = useMemo(() => (
    filteredExtras.filter((item) => {
      const id = `extra-${item.id}`;
      const parentId = item.parent_id || item.parent_item_id;
      const parentRowId = `item-${parentId}`;
      return isExtraForMode(item, scanMode)
        && modeVisibleMatchedItemIds.has(parentId)
        && !dismissedRowIds.has(id)
        && !dismissedRowIds.has(parentRowId);
    })
  ), [dismissedRowIds, filteredExtras, modeVisibleMatchedItemIds, scanMode]);

  const tabCounts = useMemo(() => {
    const visibleReview = reviewOrganizerMedia.filter((item) => {
      const id = `item-${item.id}`;
      return !dismissedRowIds.has(id)
        && isModeType(item, scanMode)
        && MANUAL_REVIEW_STATUSES.has(normalizeItemStatus(item.status));
    });
    const visibleMatched = modeVisibleMatchedItems;

    const manualCount = visibleReview.length;
    const manualMoviesCount = visibleReview.filter((item) => isRegularMovieType(item.type)).length;
    const manualEpisodesCount = visibleReview.filter((item) => isTvLikeMediaType(item.type)).length;
    const manualScenesCount = visibleReview.filter((item) => isSceneType(item.type)).length;
    const moviesCount = visibleMatched.filter((item) => isRegularMovieType(item.type)).length;
    const episodesCount = visibleMatched.filter((item) => isTvLikeMediaType(item.type)).length;
    const scenesCount = visibleMatched.filter((item) => isSceneType(item.type)).length;

    const extrasCount = modeVisibleExtrasForRename.length;

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
  }, [dismissedRowIds, modeVisibleExtrasForRename.length, modeVisibleMatchedItems, reviewOrganizerMedia, scanMode]);

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
        .filter((item) => isTvLikeMediaType(item.type) && MATCHED_STATUSES.has(normalizeItemStatus(item.status)))
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
      (row) => !dismissedRowIds.has(row.id)
        && (row.rawType !== 'extra' || !dismissedRowIds.has(`item-${row.parent_id}`)),
    );
  }, [activeExtrasTab, activeManualTab, activeMainTab, matchedOrganizerMedia, reviewOrganizerMedia, t, dismissedRowIds, scanMode, filteredExtras]);

  return {
    visibleMediaCount,
    visibleExtraCount: filteredExtras.length,
    sessionVisibleMediaCount,
    sessionVisibleExtraCount: sessionFilteredExtras.length,
    reviewOrganizerMedia,
    matchedOrganizerMedia,
    modeVisibleMatchedItems,
    modeVisibleExtrasForRename,
    tabCounts,
    tabFilteredRows,
  };
}
