import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import Button from '../../../ui/Button';
import OrganizerRenameModalContent from '../OrganizerRenameModalContent.jsx';
import { mapOrganizerItemRow, mapExtraRow } from '../organizerMappers';

export function useOrganizerRename({
  modeVisibleMatchedItems,
  modeVisibleExtrasForRename,
  isScanActive,
  renameMutation,
  queryClient,
  renameStartedRef,
  setIsRenamePending,
  t,
  toast,
  openModal,
  closeModal,
}) {
  const [isRenameStarting, setIsRenameStarting] = useState(false);

  const handleRename = async () => {
    if (isRenameStarting || isScanActive) {
      return;
    }

    const matchedItems = modeVisibleMatchedItems || [];
    const matchedExtras = modeVisibleExtrasForRename || [];

    if (matchedItems.length === 0) {
      toast(t('organizer.toasts.noMatchedItems'), 'danger');
      return;
    }

    const mappedItems = [
      ...matchedItems.map((item) => mapOrganizerItemRow(item, t)),
      ...matchedExtras.map((extra) => mapExtraRow(extra, t)),
    ];

    const executeRename = async (organizeInPlaceVal) => {
      closeModal();
      setIsRenameStarting(true);
      const previousScanStatus = queryClient.getQueryData(['scan-status']);
      try {
        const ids = matchedItems.map((item) => item.id);
        if (renameStartedRef) {
          renameStartedRef.current = true;
        }
        setIsRenamePending(true);
        queryClient.setQueryData(['scan-status'], (current) => ({
          ...(current || {}),
          active: true,
          phase: 'organizing',
          current: 0,
          total: ids.length,
          start_time: Math.floor(Date.now() / 1000),
          can_stop: true,
          stop_requested: false,
          current_file_progress: 0,
        }));
        const response = await renameMutation.mutateAsync({
          item_ids: ids,
          organize_in_place: organizeInPlaceVal
        });
        if (response?.status === 'error') {
          throw new Error(response.message);
        }
        queryClient.invalidateQueries({ queryKey: ['history'] });
        queryClient.invalidateQueries({ queryKey: ['library'] });
      } catch (error) {
        queryClient.setQueryData(['scan-status'], previousScanStatus || null);
        if (renameStartedRef) {
          renameStartedRef.current = false;
        }
        setIsRenamePending(false);
        toast(error.message || t('organizer.toasts.renameStartFailed'), 'danger');
      } finally {
        setIsRenameStarting(false);
      }
    };

    const showModal = (organizeInPlaceVal) => {
      openModal({
        title: t('organizer.renameModal.title') || 'Confirm Rename',
        description: t('organizer.renameModal.description') || 'Review the files that will be renamed.',
        icon: Sparkles,
        className: 'ui-modal--extra-wide',
        content: (
          <OrganizerRenameModalContent
            items={mappedItems}
            t={t}
            organizeInPlace={organizeInPlaceVal}
            setOrganizeInPlace={showModal}
          />
        ),
        footer: (
          <>
            <Button variant="secondary-neutral" onClick={closeModal}>
              {t('organizer.details.delete.cancel') || 'Cancel'}
            </Button>
            <Button variant="primary" onClick={() => executeRename(organizeInPlaceVal)}>
              {organizeInPlaceVal
                ? (t('organizer.renameModal.organizeInPlace') || 'Organize in Place')
                : (t('organizer.actions.rename') || 'Rename')}
            </Button>
          </>
        ),
      });
    };

    showModal(false);
  };

  return {
    handleRename,
    isRenameStarting,
  };
}
