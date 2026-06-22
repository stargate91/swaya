import { useMemo } from 'react';
import { EXTRA_CATEGORY_BY_TAB } from './organizerMappers';
import { EXTRAS_TABS, MAIN_TABS, MANUAL_TABS } from './organizerConstants';

const isPornDbMovieMode = (scanMode) => scanMode === 'porndb_movie';

const getMainTabsForMode = (scanMode) => {
  if (scanMode === 'scenes') return ['manual', 'scenes', 'extras'];
  if (isPornDbMovieMode(scanMode)) return ['manual', 'movies', 'extras'];
  return ['manual', 'movies', 'episodes', 'extras'];
};

const isExtraForMode = (item, scanMode) => {
  const parentType = String(item.parent_type || '').toLowerCase();
  if (scanMode === 'scenes') return parentType === 'scene';
  if (isPornDbMovieMode(scanMode)) return parentType === 'movie';
  return parentType !== 'scene';
};

const getManualTabsForMode = (scanMode) => {
  if (scanMode === 'scenes') return ['scenes'];
  if (isPornDbMovieMode(scanMode)) return ['movies'];
  return ['movies', 'episodes'];
};

export function useOrganizerTabs({ organizerExtras, t, tabCounts, dismissedRowIds, scanMode }) {
  const computedMainTabs = useMemo(() => {
    const allowedTabs = new Set(getMainTabsForMode(scanMode));
    return MAIN_TABS.filter((tab) => allowedTabs.has(tab.value)).map((tab) => ({
      ...tab,
      label: t(tab.labelKey),
      count: tab.value === 'manual'
        ? tabCounts.manualCount
        : tab.value === 'movies'
          ? tabCounts.moviesCount
          : tab.value === 'episodes'
            ? tabCounts.episodesCount
            : tab.value === 'scenes'
              ? tabCounts.scenesCount
              : tabCounts.extrasCount,
    }));
  }, [t, tabCounts, scanMode]);

  const computedManualTabs = useMemo(() => {
    const allowedTabs = new Set(getManualTabsForMode(scanMode));
    return MANUAL_TABS.filter((tab) => allowedTabs.has(tab.value)).map((tab) => ({
      ...tab,
      label: t(tab.labelKey),
      count: tab.value === 'movies'
        ? tabCounts.manualMoviesCount
        : tab.value === 'episodes'
          ? tabCounts.manualEpisodesCount
          : tabCounts.manualScenesCount,
    }));
  }, [t, tabCounts, scanMode]);

  const computedExtrasTabs = useMemo(() => EXTRAS_TABS
    .map((tab) => ({
      ...tab,
      label: t(tab.labelKey),
      count: (organizerExtras || []).filter((item) => {
        if (!isExtraForMode(item, scanMode) || item.category !== EXTRA_CATEGORY_BY_TAB[tab.value]) {
          return false;
        }
        if (dismissedRowIds) {
          const id = `extra-${item.id}`;
          const parentId = `item-${item.parent_id || item.parent_item_id}`;
          if (dismissedRowIds.has(id) || dismissedRowIds.has(parentId)) {
            return false;
          }
        }
        return true;
      }).length,
    })), [organizerExtras, t, dismissedRowIds, scanMode]);

  return {
    computedExtrasTabs,
    computedManualTabs,
    computedMainTabs,
  };
}
