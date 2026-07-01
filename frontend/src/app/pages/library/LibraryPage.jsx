import Page from '@/ui/Page';
import LibraryPagination from './components/LibraryPagination';
import { useLibraryState } from './hooks/useLibraryState';
import { useLibraryModals } from './hooks/useLibraryModals';
import LibraryHeader from './components/LibraryHeader';
import LibraryFilters from './components/LibraryFilters';
import LibraryGrid from './components/LibraryGrid';
import { useDeleteTagMutation } from '@/queries';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { isLibraryTagsTab } from '@/lib/libraryTabs';
import { useUi } from '@/providers/UiProvider';
import UniversalImagePickerModal from './modals/UniversalImagePickerModal';
import './LibraryPage.css';

export default function LibraryPage({ initialTab = 'movies', lockTab = false, showTabs = true, pageTitle = null }) {
  const state = useLibraryState({ initialTab, lockTab, includeTagsTab: true });
  const [focusedTagName, setFocusedTagName] = useState(null);
  const [imagePickerData, setImagePickerData] = useState(null);
  const { toast } = useUi();
  const deleteTagMutation = useDeleteTagMutation();
  const modals = useLibraryModals({
    state,
    focusedTagName,
    setFocusedTagName,
    deleteTagMutation,
  });

  const isAdultMode = state.activeSessionMode === 'nsfw';

  useEffect(() => {
    if (imagePickerData) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [imagePickerData]);

  useEffect(() => {
    if (!state.isTags && focusedTagName !== null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setFocusedTagName(null);
    }
  }, [state.isTags, focusedTagName]);



  const focusedTag = useMemo(() => {
    if (!state.isTags || !focusedTagName) return null;
    return state.sortedItems.find((item) => item.name === focusedTagName) || null;
  }, [focusedTagName, state.isTags, state.sortedItems]);

  const isTagFocusMode = state.isTags && !!focusedTag;



  if (state.isLoading) {
    return (
      <Page className="library-page">
        <div className="library-loading">
          <div className="library-spinner" />
        </div>
      </Page>
    );
  }

  return (
    <Page className={`library-page ${isAdultMode ? 'library-page--nsfw' : ''}`}>
      <div className="library-main">
        <div className={`organizer-panel ${isAdultMode ? 'organizer-panel--nsfw' : ''}`}>
          <LibraryHeader
            t={state.t}
            pageTitle={pageTitle}
            tabs={state.tabs}
            resolvedTab={state.resolvedTab}
            setActiveTab={state.setActiveTab}
            searchPlaceholder={state.searchPlaceholder}
            setSearchQuery={state.setSearchQuery}
            onAddPeople={modals.openAddPeopleModal}
            onCreateTag={modals.openCreateTagModal}
            showTabs={showTabs}
            sortKey={state.sortKey}
            setSortKey={state.setSortKey}
            sortDirection={state.sortDirection}
            setSortDirection={state.setSortDirection}
            setCurrentPage={state.setCurrentPage}
            activeSessionMode={state.activeSessionMode}
          />

          {!(isLibraryTagsTab(state.resolvedTab) && !showTabs) ? (
            <LibraryFilters
              t={state.t}
              settings={state.settings}
              resolvedTab={state.resolvedTab}
              isCollections={state.isCollections}
              isPeople={state.isPeople}
              activeSessionMode={state.activeSessionMode}
              sortKey={state.sortKey}
              setSortKey={state.setSortKey}
              sortDirection={state.sortDirection}
              setSortDirection={state.setSortDirection}
              setCurrentPage={state.setCurrentPage}
              collectionStatusFilter={state.collectionStatusFilter}
              setCollectionStatusFilter={state.setCollectionStatusFilter}
              peopleRoleFilter={state.peopleRoleFilter}
              setPeopleRoleFilter={state.setPeopleRoleFilter}
              genderFilter={state.genderFilter}
              setGenderFilter={state.setGenderFilter}
              ownershipFilter={state.ownershipFilter}
              setOwnershipFilter={state.setOwnershipFilter}
              watchedFilter={state.watchedFilter}
              setWatchedFilter={state.setWatchedFilter}
              genreFilter={state.genreFilter}
              setGenreFilter={state.setGenreFilter}
              decadeFilter={state.decadeFilter}
              setDecadeFilter={state.setDecadeFilter}
              yearFilter={state.yearFilter}
              setYearFilter={state.setYearFilter}
              timeFilterMode={state.timeFilterMode}
              setTimeFilterMode={state.setTimeFilterMode}
              favoriteFilter={state.favoriteFilter}
              setFavoriteFilter={state.setFavoriteFilter}
              selectedTags={state.selectedTags}
              setSelectedTags={state.setSelectedTags}
              performerFilter={state.performerFilter}
              setPerformerFilter={state.setPerformerFilter}
              studioFilter={state.studioFilter}
              setStudioFilter={state.setStudioFilter}
              hairColorFilter={state.hairColorFilter}
              setHairColorFilter={state.setHairColorFilter}
              ethnicityFilter={state.ethnicityFilter}
              setEthnicityFilter={state.setEthnicityFilter}
              eyeColorFilter={state.eyeColorFilter}
              setEyeColorFilter={state.setEyeColorFilter}
              tattoosFilter={state.tattoosFilter}
              setTattoosFilter={state.setTattoosFilter}
              piercingsFilter={state.piercingsFilter}
              setPiercingsFilter={state.setPiercingsFilter}
              breastTypeFilter={state.breastTypeFilter}
              setBreastTypeFilter={state.setBreastTypeFilter}
              filterData={state.filterData}
            />
          ) : null}
        </div>

        <LibraryPagination
          state={state}
          isTagFocusMode={isTagFocusMode}
          showPageSizes
        />

        <LibraryGrid
          key={state.resolvedTab}
          t={state.t}
          isDataLoading={state.isDataLoading}
          paginatedItems={state.paginatedItems}
          isTags={state.isTags}
          isCollections={state.isCollections}
          resolvedTab={state.resolvedTab}
          emptyTitle={state.emptyTitle}
          emptyDescription={state.emptyDescription}
          emptyStateVariant={state.emptyStateVariant}
          emptyIcon={state.emptyIcon}
          hasActiveFilters={state.hasActiveFilters}
          onAddPeople={modals.openAddPeopleModal}
          onCreateTag={modals.openCreateTagModal}
          onEditTag={modals.openEditTagModal}
          onDeleteTag={modals.openDeleteTagModal}
          focusedTag={focusedTag}
          onFocusTag={setFocusedTagName}
          onExitTagFocus={() => setFocusedTagName(null)}
          activeSessionMode={state.activeSessionMode}
          onEditImage={setImagePickerData}
        />

        <LibraryPagination
          state={state}
          isTagFocusMode={isTagFocusMode}
          showSpacer
        />
      </div>

      {/* Image Picker Drawer */}
      {imagePickerData && typeof document !== 'undefined' && createPortal(
        <>
          <div
            className="entity-detail-page__drawer-backdrop ui-drawer-backdrop entity-detail-page__drawer-backdrop--transparent"
            role="button"
            tabIndex={-1}
            onClick={() => setImagePickerData(null)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                setImagePickerData(null);
              }
            }}
          />
          <div className="entity-detail-page__drawer ui-drawer ui-drawer--md entity-detail-page__drawer--poster">
            <div className="entity-detail-page__drawer-header">
              <h3 className="entity-detail-page__drawer-title">
                {imagePickerData.title}
              </h3>
              <button
                type="button"
                className="entity-detail-page__drawer-close"
                onClick={() => setImagePickerData(null)}
              >
                &times;
              </button>
            </div>
            <div className="entity-detail-page__drawer-content" style={{ padding: '24px' }}>
              <UniversalImagePickerModal
                entityId={imagePickerData.entityId}
                tmdbId={imagePickerData.tmdbId}
                imageType={imagePickerData.imageType}
                entityType={imagePickerData.entityType}
                currentPath={imagePickerData.currentPath}
                t={state.t}
                toast={toast}
                externalIds={imagePickerData.externalIds}
                item={imagePickerData.item}
                onImageSelected={() => {
                  toast.success(state.t('library.details.imageUpdatedSuccessfully') || 'Image updated successfully');
                }}
              />
            </div>
          </div>
        </>,
        document.body
      )}
    </Page>
  );
}
