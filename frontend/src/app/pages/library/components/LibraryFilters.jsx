import { useMemo, useState } from 'react';
import Dropdown from '@/ui/Dropdown';
import SegmentedControl from '@/ui/SegmentedControl';
import Pill from '@/ui/Pill';
import { SlidersHorizontal } from 'lucide-react';
import {
  isLibraryCollectionTab,
  isLibraryPeopleTab,
  isLibraryTvTab,
  isLibraryTagsTab,
  isLibraryVideoTab,
  isLibraryScenesTab,
} from '@/lib/libraryTabs';

const formatPhysicalAttributeLabel = (val) => {
  if (!val) return '';
  if (val.toUpperCase() === 'NA' || val.toUpperCase() === 'N/A') return 'N/A';
  return val
    .toLowerCase()
    .split(' ')
    .map(word => {
      if (word === 'na' || word === 'n/a') return 'N/A';
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(' ');
};

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
  performerFilter,
  setPerformerFilter,
  studioFilter,
  setStudioFilter,
  hairColorFilter,
  setHairColorFilter,
  ethnicityFilter,
  setEthnicityFilter,
  eyeColorFilter,
  setEyeColorFilter,
  tattoosFilter,
  setTattoosFilter,
  piercingsFilter,
  setPiercingsFilter,
  breastTypeFilter,
  setBreastTypeFilter,
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

  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <>
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
                      ...(activeSessionMode === 'nsfw' ? [
                        { value: 'cup_size', label: t('library.sort.cupSize') || 'Breast Size' },
                        { value: 'waist', label: t('library.sort.waist') || 'Waist Size' },
                        { value: 'hip', label: t('library.sort.hip') || 'Hip Size' },
                        { value: 'hourglass_ratio', label: t('library.sort.hourglassRatio') || 'Hourglass Ratio' },
                        { value: 'body_slender', label: t('library.sort.bodySlender') || 'Slender / Athletic' },
                        { value: 'body_curvy', label: t('library.sort.bodyCurvy') || 'Hourglass / Curvy' }
                      ] : []),
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
        )
      }

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

        {isScenesTab && activeSessionMode === 'nsfw' && filterData?.performers && filterData.performers.length > 0 && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.performerLabel') || 'Performer:'}</span>
            <Dropdown
              variant="sorter"
              value={performerFilter}
              onChange={(e) => {
                setPerformerFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: '', label: t('library.filter.allPerformers') || 'All Performers' },
                ...(filterData.performers).map(p => ({ value: String(p.id), label: p.name })),
              ]}
            />
          </div>
        )}

        {isScenesTab && activeSessionMode === 'nsfw' && filterData?.studios && filterData.studios.length > 0 && (
          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.studioLabel') || 'Studio:'}</span>
            <Dropdown
              variant="sorter"
              value={studioFilter}
              onChange={(e) => {
                setStudioFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: '', label: t('library.filter.allStudios') || 'All Studios' },
                ...(filterData.studios).map(s => ({ value: String(s.id), label: s.name })),
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

      <div className="library-filters-right">
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

        {isPeopleTab && activeSessionMode === 'nsfw' && (
          <Pill
            variant={showAdvanced ? 'filter-active' : 'favorite'}
            onClick={() => setShowAdvanced(prev => !prev)}
            className="advanced-filters-toggle"
          >
            {showAdvanced ? (t('library.filter.lessFilters') || 'Less') : (t('library.filter.advancedFilters') || 'Filters')}
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
    </div>

    {showAdvanced && isPeopleTab && activeSessionMode === 'nsfw' && (
      <div className="organizer-panel__row library-filters-row library-filters-advanced-row">
        <div className="library-filters-left">
          {filterData?.hair_colors && filterData.hair_colors.length > 0 && (
            <div className="library-sorter-container">
              <span className="library-sorter-label">{t('library.filter.hairColorLabel') || 'Hair Color:'}</span>
              <Dropdown
                variant="sorter"
                value={hairColorFilter}
                onChange={(e) => {
                  setHairColorFilter(e.target.value);
                  setCurrentPage(1);
                }}
                options={[
                  { value: '', label: t('library.filter.allHairColors') || 'All Hair Colors' },
                  ...(filterData.hair_colors).map(hc => ({ value: hc, label: formatPhysicalAttributeLabel(hc) })),
                ]}
              />
            </div>
          )}

          {filterData?.ethnicities && filterData.ethnicities.length > 0 && (
            <div className="library-sorter-container">
              <span className="library-sorter-label">{t('library.filter.ethnicityLabel') || 'Ethnicity:'}</span>
              <Dropdown
                variant="sorter"
                value={ethnicityFilter}
                onChange={(e) => {
                  setEthnicityFilter(e.target.value);
                  setCurrentPage(1);
                }}
                options={[
                  { value: '', label: t('library.filter.allEthnicities') || 'All Ethnicities' },
                  ...(filterData.ethnicities).map(eth => ({ value: eth, label: formatPhysicalAttributeLabel(eth) })),
                ]}
              />
            </div>
          )}

          {filterData?.eye_colors && filterData.eye_colors.length > 0 && (
            <div className="library-sorter-container">
              <span className="library-sorter-label">{t('library.filter.eyeColorLabel') || 'Eye Color:'}</span>
              <Dropdown
                variant="sorter"
                value={eyeColorFilter}
                onChange={(e) => {
                  setEyeColorFilter(e.target.value);
                  setCurrentPage(1);
                }}
                options={[
                  { value: '', label: t('library.filter.allEyeColors') || 'All Eye Colors' },
                  ...(filterData.eye_colors).map(ec => ({ value: ec, label: formatPhysicalAttributeLabel(ec) })),
                ]}
              />
            </div>
          )}

          {filterData?.breast_types && filterData.breast_types.length > 0 && (
            <div className="library-sorter-container">
              <span className="library-sorter-label">{t('library.filter.breastTypeLabel') || 'Breast Type:'}</span>
              <Dropdown
                variant="sorter"
                value={breastTypeFilter}
                onChange={(e) => {
                  setBreastTypeFilter(e.target.value);
                  setCurrentPage(1);
                }}
                options={[
                  { value: '', label: t('library.filter.allBreastTypes') || 'All Types' },
                  ...(filterData.breast_types).map(bt => ({ value: bt, label: formatPhysicalAttributeLabel(bt) })),
                ]}
              />
            </div>
          )}

          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.tattoosLabel') || 'Tattoos:'}</span>
            <Dropdown
              variant="sorter"
              value={tattoosFilter}
              onChange={(e) => {
                setTattoosFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: '', label: t('library.filter.allTattoos') || 'All Options' },
                { value: 'yes', label: t('library.filter.yes') || 'Yes' },
                { value: 'no', label: t('library.filter.no') || 'No' },
              ]}
            />
          </div>

          <div className="library-sorter-container">
            <span className="library-sorter-label">{t('library.filter.piercingsLabel') || 'Piercings:'}</span>
            <Dropdown
              variant="sorter"
              value={piercingsFilter}
              onChange={(e) => {
                setPiercingsFilter(e.target.value);
                setCurrentPage(1);
              }}
              options={[
                { value: '', label: t('library.filter.allPiercings') || 'All Options' },
                { value: 'yes', label: t('library.filter.yes') || 'Yes' },
                { value: 'no', label: t('library.filter.no') || 'No' },
              ]}
            />
          </div>
        </div>
      </div>
    )}
  </>
  );
}
