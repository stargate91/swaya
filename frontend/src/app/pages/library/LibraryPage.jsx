import Page from '@/ui/Page';
import LibraryPagination from './components/LibraryPagination';
import NavButton from '@/ui/NavButton';
import { useLibraryState } from './hooks/useLibraryState';
import { useLibraryModals } from './hooks/useLibraryModals';
import LibraryHeader from './components/LibraryHeader';
import LibraryFilters from './components/LibraryFilters';
import LibraryBulkImportBanner from './components/LibraryBulkImportBanner';
import { useLibraryBulkImport } from './hooks/useLibraryBulkImport';
import LibraryGrid from './components/LibraryGrid';
import UtilityBarPortal from '../../../components/UtilityBarPortal';
import { useDeleteTagMutation } from '@/queries';
import { useUi } from '@/providers/UiProvider';
import { useEffect, useMemo, useState } from 'react';
import { isLibraryPeopleTab, isLibraryTagsTab } from '@/lib/libraryTabs';
import './LibraryPage.css';

export default function LibraryPage({ initialTab = 'movies', lockTab = false, showTabs = true, pageTitle = null }) {
  const state = useLibraryState({ initialTab, lockTab, includeTagsTab: true });
  const { openModal, closeModal } = useUi();
  const [focusedTagName, setFocusedTagName] = useState(null);
  const deleteTagMutation = useDeleteTagMutation();
  const modals = useLibraryModals({
    state,
    focusedTagName,
    setFocusedTagName,
    deleteTagMutation,
  });

  const isAdultMode = state.activeSessionMode === 'nsfw';
  const isPeopleTab = isLibraryPeopleTab(state.resolvedTab);

  const bulkImport = useLibraryBulkImport({ isAdultMode, isPeopleTab });

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
              filterData={state.filterData}
            />
          ) : null}
        </div>

        <LibraryBulkImportBanner
          t={state.t}
          resolvedTab={state.resolvedTab}
          isAdultMode={isAdultMode}
          openBulkImportResolveModal={modals.openBulkImportResolveModal}
          openModal={openModal}
          closeModal={closeModal}
          showBulkImportBanner={bulkImport.showBulkImportBanner}
          dismissBulkImportBanner={bulkImport.dismissBulkImportBanner}
        />

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
        />

        <LibraryPagination
          state={state}
          isTagFocusMode={isTagFocusMode}
          showSpacer
        />
      </div>
    </Page>
  );
}
