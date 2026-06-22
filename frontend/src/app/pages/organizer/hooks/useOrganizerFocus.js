import {
  EXTRA_CATEGORY_BY_TAB,
  MANUAL_REVIEW_STATUSES,
  mapOrganizerItemRow,
  mapExtraRow,
  MATCHED_STATUSES,
  normalizeItemStatus,
} from '../organizerMappers';
import { scrollOrganizerToTop } from '../organizerScroll';
import { isEpisodeMediaType, isMovieMediaType, isTvLikeMediaType } from '@/lib/mediaTypes';

const normalizeType = (value) => String(value || '').toLowerCase();
const isSceneType = (value) => normalizeType(value) === 'scene';
const isRegularMovieType = (value) => isMovieMediaType(value);
const isPornDbMovieMode = (scanMode) => scanMode === 'porndb_movie';

const isExtraForMode = (item, scanMode) => {
  const parentType = String(item.parent_type || '').toLowerCase();
  if (scanMode === 'scenes') return parentType === 'scene' && item.category !== 'video';
  if (isPornDbMovieMode(scanMode)) return parentType === 'movie';
  return parentType !== 'scene';
};

export function useOrganizerFocus({
  organizer,
  t,
  activeRowId,
  setActiveRowId,
  setActiveMainTab,
  setActiveExtrasTab,
  setActiveManualTab,
  setSearchQuery,
  setSelectedRowIds,
  setCurrentPage,
  setIsDetailsCollapsed,
  scanMode,
}) {
  const focusFirstAvailableResult = (nextOrganizer = organizer) => {
    const modeExtras = (nextOrganizer.extras || []).filter((item) => isExtraForMode(item, scanMode));
    if (activeRowId) {
      const allIds = new Set([
        ...(nextOrganizer.manual || []).map((i) => `item-${i.id}`),
        ...(nextOrganizer.movies || []).map((i) => `item-${i.id}`),
        ...(nextOrganizer.tv || []).map((i) => `item-${i.id}`),
        ...(nextOrganizer.collisions || []).map((i) => `item-${i.id}`),
        ...modeExtras.map((i) => `extra-${i.id}`),
      ]);
      if (allIds.has(activeRowId)) {
        return;
      }
    }
    const reviewMedia = [
      ...(nextOrganizer.manual || []),
      ...(nextOrganizer.movies || []),
      ...(nextOrganizer.tv || []),
    ];
    const matchedMedia = [
      ...(nextOrganizer.movies || []),
      ...(nextOrganizer.tv || []),
      ...(nextOrganizer.collisions || []),
    ];
    const movieRows = matchedMedia
      .filter((item) => isRegularMovieType(item.type) && MATCHED_STATUSES.has(normalizeItemStatus(item.status)))
      .map((item) => mapOrganizerItemRow(item, t));
    const episodeRows = matchedMedia
      .filter((item) => isEpisodeMediaType(item.type) && MATCHED_STATUSES.has(normalizeItemStatus(item.status)))
      .map((item) => mapOrganizerItemRow(item, t));
    const manualMovieRows = reviewMedia
      .filter((item) => isRegularMovieType(item.type) && MANUAL_REVIEW_STATUSES.has(normalizeItemStatus(item.status)))
      .map((item) => mapOrganizerItemRow(item, t));
    const manualEpisodeRows = reviewMedia
      .filter((item) => isTvLikeMediaType(item.type) && MANUAL_REVIEW_STATUSES.has(normalizeItemStatus(item.status)))
      .map((item) => mapOrganizerItemRow(item, t));
    const sceneRows = matchedMedia
      .filter((item) => isSceneType(item.type) && MATCHED_STATUSES.has(normalizeItemStatus(item.status)))
      .map((item) => mapOrganizerItemRow(item, t));

    const manualSceneRows = reviewMedia
      .filter((item) => isSceneType(item.type) && MANUAL_REVIEW_STATUSES.has(normalizeItemStatus(item.status)))
      .map((item) => mapOrganizerItemRow(item, t));

    const extraTabPriority = ['bonus', 'subtitles', 'audio', 'images', 'metadata'];
    const firstExtraTab = extraTabPriority.find((tab) =>
      modeExtras.some((item) => item.category === EXTRA_CATEGORY_BY_TAB[tab]));
    const extraRows = firstExtraTab
      ? modeExtras
          .filter((item) => item.category === EXTRA_CATEGORY_BY_TAB[firstExtraTab])
          .map((item) => mapExtraRow(item, t))
      : [];

    const targetPriority = scanMode === 'scenes'
      ? [
          { mainTab: 'scenes', rows: sceneRows },
          { mainTab: 'manual', rows: manualSceneRows, manualTab: 'scenes' },
          { mainTab: 'extras', rows: extraRows, extrasTab: firstExtraTab },
        ]
      : isPornDbMovieMode(scanMode)
        ? [
            { mainTab: 'movies', rows: movieRows },
            { mainTab: 'manual', rows: manualMovieRows, manualTab: 'movies' },
            { mainTab: 'extras', rows: extraRows, extrasTab: firstExtraTab },
          ]
        : [
            { mainTab: 'movies', rows: movieRows },
            { mainTab: 'episodes', rows: episodeRows },
            { mainTab: 'manual', rows: manualMovieRows, manualTab: 'movies' },
            { mainTab: 'manual', rows: manualEpisodeRows, manualTab: 'episodes' },
            { mainTab: 'extras', rows: extraRows, extrasTab: firstExtraTab },
          ];
    const firstTarget = targetPriority.find((entry) => entry.rows.length > 0);

    if (!firstTarget) {
      setActiveRowId(null);
      return;
    }

    setActiveMainTab(firstTarget.mainTab);
    if (firstTarget.extrasTab) {
      setActiveExtrasTab(firstTarget.extrasTab);
    }
    if (firstTarget.manualTab) {
      setActiveManualTab(firstTarget.manualTab);
    }
    setSearchQuery('');
    setSelectedRowIds(new Set());
    setCurrentPage(1);
    setActiveRowId(firstTarget.rows[0].id);
    setIsDetailsCollapsed(false);
    try {
      localStorage.setItem('organizer_details_collapsed', JSON.stringify(false));
    } catch {
    }
    scrollOrganizerToTop();
  };

  return {
    focusFirstAvailableResult,
  };
}
