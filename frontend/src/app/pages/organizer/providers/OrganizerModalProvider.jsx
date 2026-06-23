import { useOrganizerModalActions } from '../useOrganizerModalActions';
import { OrganizerModalContext } from './OrganizerModalContext';

export function OrganizerModalProvider({
  children,
  focusFirstAvailableResult,
  clearSelectedRows,
  dismissRows,
  selectedRows,
  scanMode,
  sessionMode,
}) {
  const {
    openDeleteModal,
    openBulkDeleteModal,
    openMatchModal,
    openOverrideModal,
    openBulkOverrideModal,
    rowActions,
    bulkActionBar,
    refreshOrganizer,
  } = useOrganizerModalActions({
    focusFirstAvailableResult,
    clearSelectedRows,
    dismissRows,
    selectedRows,
    scanMode,
    sessionMode,
  });

  const contextValue = {
    openDeleteModal,
    openBulkDeleteModal,
    openMatchModal,
    openOverrideModal,
    openBulkOverrideModal,
    rowActions,
    bulkActionBar,
    refreshOrganizer,
    selectedRows,
    dismissRows,
    clearSelectedRows,
  };

  return (
    <OrganizerModalContext.Provider value={contextValue}>
      {children}
    </OrganizerModalContext.Provider>
  );
}
