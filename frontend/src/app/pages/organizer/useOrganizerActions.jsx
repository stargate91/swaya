import { useRef, useState } from 'react';
import { useRenameMutation, getOrganizerQueryKey } from '../../queries';
import { useOrganizerRename } from './hooks/useOrganizerRename';
import { useOrganizerScan } from './hooks/useOrganizerScan';

export function useOrganizerActions({
  defaultScanDir,
  organizerCountQuery,
  organizerQuery,
  isScanActive,
  onResultsReady,
  queryClient,
  t,
  toast,
  openModal,
  closeModal,
  sortedRows,
  scanStatusQuery,
  scanMode,
  sessionMode,
  includeAdult,
  provider,
}) {
  const [isLoadingAll, setIsLoadingAll] = useState(false);
  const renameStartedRef = useRef(false);
  const renameMutation = useRenameMutation();

  const {
    handleScanPaths,
    handleBrowseAndScan,
    isBrowseStarting,
  } = useOrganizerScan({
    defaultScanDir,
    organizerQuery,
    isScanActive,
    onResultsReady,
    queryClient,
    t,
    toast,
    scanStatusQuery,
    renameStartedRef,
    scanMode,
    sessionMode,
    includeAdult,
    provider,
  });

  const { handleRename, isRenameStarting } = useOrganizerRename({
    organizerQuery,
    sortedRows,
    isScanActive,
    renameMutation,
    queryClient,
    renameStartedRef,
    t,
    toast,
    openModal,
    closeModal,
  });

  const handleLoadAll = async () => {
    if (isLoadingAll) {
      return;
    }

    setIsLoadingAll(true);
    try {
      const result = await organizerQuery.refetch();
      if (result.data) {
        queryClient.setQueryData(getOrganizerQueryKey(scanMode, sessionMode), result.data);
        onResultsReady?.(result.data);
      }
      await organizerCountQuery.refetch();
      toast(t('organizer.toasts.loadAllSuccess'), 'success');
    } finally {
      setIsLoadingAll(false);
    }
  };

  return {
    handleBrowseAndScan,
    handleLoadAll,
    handleRename,
    handleScanPaths,
    isBrowseStarting,
    isLoadingAll,
    isRenameStarting,
  };
}
