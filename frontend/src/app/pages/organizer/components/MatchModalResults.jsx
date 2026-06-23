import { useRef, useEffect } from 'react';
import MatchCandidateCard from './MatchCandidateCard';
import EmptyState from '../../../ui/EmptyState';

export default function MatchModalResults({
  results,
  visibleResultCandidates,
  shouldShowPosterResults,
  shouldShowListResults,
  mode,
  isResolvingId,
  isBrowserLoading,
  onCandidateSelect,
  row,
  t,
  hasSearched,
  view,
}) {
  const posterResultsRef = useRef(null);

  useEffect(() => {
    const el = posterResultsRef.current;
    if (!el) return;
    const handleWheel = (e) => {
      if (e.deltaY === 0) return;
      e.preventDefault();
      el.scrollLeft += e.deltaY;
    };
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [shouldShowPosterResults]);

  return (
    <>
      {shouldShowPosterResults ? (
        <div
          ref={posterResultsRef}
          className={`organizer-match-modal__poster-results${mode === 'scene' || visibleResultCandidates.some(c => c.type === 'scene' || c.media_type === 'scene') ? ' is-scene' : ''}`}
        >
          {visibleResultCandidates.map((candidate) => (
            <MatchCandidateCard
              key={`existing-${candidate.tmdb_id || candidate.id}`}
              candidate={candidate}
              sourceLabel="existing"
              variant="poster"
              mode={mode}
              isResolvingId={isResolvingId}
              isBrowserLoading={isBrowserLoading}
              onSelect={onCandidateSelect}
              t={t}
              rowStatus={row?.rawStatus}
            />
          ))}
        </div>
      ) : null}

      {shouldShowListResults ? (
        <div className="organizer-match-modal__results">
          {results.map((candidate) => (
            <MatchCandidateCard
              key={`search-${candidate.tmdb_id || candidate.id}`}
              candidate={candidate}
              sourceLabel="search"
              variant="list"
              mode={mode}
              isResolvingId={isResolvingId}
              isBrowserLoading={isBrowserLoading}
              onSelect={onCandidateSelect}
              t={t}
              rowStatus={row?.rawStatus}
            />
          ))}
        </div>
      ) : null}

      {view === 'results' && hasSearched && results.length === 0 && !isBrowserLoading ? (
        <EmptyState
          title={mode === 'tv' || mode === 'tv'
            ? (t('organizer.details.matchModal.noResultsTvTitle') || 'No matching tv found')
            : (t('organizer.details.matchModal.noResultsMovieTitle') || 'No matching movies found')
          }
          description={mode === 'tv' || mode === 'tv'
            ? (t('organizer.details.matchModal.noResultsTvDesc') || 'We could not find any tv matching your search. Try adjusting the title or year.')
            : (t('organizer.details.matchModal.noResultsMovieDesc') || 'We could not find any movies matching your search. Try adjusting the title or year.')
          }
          variant="modal-search"
        />
      ) : null}
    </>
  );
}
