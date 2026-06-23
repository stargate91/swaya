import { useMemo } from 'react';
import { Database, Inbox } from 'lucide-react';

export function useOrganizerViewModel({
  organizerItemCount,
  isBrowseStarting,
  isOrganizerCountReady,
  isLoadingAll,
  isRenamePending,
  isRenameStarting,
  isScanActive,
  pageEnd,
  pageStart,
  scanPhase,
  sortedRows,
  t,
  visibleExtraCount,
  visibleMediaCount,
}) {
  return useMemo(() => {
    const loadedMediaCount = visibleMediaCount || 0;
    const hasVisibleItems = loadedMediaCount > 0 || (visibleExtraCount || 0) > 0;
    const hasDatabaseItems = isOrganizerCountReady && organizerItemCount > 0;
    const remainingOrganizerCount = isOrganizerCountReady
      ? Math.max(0, organizerItemCount - loadedMediaCount)
      : null;
    const shouldShowLoadRest = hasVisibleItems && isOrganizerCountReady && remainingOrganizerCount > 0;
    const summaryText = `${pageStart}-${pageEnd} / ${sortedRows.length}`;
    const isRenameActive = isRenamePending || (isScanActive && scanPhase === 'organizing');

    const loadingState = isLoadingAll
      ? {
        label: t('organizer.loadingStates.loadAll.label'),
        description: t('organizer.loadingStates.loadAll.description'),
      }
      : isRenameActive
        ? {
          label: t('organizer.loadingStates.rename.label'),
          description: t('organizer.loadingStates.rename.description'),
        }
        : isScanActive
          ? {
            label: t('organizer.loadingStates.scan.label'),
            description: t('organizer.loadingStates.scan.description'),
          }
          : null;

    const emptyState = !hasVisibleItems && !loadingState
      ? hasDatabaseItems
        ? {
          icon: Inbox,
          title: t('organizer.emptyStates.notLoaded.title'),
          description: t('organizer.emptyStates.notLoaded.description'),
        }
        : {
          icon: Database,
          title: t('organizer.emptyStates.emptyDatabase.title'),
          description: t('organizer.emptyStates.emptyDatabase.description'),
        }
      : null;

    return {
      browseButtonLabel: isBrowseStarting ? t('organizer.buttons.opening') : isScanActive ? t('organizer.buttons.scanning') : t('organizer.buttons.browseAndScan'),
      emptyState,
      hasDatabaseItems,
      hasVisibleItems,
      loadAllButtonLabel: isLoadingAll
        ? t('organizer.buttons.loadingAll')
        : isOrganizerCountReady
          ? `${t('organizer.buttons.loadAll')} (${organizerItemCount})`
          : t('organizer.buttons.loadAll'),
      loadRestButtonLabel: isLoadingAll
        ? t('organizer.buttons.loadingAll')
        : isOrganizerCountReady
          ? `${t('organizer.buttons.loadTheRest')} (${remainingOrganizerCount})`
          : t('organizer.buttons.loadTheRest'),
      loadingState,
      renameButtonLabel: isRenameStarting || isRenameActive
        ? t('organizer.buttons.organizing')
        : t('organizer.buttons.rename'),
      shouldShowDetailsPanel: !emptyState && !loadingState,
      shouldShowLoadRest,
      summaryText,
    };
  }, [
    organizerItemCount,
    isBrowseStarting,
    isOrganizerCountReady,
    isLoadingAll,
    isRenamePending,
    isRenameStarting,
    isScanActive,
    pageEnd,
    pageStart,
    scanPhase,
    sortedRows.length,
    t,
    visibleExtraCount,
    visibleMediaCount,
  ]);
}
