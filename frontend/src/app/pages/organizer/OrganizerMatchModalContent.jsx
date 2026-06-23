import { useState } from 'react';
import Spinner from '../../ui/Spinner';
import MatchModalSearchForm from './components/MatchModalSearchForm';
import MatchModalBrowserToolbar from './components/MatchModalBrowserToolbar';
import MatchModalBucket from './components/MatchModalBucket';
import MatchModalConfirmDialog from './components/MatchModalConfirmDialog';
import MatchModalResults from './components/MatchModalResults';
import MatchModalBrowser from './components/MatchModalBrowser';
import useMatchModalViewModel from './components/useMatchModalViewModel';
import EmptyState from '../../ui/EmptyState';
import '../../styles/MatchModal.css';

function getInitialMatchEmptyState({ row, mode, t }) {
  const isTvMode = mode === 'tv' || mode === 'tv';

  if (row?.rawStatus === 'no_match') {
    return {
      title: t('organizer.details.matchModal.noDetectedMatchesTitle') || 'No detected matches',
      description: isTvMode
        ? (t('organizer.details.matchModal.noDetectedMatchesTvDesc') || 'We could not detect a usable tv match for this item. Search above to find the right show.')
        : (t('organizer.details.matchModal.noDetectedMatchesMovieDesc') || 'We could not detect a usable movie match for this item. Search above to find the right title.'),
    };
  }

  if (row?.rawStatus === 'error') {
    return {
      title: t('organizer.details.matchModal.errorDetectedMatchesTitle') || 'Automatic matching ran into an issue',
      description: isTvMode
        ? (t('organizer.details.matchModal.errorDetectedMatchesTvDesc') || 'This item could not be matched automatically right now. Search above to choose the correct show manually.')
        : (t('organizer.details.matchModal.errorDetectedMatchesMovieDesc') || 'This item could not be matched automatically right now. Search above to choose the correct movie manually.'),
    };
  }

  return {
    title: t('organizer.details.matchModal.newDetectedMatchesTitle') || 'No automatic match yet',
    description: isTvMode
      ? (t('organizer.details.matchModal.newDetectedMatchesTvDesc') || 'This item has not been matched to a show yet. Search above to find the correct tv.')
      : (t('organizer.details.matchModal.newDetectedMatchesMovieDesc') || 'This item has not been matched to a movie yet. Search above to find the correct title.'),
  };
}

export default function OrganizerMatchModalContent({
  row,
  rows = [],
  t,
  toast,
  onResolved,
  scanMode,
}) {
  const {
    query,
    setQuery,
    mode,
    year,
    setYear,
    season,
    setSeason,
    episode,
    setEpisode,
    results,
    hasSearched,
    isSearching,
    isResolvingId,
    browserState,
    isBrowserLoading,
    isTvMode,
    browserTitle,
    browserMetaItems,
    bucketEpisodeNumbers,
    visibleResultCandidates,
    shouldShowPosterResults,
    shouldShowListResults,
    handleSearch,
    handleModeChange,
    handleResolve,
    handleBrowseSeason,
    handleCandidateSelect,
    handleBrowserBack,
    toggleBucketEpisode,
    handleApplyBucket,
    handleSelectEpisode,
    confirmState,
    setConfirmState,
    provider,
    handleProviderChange,
    sessionMode,
  } = useMatchModalViewModel({ row, rows, t, toast, onResolved, scanMode });

  const targetRows = rows.length > 0 ? rows : (row ? [row] : []);
  const isBulk = targetRows.length > 1;
  const shouldShowStatusEmptyState = !isBulk && !hasSearched && browserState.view === 'results' && ['no_match', 'new', 'error'].includes(row?.rawStatus);
  const initialMatchEmptyState = shouldShowStatusEmptyState
    ? getInitialMatchEmptyState({ row, mode, t })
    : null;

  const [dontShowAgain, setDontShowAgain] = useState(false);

  const handleConfirmMatch = () => {
    if (!confirmState) return;
    if (dontShowAgain) {
      localStorage.setItem(confirmState.skipKey, 'true');
    }
    confirmState.onConfirm();
    setDontShowAgain(false);
  };

  const handleCancelConfirm = () => {
    setConfirmState(null);
    setDontShowAgain(false);
  };

  return (
    <div className="organizer-match-modal">
      <MatchModalSearchForm
        query={query}
        setQuery={setQuery}
        year={year}
        setYear={setYear}
        season={season}
        setSeason={setSeason}
        episode={episode}
        setEpisode={setEpisode}
        mode={mode}
        isTvMode={isTvMode}
        isSearching={isSearching}
        onSearch={handleSearch}
        onModeChange={handleModeChange}
        isBulk={isBulk}
        t={t}
        provider={provider}
        setProvider={handleProviderChange}
        sessionMode={sessionMode}
        scanMode={scanMode}
      />

      <section className="organizer-match-modal__section">
        {isBulk && !hasSearched && browserState.view === 'results' ? (
          <EmptyState
            variant="modal-intro"
            title={t('organizer.details.matchModal.bulkSearchIntroTitle')}
            description={t('organizer.details.matchModal.bulkSearchIntroDesc')}
          />
        ) : shouldShowStatusEmptyState ? (
          <EmptyState
            variant="modal-default"
            title={initialMatchEmptyState.title}
            description={initialMatchEmptyState.description}
          />
        ) : (
          <>
            <div className="organizer-match-modal__section-header">
              <strong>
                {browserState.view === 'results'
                  ? (hasSearched
                      ? t('organizer.details.matchModal.searchResults')
                      : t('organizer.details.matchModal.detectedMatches'))
                  : browserState.view === 'seasons'
                    ? t('organizer.details.matchModal.seasons')
                    : t('organizer.details.matchModal.episodes')}
              </strong>
              <span>
                {browserState.view === 'results'
                  ? (hasSearched
                      ? t('organizer.details.matchModal.searchResultsHint')
                      : t('organizer.details.matchModal.detectedMatchesHint'))
                  : browserState.view === 'seasons'
                    ? t('organizer.details.matchModal.seasonsHint')
                    : t('organizer.details.matchModal.episodesHint')}
              </span>
            </div>

            <MatchModalBrowserToolbar
              view={browserState.view}
              browserTitle={browserTitle}
              browserMetaItems={browserMetaItems}
              tvCandidate={browserState.tvCandidate}
              selectedSeason={browserState.selectedSeason}
              bucketEpisodeNumbers={bucketEpisodeNumbers}
              onBack={handleBrowserBack}
              onResolve={handleResolve}
              onApplyBucket={handleApplyBucket}
              t={t}
            />

            {!isBulk ? (
              <MatchModalBucket
                view={browserState.view}
                bucketEpisodeNumbers={bucketEpisodeNumbers}
                onToggle={toggleBucketEpisode}
                t={t}
              />
            ) : null}

            {isBrowserLoading || isResolvingId ? (
              <Spinner
                label={isResolvingId ? t('organizer.details.matchModal.applying') : t('organizer.details.matchModal.loading')}
              />
            ) : null}

            <MatchModalResults
              results={results}
              visibleResultCandidates={visibleResultCandidates}
              shouldShowPosterResults={shouldShowPosterResults}
              shouldShowListResults={shouldShowListResults}
              mode={mode}
              isResolvingId={isResolvingId}
              isBrowserLoading={isBrowserLoading}
              onCandidateSelect={handleCandidateSelect}
              row={row}
              t={t}
              hasSearched={hasSearched}
              view={browserState.view}
            />

            <MatchModalBrowser
              browserState={browserState}
              isBrowserLoading={isBrowserLoading}
              row={row}
              bucketEpisodeNumbers={bucketEpisodeNumbers}
              isResolvingId={isResolvingId}
              onBrowseSeason={handleBrowseSeason}
              onSelectEpisode={handleSelectEpisode}
              onToggleBucketEpisode={toggleBucketEpisode}
              episode={episode}
              t={t}
            />
          </>
        )}
      </section>

      <MatchModalConfirmDialog
        confirmState={confirmState}
        dontShowAgain={dontShowAgain}
        setDontShowAgain={setDontShowAgain}
        onCancel={handleCancelConfirm}
        onConfirm={handleConfirmMatch}
        t={t}
      />
    </div>
  );
}
