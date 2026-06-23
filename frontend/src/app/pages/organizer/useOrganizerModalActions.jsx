import { useMemo } from 'react';
import { FolderOpen, Play, Search, Sliders, Trash2, X, EyeOff } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import Button from '../../ui/Button';
import FloatingActionBar from '../../ui/FloatingActionBar';
import OrganizerMatchModalContent from './OrganizerMatchModalContent';
import OrganizerOverrideModalContent from './components/OrganizerOverrideModalContent';
import OrganizerBulkOverrideModalContent from './components/OrganizerBulkOverrideModalContent';
import api from '../../lib/api';
import { showItemInFolder } from '../../lib/ipc';
import { useUi } from '../../providers/UiProvider';
import { useTranslation } from '../../providers/LanguageContext';
import { useOrganizerDeleteActions } from './useOrganizerDeleteActions';
import { useSettingsQuery } from '../../queries';
import { mapOrganizerTypeLabel } from './organizerMappers';

export function useOrganizerModalActions({
  focusFirstAvailableResult,
  clearSelectedRows,
  dismissRows,
  selectedRows,
  scanMode,
  sessionMode,
  provider,
}) {
  const { t } = useTranslation();
  const { closeModal, openModal, toast } = useUi();
  const queryClient = useQueryClient();
  const settingsQuery = useSettingsQuery();
  const settings = settingsQuery.data;

  const {
    refreshOrganizer,
    handleResolveOrganizerRows,
    handleDeleteOrganizerRow,
    handleDeleteOrganizerRows,
  } = useOrganizerDeleteActions({
    t,
    closeModal,
    toast,
    queryClient,
    focusFirstAvailableResult,
    clearSelectedRows,
    scanMode,
    sessionMode,
  });

  const isPlayableOrganizerRow = (row) => {
    if (!row?.sourcePath) {
      return false;
    }
    if (row.rawType === 'extra') {
      return String(row.rawPayload?.category || '').toLowerCase() === 'video';
    }
    return true;
  };

  const handlePreviewRow = async (row) => {
    if (!settings?.vlc_path && !settings?.mpc_path) {
      throw new Error(t('organizer.toasts.noMediaPlayerConfigured'));
    }
    await api.media.preview(row.sourcePath);
  };

  const openDeleteModal = (row) => {
    const isExtra = row.rawType === 'extra';
    const actionCards = [
      !isExtra ? {
        key: 'ignore',
        label: t('organizer.details.delete.ignore.label'),
        description: t('organizer.details.delete.ignore.description'),
      } : null,
      {
        key: 'db_only',
        label: t('organizer.details.delete.dbOnly.label'),
        description: t(isExtra ? 'organizer.details.delete.dbOnly.descriptionExtra' : 'organizer.details.delete.dbOnly.descriptionMedia'),
      },
      {
        key: 'trash',
        label: t('organizer.details.delete.trash.label'),
        description: t(isExtra ? 'organizer.details.delete.trash.descriptionExtra' : 'organizer.details.delete.trash.descriptionMedia'),
        className: 'ui-modal__action-card--danger',
      },
    ].filter(Boolean);

    openModal({
      title: t('organizer.details.delete.title'),
      description: t(isExtra ? 'organizer.details.delete.descriptionExtra' : 'organizer.details.delete.descriptionMedia'),
      icon: Trash2,
      variant: 'danger',
      content: (
        <div className="ui-modal__actions-list">
          {actionCards.map((action) => (
            <button
              key={action.key}
              type="button"
              className={`ui-modal__action-card ${action.className || ''}`.trim()}
              onClick={() => {
                handleDeleteOrganizerRow(row, action.key).catch((error) => {
                  toast(error.message || t('organizer.toasts.deleteActionFailed'), 'danger');
                });
              }}
            >
              <div className="ui-modal__action-copy">
                <strong className="ui-modal__action-title">{action.label}</strong>
                <span className="ui-modal__action-description">{action.description}</span>
              </div>
            </button>
          ))}
        </div>
      ),
      footer: (
        <Button variant="secondary-neutral" onClick={closeModal}>
          {t('organizer.details.delete.cancel')}
        </Button>
      ),
    });
  };

  const openBulkDeleteModal = (rows) => {
    const hasExtras = rows.some((row) => row.rawType === 'extra');
    const hasMedia = rows.some((row) => row.rawType !== 'extra');
    const actionCards = [
      hasMedia ? {
        key: 'ignore',
        label: t('organizer.details.delete.ignore.label'),
        description: t('organizer.details.delete.ignore.description'),
      } : null,
      {
        key: 'db_only',
        label: t('organizer.details.delete.dbOnly.label'),
        description: hasMedia && hasExtras
          ? t('organizer.details.bulkDelete.dbOnly.descriptionMixed')
          : hasExtras
            ? t('organizer.details.bulkDelete.dbOnly.descriptionExtra')
            : t('organizer.details.bulkDelete.dbOnly.descriptionMedia'),
      },
      {
        key: 'trash',
        label: t('organizer.details.delete.trash.label'),
        description: hasMedia && hasExtras
          ? t('organizer.details.bulkDelete.trash.descriptionMixed')
          : hasExtras
            ? t('organizer.details.bulkDelete.trash.descriptionExtra')
            : t('organizer.details.bulkDelete.trash.descriptionMedia'),
        className: 'ui-modal__action-card--danger',
      },
    ].filter(Boolean);

    openModal({
      title: t('organizer.details.bulkDelete.title'),
      description: t('organizer.details.bulkDelete.description').replace('{count}', String(rows.length)),
      icon: Trash2,
      variant: 'danger',
      content: (
        <div className="ui-modal__actions-list">
          {actionCards.map((action) => (
            <button
              key={action.key}
              type="button"
              className={`ui-modal__action-card ${action.className || ''}`.trim()}
              onClick={() => {
                handleDeleteOrganizerRows(rows, action.key).catch((error) => {
                  toast(error.message || t('organizer.toasts.deleteActionFailed'), 'danger');
                });
              }}
            >
              <div className="ui-modal__action-copy">
                <strong className="ui-modal__action-title">{action.label}</strong>
                <span className="ui-modal__action-description">{action.description}</span>
              </div>
            </button>
          ))}
        </div>
      ),
      footer: (
        <Button variant="secondary-neutral" onClick={closeModal}>
          {t('organizer.details.delete.cancel')}
        </Button>
      ),
    });
  };

  const openMatchModal = (row, rows = null) => {
    const targetRows = rows || [row];
    const isBulk = targetRows.length > 1;
    openModal({
      title: isBulk
        ? t('organizer.details.matchModal.titleBulk') || 'Match Selected Items'
        : t('organizer.details.matchModal.title'),
      description: isBulk
        ? t('organizer.details.matchModal.descriptionBulk') || 'Search and apply a match for the selected items.'
        : t('organizer.details.matchModal.description'),
      className: 'ui-modal--wide',
      icon: Search,
      content: (
        <OrganizerMatchModalContent
          row={row}
          rows={targetRows}
          t={t}
          toast={toast}
          scanMode={scanMode}
          onResolved={(performMutationFn) => {
            handleResolveOrganizerRows(targetRows, performMutationFn);
          }}
        />
      ),
      footer: (
        <Button variant="secondary-neutral" onClick={closeModal}>
          {t('organizer.details.delete.cancel')}
        </Button>
      ),
    });
  };

  const openOverrideModal = (row) => {
    openModal({
      title: t('organizer.overrideModal.title').replace('{type}', mapOrganizerTypeLabel(row.rawType, t) || ''),
      description: t('organizer.overrideModal.description'),
      icon: Sliders,
      content: (
        <OrganizerOverrideModalContent
          row={row}
          onClose={closeModal}
          toast={toast}
          api={api}
          scanMode={scanMode}
          sessionMode={sessionMode}
        />
      ),
      footer: (
        <>
          <Button variant="secondary-neutral" type="button" onClick={closeModal}>
            {t('organizer.details.delete.cancel')}
          </Button>
          <Button variant="primary" type="submit" form="organizer-override-form">
            {t('organizer.overrideModal.apply')}
          </Button>
        </>
      ),
    });
  };

  const openBulkOverrideModal = (rows) => {
    const type = rows[0]?.rawType || '';
    openModal({
      title: (t('organizer.overrideModal.titleBulk') || 'Bulk Override {type}s').replace('{type}', mapOrganizerTypeLabel(type, t)),
      description: t('organizer.overrideModal.descriptionBulk') || 'Apply settings or numberings to all selected items.',
      icon: Sliders,
      className: 'ui-modal--bulk-override',
      content: (
        <OrganizerBulkOverrideModalContent
          rows={rows}
          onClose={closeModal}
          toast={toast}
          scanMode={scanMode}
          sessionMode={sessionMode}
        />
      ),
      footer: (
        <>
          <Button variant="secondary-neutral" type="button" onClick={closeModal}>
            {t('organizer.details.delete.cancel')}
          </Button>
          <Button variant="primary" type="submit" form="organizer-bulk-override-form">
            {t('organizer.overrideModal.applyBulk')}
          </Button>
        </>
      ),
    });
  };

  const rowActions = useMemo(() => [
    {
      key: 'match',
      label: t('organizer.actions.match'),
      icon: Search,
      isVisible: (row) => row.rawType !== 'extra',
      onClick: (row) => openMatchModal(row),
    },
    {
      key: 'override',
      label: t('organizer.actions.override'),
      icon: Sliders,
      onClick: (row) => openOverrideModal(row),
    },
    {
      key: 'preview',
      label: t('organizer.actions.preview'),
      icon: Play,
      isVisible: isPlayableOrganizerRow,
      onClick: async (row) => {
        try {
          await handlePreviewRow(row);
        } catch (error) {
          toast(error.message || t('organizer.toasts.previewFailed'), 'danger');
        }
      },
    },
    {
      key: 'show-in-folder',
      label: t('organizer.actions.showInFolder'),
      icon: FolderOpen,
      onClick: async (row) => {
        const result = await showItemInFolder(row.sourcePath);
        if (!result?.success) {
          toast(result?.error || t('organizer.toasts.showInFolderFailed'), 'danger');
        }
      },
    },
    {
      key: 'dismiss',
      label: t('organizer.actions.dismiss'),
      icon: EyeOff,
      isVisible: (row) => row.rawType !== 'extra',
      onClick: (row) => dismissRows([row.id]),
    },
    {
      key: 'delete',
      label: t('organizer.details.delete.title'),
      tooltip: t('organizer.actions.delete'),
      icon: Trash2,
      className: 'is-danger',
      onClick: (row) => openDeleteModal(row),
    },
  ], [
    t,
    dismissRows,
    scanMode,
    openMatchModal,
    openOverrideModal,
    openDeleteModal,
    isPlayableOrganizerRow,
    handlePreviewRow,
    toast,
  ]);

  const bulkActionBar = (
    <FloatingActionBar
      visible={selectedRows.length > 0}
      title={t('organizer.bulkBar.title').replace('{count}', String(selectedRows.length))}
      actions={[
        !selectedRows.some((row) => row.rawType === 'extra') ? {
          key: 'dismiss',
          label: t('organizer.actions.dismissBulk'),
          icon: EyeOff,
          onClick: () => {
            dismissRows(selectedRows.map((r) => r.id));
            clearSelectedRows();
          },
          disabled: selectedRows.length === 0,
        } : null,
        {
          key: 'delete',
          label: t('organizer.actions.delete'),
          icon: Trash2,
          variant: 'danger',
          onClick: () => openBulkDeleteModal(selectedRows),
          disabled: selectedRows.length === 0,
        },
        (!selectedRows.some((row) => row.rawType === 'extra') && scanMode !== 'scenes' && provider !== 'porndb') ? {
          key: 'match',
          label: t('organizer.actions.match') || 'Match',
          icon: Search,
          onClick: () => openMatchModal(null, selectedRows),
          disabled: selectedRows.length === 0,
        } : null,
        selectedRows.length > 0 && selectedRows.every((r) => r.rawType === selectedRows[0].rawType) ? {
          key: 'override',
          label: t('organizer.actions.override') || 'Override',
          icon: Sliders,
          onClick: () => openBulkOverrideModal(selectedRows),
        } : null,
        {
          key: 'clear',
          label: t('organizer.bulkBar.clear'),
          icon: X,
          onClick: clearSelectedRows,
          disabled: selectedRows.length === 0,
        },
      ].filter(Boolean)}
    />
  );

  return {
    openDeleteModal,
    openBulkDeleteModal,
    openMatchModal,
    openOverrideModal,
    openBulkOverrideModal,
    rowActions,
    bulkActionBar,
    refreshOrganizer,
  };
}

