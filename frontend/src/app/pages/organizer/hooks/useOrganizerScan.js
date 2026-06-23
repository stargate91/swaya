import { useEffect, useRef, useState } from 'react';
import { selectFolder } from '../../../lib/ipc';
import { scrollOrganizerToTop } from '../organizerScroll';
import { useScanMutation, getOrganizerQueryKey } from '../../../queries';
import { isEpisodeMediaType } from '@/lib/mediaTypes';

const EMPTY_ORGANIZER = {
  manual: [],
  movies: [],
  tv: [],
  extras: [],
  collisions: [],
};

const normalizePath = (value) => String(value || '').replace(/\\/g, '/').toLowerCase();

const isPathInsideFolder = (pathValue, folderPath) => {
  const path = normalizePath(pathValue);
  const folder = normalizePath(folderPath).replace(/\/+$/, '');
  return path === folder || path.startsWith(`${folder}/`);
};

const matchesAnyDroppedPath = (value, paths) => paths.some((path) => isPathInsideFolder(value, path));

const filterOrganizerByPaths = (organizer, paths) => ({
  manual: (organizer.manual || []).filter((item) => matchesAnyDroppedPath(item.current_path || item.filename, paths)),
  movies: (organizer.movies || []).filter((item) => matchesAnyDroppedPath(item.current_path || item.filename, paths)),
  tv: (organizer.tv || []).filter((item) => matchesAnyDroppedPath(item.current_path || item.filename, paths)),
  collisions: (organizer.collisions || []).filter((item) => matchesAnyDroppedPath(item.current_path || item.filename, paths)),
  extras: (organizer.extras || []).filter((item) => matchesAnyDroppedPath(item.path || item.filename, paths)),
});

const mergeById = (currentItems = [], nextItems = []) => {
  const byId = new Map();
  currentItems.forEach((item) => byId.set(item.id, item));
  nextItems.forEach((item) => byId.set(item.id, item));
  return [...byId.values()];
};

const mergeOrganizerGroups = (currentOrganizer, nextOrganizer) => {
  const nextItemIds = new Set([
    ...(nextOrganizer.manual || []).map((i) => i.id),
    ...(nextOrganizer.movies || []).map((i) => i.id),
    ...(nextOrganizer.tv || []).map((i) => i.id),
    ...(nextOrganizer.collisions || []).map((i) => i.id),
  ]);

  const nextExtraIds = new Set([
    ...(nextOrganizer.extras || []).map((i) => i.id),
  ]);

  const cleanCurrent = {
    manual: (currentOrganizer.manual || []).filter((i) => !nextItemIds.has(i.id)),
    movies: (currentOrganizer.movies || []).filter((i) => !nextItemIds.has(i.id)),
    tv: (currentOrganizer.tv || []).filter((i) => !nextItemIds.has(i.id)),
    collisions: (currentOrganizer.collisions || []).filter((i) => !nextItemIds.has(i.id)),
    extras: (currentOrganizer.extras || []).filter((i) => !nextExtraIds.has(i.id)),
  };

  return {
    manual: mergeById(cleanCurrent.manual, nextOrganizer.manual),
    movies: mergeById(cleanCurrent.movies, nextOrganizer.movies),
    tv: mergeById(cleanCurrent.tv, nextOrganizer.tv),
    collisions: mergeById(cleanCurrent.collisions, nextOrganizer.collisions),
    extras: mergeById(cleanCurrent.extras, nextOrganizer.extras),
  };
};

export function useOrganizerScan({
  defaultScanDir,
  organizerQuery,
  isScanActive,
  onResultsReady,
  queryClient,
  t,
  toast,
  scanStatusQuery,
  renameStartedRef,
  setIsRenamePending,
  scanMode,
  sessionMode,
  includeAdult,
  provider,
}) {
  const queryKey = getOrganizerQueryKey(scanMode, sessionMode);
  const [isBrowseStarting, setIsBrowseStarting] = useState(false);
  const previousScanActiveRef = useRef(false);
  const lastScanPathsRef = useRef([]);
  const scanMutation = useScanMutation();
  const wasStopRequestedRef = useRef(false);
  const scanStatus = scanStatusQuery?.data || null;
  const lastCompletedRef = useRef(scanStatus?.last_completed || 0);

  useEffect(() => {
    if (isScanActive && scanStatus) {
      if (scanStatus.stop_requested) {
        wasStopRequestedRef.current = true;
      }
    }
  }, [isScanActive, scanStatus]);

  useEffect(() => {
    const wasActive = previousScanActiveRef.current;
    const nextLastCompleted = scanStatus?.last_completed || 0;
    const prevLastCompleted = lastCompletedRef.current;

    if (scanStatus?.last_completed) {
      lastCompletedRef.current = scanStatus.last_completed;
    }

    const isBackgroundScanCompleted = !isScanActive && prevLastCompleted !== 0 && nextLastCompleted > prevLastCompleted;

    if ((wasActive && !isScanActive) || isBackgroundScanCompleted) {
      const finalizeScan = async () => {
        const wasRename = renameStartedRef.current;
        renameStartedRef.current = false;
        setIsRenamePending(false);

        const wasAborted = wasStopRequestedRef.current;
        wasStopRequestedRef.current = false;

        const currentVisibleOrganizer = queryClient.getQueryData(queryKey) || EMPTY_ORGANIZER;

        queryClient.invalidateQueries({ queryKey: ['organizer'] });
        queryClient.invalidateQueries({ queryKey: ['organizer-count'] });
        queryClient.invalidateQueries({ queryKey: ['stats'] });
        queryClient.invalidateQueries({ queryKey: ['history'] });
        queryClient.invalidateQueries({ queryKey: ['library'] });

        try {
          const result = await organizerQuery.refetch();
          const nextOrganizer = result.data || EMPTY_ORGANIZER;

          if (wasRename) {
            queryClient.setQueryData(queryKey, nextOrganizer);
            onResultsReady?.(nextOrganizer);
            if (wasAborted) {
              toast(t('organizer.toasts.renameAborted') || 'Renaming stopped.', 'warning');
            } else {
              toast(t('organizer.toasts.renameComplete') || 'Renaming complete!', 'success');
            }
          } else {
            const scanSubset = lastScanPathsRef.current.length > 0
              ? filterOrganizerByPaths(nextOrganizer, lastScanPathsRef.current)
              : nextOrganizer;
            const mergedOrganizer = mergeOrganizerGroups(currentVisibleOrganizer, scanSubset);
            queryClient.setQueryData(queryKey, mergedOrganizer);
            onResultsReady?.(mergedOrganizer);
            const matchedMovies = (nextOrganizer.movies || []).length;
            const matchedEpisodes = (nextOrganizer.tv || []).filter((item) => isEpisodeMediaType(item.type)).length;
            const matchedReady = matchedMovies + matchedEpisodes;
            toast(t('organizer.toasts.scanComplete').replace('{count}', matchedReady), 'success');
          }
        } catch {
          toast(wasRename ? (t('organizer.toasts.renameComplete') || 'Renaming complete!') : t('organizer.toasts.scanCompleteFallback'), 'success');
        }
        lastScanPathsRef.current = [];
      };

      finalizeScan();
      scrollOrganizerToTop();
    }
    previousScanActiveRef.current = isScanActive;
  }, [isScanActive, onResultsReady, queryClient, queryKey, setIsRenamePending, t, toast, organizerQuery, renameStartedRef, scanStatus]);

  const handleScanPaths = async (paths) => {
    if (isScanActive || isBrowseStarting) {
      return;
    }

    const uniquePaths = [...new Set((paths || []).filter(Boolean))];
    if (uniquePaths.length === 0) {
      return;
    }

    setIsBrowseStarting(true);
    try {
      lastScanPathsRef.current = uniquePaths;

      const response = await scanMutation.mutateAsync({
        paths: uniquePaths,
        mode: scanMode,
        include_adult: includeAdult,
        provider: provider,
      });

      if (response?.status === 'error') {
        throw new Error(response.message);
      }

      queryClient.invalidateQueries({ queryKey: ['scan-status'] });
      queryClient.invalidateQueries({ queryKey: ['organizer'] });
      queryClient.invalidateQueries({ queryKey: ['organizer-count'] });
    } catch (error) {
      toast(error.message || t('organizer.toasts.scanStartFailed'), 'danger');
    } finally {
      setIsBrowseStarting(false);
    }
  };

  const handleBrowseAndScan = async () => {
    const folder = await selectFolder(defaultScanDir);
    if (!folder) {
      return;
    }

    await handleScanPaths([folder]);
  };

  return {
    handleScanPaths,
    handleBrowseAndScan,
    isBrowseStarting,
  };
}
