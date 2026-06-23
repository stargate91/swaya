import { Search } from 'lucide-react';
import IconButton from '../../../ui/IconButton';
import SegmentedControl from '../../../ui/SegmentedControl';
import Tooltip from '../../../ui/Tooltip';
import Input from '../../../ui/Input';
import Dropdown from '../../../ui/Dropdown';

export default function MatchModalSearchForm({
  query,
  setQuery,
  year,
  setYear,
  season,
  setSeason,
  episode,
  setEpisode,
  mode,
  isTvMode,
  isSearching,
  onSearch,
  onModeChange,
  isBulk = false,
  t,
  provider,
  setProvider,
  sessionMode,
  scanMode,
  providerOptions,
}) {
  return (
    <form className="organizer-match-modal__search" onSubmit={onSearch}>
      <div className="organizer-match-modal__search-layout">
        <div
          className={`organizer-match-modal__search-grid${isTvMode && !isBulk ? ' is-tv' : ' is-movie'}`}
        >
          {sessionMode === 'nsfw' ? (
            <div className="organizer-match-modal__search-input-group organizer-match-modal__field organizer-match-modal__field--query">
              <div className="organizer-match-modal__search-source">
                <Dropdown
                  className="organizer-match-dropdown"
                  menuClassName="search-source-dropdown-menu"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  options={providerOptions}
                />
              </div>
              <div className="organizer-match-modal__form-input-wrapper">
                <Input
                  type="text"
                  placeholder={
                    isTvMode
                      ? t('organizer.details.matchModal.queryPlaceholderTv')
                      : t('organizer.details.matchModal.queryPlaceholderMovie')
                  }
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  aria-label={t('organizer.details.matchModal.query')}
                />
              </div>
            </div>
          ) : (
            <Input
              className="organizer-match-modal__field organizer-match-modal__field--query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={
                isTvMode
                  ? t('organizer.details.matchModal.queryPlaceholderTv')
                  : t('organizer.details.matchModal.queryPlaceholderMovie')
              }
              aria-label={t('organizer.details.matchModal.query')}
            />
          )}
          <Input
            className="organizer-match-modal__field organizer-match-modal__field--year"
            value={year}
            onChange={(event) => setYear(event.target.value)}
            placeholder={t('organizer.details.matchModal.year')}
            aria-label={t('organizer.details.matchModal.year')}
            inputMode="numeric"
          />
          {isTvMode && !isBulk ? (
            <Input
              className="organizer-match-modal__field organizer-match-modal__field--compact"
              value={season}
              onChange={(event) => setSeason(event.target.value)}
              placeholder={t('organizer.details.matchModal.seasonShort')}
              aria-label={t('organizer.details.matchModal.seasonShort')}
              inputMode="numeric"
            />
          ) : null}
          {isTvMode && !isBulk ? (
            <Input
              className="organizer-match-modal__field organizer-match-modal__field--compact"
              value={episode}
              onChange={(event) => setEpisode(event.target.value)}
              placeholder={t('organizer.details.matchModal.episodeShort')}
              aria-label={t('organizer.details.matchModal.episodeShort')}
              inputMode="numeric"
            />
          ) : null}
        </div>
        <div className="organizer-match-modal__search-actions">
          <Tooltip
            content={isSearching ? t('organizer.details.matchModal.searching') : t('organizer.details.matchModal.search')}
            side="top"
          >
            <IconButton
              type="submit"
              variant="secondary"
              className="organizer-match-modal__search-button"
              disabled={isSearching}
              label={isSearching ? t('organizer.details.matchModal.searching') : t('organizer.details.matchModal.search')}
              title={null}
            >
              <Search size={15} />
            </IconButton>
          </Tooltip>
        </div>
        {!isBulk && provider !== 'porndb' && scanMode !== 'scenes' ? (
          <SegmentedControl
            className="organizer-match-modal__mode-toggle"
            options={[
              { value: 'movie', label: t('organizer.details.matchModal.movie') },
              { value: 'tv', label: t('organizer.details.matchModal.tv') },
            ]}
            value={mode}
            onChange={onModeChange}
            ariaLabel={t('organizer.details.matchModal.type')}
          />
        ) : null}
      </div>
    </form>
  );
}


