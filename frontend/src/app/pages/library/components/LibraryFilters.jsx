import { useMemo } from 'react';
import Dropdown from '@/ui/Dropdown';
import SegmentedControl from '@/ui/SegmentedControl';
import Pill from '@/ui/Pill';
import {
  isLibraryCollectionTab,
  isLibraryPeopleTab,
  isLibraryTvTab,
  isLibraryTagsTab,
  isLibraryVideoTab,
  isLibraryScenesTab,
} from '@/lib/libraryTabs';

export default function LibraryFilters({
  t,
  settings,
  resolvedTab,
  isCollections,
  isPeople,
  activeSessionMode,
  sortKey,
  setSortKey,
  sortDirection,
  setSortDirection,
  setCurrentPage,
  collectionStatusFilter,
  setCollectionStatusFilter,
  peopleRoleFilter,
  setPeopleRoleFilter,
  genderFilter,
  setGenderFilter,
  ownershipFilter,
  setOwnershipFilter,
  watchedFilter,
  setWatchedFilter,
  genreFilter,
  setGenreFilter,
  decadeFilter,
  setDecadeFilter,
  yearFilter,
  setYearFilter,
  timeFilterMode,
  setTimeFilterMode,
  favoriteFilter,
  setFavoriteFilter,
  filterData,
}) {
  const isVideoTab = isLibraryVideoTab(resolvedTab);
  const isCollectionTab = isLibraryCollectionTab(resolvedTab);
  const isPeopleTab = isLibraryPeopleTab(resolvedTab);
  const isTagsTab = isLibraryTagsTab(resolvedTab);
  const isTvTab = isLibraryTvTab(resolvedTab);
  const isScenesTab = isLibraryScenesTab(resolvedTab);

  const yearsList = filterData?.years;
  const decades = useMemo(() => {
    if (!yearsList) return [];
    const set = new Set(yearsList.map(y => `${Math.floor(Number(y) / 10) * 10}s`));
    return Array.from(set).sort((a, b) => b.localeCompare(a));
  }, [yearsList]);


  return (
    <div className="organizer-panel__row library-filters-row">
      <div className="library-filters-left">
        {(isVideoTab || isCollectionTab || isPeopleTab || isTagsTab) && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.sort.label') || 'Sort:'}</span>
            <Dropdown
              variant="sorter"
              value={sortKey}
              onChange={(e) => {
                setSortKey(e.target.value);
                setCurrentPage(1);
              }}
              sortDirection={sortDirection}
              onSortDirectionToggle={() => {
                setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
                setCurrentPage(1);
              }}
              options={
                isCollectionTab
                  ? [
                    { value: 'owned_count', label: t('library.sort.ownedCount') || 'Item Count' },
                    { value: 'title', label: t('library.sort.title') || 'Title' },
                  ]
                  : isTagsTab
                    ? [
                      { value: 'total_count', label: t('library.sort.itemCount') || 'Item Count' },
                      { value: 'name', label: t('library.sort.name') || 'Name' },
                    ]
                  : isPeopleTab
                    ? [
                      { value: 'library_count', label: t('library.sort.libraryCount') || 'Library Count' },
                      { value: 'rating', label: activeSessionMode === 'nsfw' ? (t('library.sort.porndbPerformerRating') || 'PornDB performer rating') : (t('library.sort.popularity') || 'Popularity') },
                      { value: 'name', label: t('library.sort.name') || 'Name' },
                      { value: 'birthday', label: t('library.sort.birthday') || 'Birthdate' },
                      { value: 'user_rating', label: t('library.sort.userRating') || 'User Rating' },
                    ]
                    : [
                      { value: 'title', label: t('library.sort.title') || 'Title' },
                      { value: 'year', label: isTvTab ? (t('library.sort.firstAirYear') || 'First Air Year') : (t('library.sort.year') || 'Year') },
                      { value: 'release_date', label: isTvTab ? (t('library.sort.firstAirDate') || 'First Air Date') : (t('library.sort.releaseDate') || 'Release Date') },
                      ...(!isScenesTab ? [
                        { value: 'rating_imdb', label: t('library.sort.imdbRating') || 'IMDb Rating' },
                        { value: 'rating', label: t('library.sort.tmdbRating') || 'TMDb Rating' },
                      ] : []),
                      { value: 'user_rating', label: t('library.sort.userRating') || 'User Rating' },
                      { value: 'duration', label: t('library.sort.duration') || 'Duration' },
                      ...(ownershipFilter !== 'unowned' ? [
                        { value: 'file_size', label: t('library.sort.fileSize') || 'File Size' },
                        { value: 'last_watched', label: t('library.sort.lastWatched') || 'Last Watched' },
                      ] : []),
                    ]
              }
            />
          </div>
        )}

        {isCollections && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.statusLabel') || 'Status:'}</span>
            <Dropdown
              variant="sorter"
              value={collectionStatusFilter}
              onChange={(e) => {
                setCollectionStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: t('library.filter.all') || 'All' },
                { value: 'complete', label: t('library.filter.complete') || 'Complete' },
                { value: 'in_progress', label: t('library.filter.inProgress') || 'In Progress' },
              ]}
            />
          </div>
        )}

        {isPeople && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.roleLabel') || 'Role:'}</span>
            <Dropdown
              variant="sorter"
              value={peopleRoleFilter}
              onChange={(e) => {
                setPeopleRoleFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: t('library.filter.all') || 'All' },
                { value: 'actor', label: t('library.people.roles.actor') || 'Actor' },
                { value: 'director', label: t('library.people.roles.director') || 'Director' },
                { value: 'writer', label: t('library.people.roles.writer') || 'Writer' },
              ]}
            />
          </div>
        )}

        {isPeople && (activeSessionMode !== 'nsfw' || !settings?.adult_gender_preference || settings.adult_gender_preference === 'all') && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.genderLabel') || 'Gender:'}</span>
            <Dropdown
              variant="sorter"
              value={genderFilter}
              onChange={(e) => {
                setGenderFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: t('library.filter.all') || 'All' },
                { value: 'female', label: t('library.filter.female') || 'Female' },
                { value: 'male', label: t('library.filter.male') || 'Male' },
              ]}
            />
          </div>
        )}

        {isVideoTab && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.label') || 'Filter:'}</span>
            <Dropdown
              variant="sorter"
              value={ownershipFilter}
              onChange={(e) => {
                setOwnershipFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: 'owned', label: t('library.filter.have') || 'Have' },
                { value: 'unowned', label: t('library.filter.missing') || 'Missing' },
              ]}
            />
          </div>
        )}

        {isVideoTab && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.statusLabel') || 'Status:'}</span>
            <Dropdown
              variant="sorter"
              value={watchedFilter}
              onChange={(e) => {
                setWatchedFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: t('library.filter.all') || 'All' },
                { value: 'watched', label: t('library.filter.watched') || 'Watched' },
                { value: 'unwatched', label: t('library.filter.unwatched') || 'Unwatched' },
              ]}
            />
          </div>
        )}

        {isVideoTab && !isScenesTab && activeSessionMode !== 'nsfw' && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.genreLabel') || 'Genre:'}</span>
            <Dropdown
              variant="sorter"
              value={genreFilter}
              onChange={(e) => {
                setGenreFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: '', label: t('library.filter.allGenres') || 'All Genres' },
                ...(filterData?.genres || []).map(g => ({ value: g, label: t(`library.genres.${g}`, g) })),
              ]}
            />
          </div>
        )}

        {isVideoTab && timeFilterMode === 'decade' && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.decadeLabel') || 'Decade:'}</span>
            <Dropdown
              variant="sorter"
              value={decadeFilter}
              onChange={(e) => {
                setDecadeFilter(e.target.value);
                setYearFilter('');
                setCurrentPage(1);
              }}
              options={[
                { value: 'all', label: t('library.filter.allDecades') || 'All Decades' },
                ...(decades || []).map(d => ({ value: d, label: d })),
              ]}
            />
          </div>
        )}

        {isVideoTab && timeFilterMode === 'year' && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.yearLabel') || 'Year:'}</span>
            <Dropdown
              variant="sorter"
              value={yearFilter}
              onChange={(e) => {
                setYearFilter(e.target.value);
                setDecadeFilter('all');
                setCurrentPage(1);
              }}
              options={[
                { value: '', label: t('library.filter.allYears') || 'All Years' },
                ...(filterData?.years || []).map(y => ({ value: String(y), label: String(y) })),
              ]}
            />
          </div>
        )}
      </div>

      {isPeople && (
        <Pill
          variant={favoriteFilter === 'favorites' ? 'favorite-active' : 'favorite'}
          onClick={() => {
            setFavoriteFilter(prev => prev === 'favorites' ? 'all' : 'favorites');
            setCurrentPage(1);
          }}
        >
          {t('library.filter.favorite') || 'Favourite'}
        </Pill>
      )}

      {isVideoTab && (
        <SegmentedControl
          variant="filter"
          value={timeFilterMode}
          onChange={(val) => {
            setTimeFilterMode(val);
            setDecadeFilter('all');
            setYearFilter('');
            setCurrentPage(1);
          }}
          options={[
            { value: 'decade', label: t('library.filter.decadeMode') || 'Decade' },
            { value: 'year', label: t('library.filter.yearMode') || 'Year' },
          ]}
        />
      )}
    </div>
  );
}
