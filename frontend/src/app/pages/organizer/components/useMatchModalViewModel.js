import { useMatchSearch } from './hooks/useMatchSearch';
import { useMatchBrowser } from './hooks/useMatchBrowser';
import { useMatchResolve } from './hooks/useMatchResolve';
import { MEDIA_TYPES, toMetadataMediaType } from '@/lib/mediaTypes';

export default function useMatchModalViewModel({
  row,
  rows = [],
  t,
  toast,
  onResolved,
  scanMode,
}) {
  const targetRows = rows.length > 0 ? rows : (row ? [row] : []);
  const isBulk = targetRows.length > 1;

  const {
    query,
    setQuery,
    mode,
    setMode,
    year,
    setYear,
    season,
    setSeason,
    episode,
    setEpisode,
    results,
    hasSearched,
    isSearching,
    isTvMode,
    existingCandidates,
    performSearch,
    provider,
    setProvider,
    sessionMode,
  } = useMatchSearch({ rows: targetRows, t, toast, scanMode });

  const {
    browserState,
    isBrowserLoading,
    resetBrowser,
    handleBrowseTv,
    handleBrowseSeason,
    handleDirectBrowse,
    handleBrowserBack,
    browserTitle,
    browserMetaItems,
    bucketEpisodeNumbers,
    toggleBucketEpisode,
  } = useMatchBrowser({ t });

  const {
    confirmState,
    setConfirmState,
    isResolvingId,
    handleResolve,
  } = useMatchResolve({
    rows: targetRows,
    t,
    toast,
    onResolved,
    mode,
    season,
    episode,
  });

  const handleBrowseSeasonClick = async (seasonEntry) => {
    if (isBulk) {
      await handleResolve(browserState.tvCandidate, {
        season: seasonEntry.season_number,
        episode: null,
      });
    } else {
      await handleBrowseSeason(seasonEntry);
    }
  };

  const handleSearch = async (event) => {
    event?.preventDefault();
    const searchResults = await performSearch(resetBrowser);
    if (searchResults && searchResults.length === 1 && mode === MEDIA_TYPES.TV) {
      const parsedSeason = Number.parseInt(season, 10);
      if (Number.isFinite(parsedSeason)) {
        handleDirectBrowse(searchResults[0], parsedSeason);
      } else {
        handleBrowseTv(searchResults[0]);
      }
    }
  };

  const handleModeChange = async (nextMode) => {
    console.log('[DEBUG] handleModeChange called with nextMode:', nextMode, 'current mode:', mode);
    if (nextMode === mode) {
      console.log('[DEBUG] handleModeChange: nextMode matches current mode. Bailing out.');
      return;
    }

    setMode(nextMode);
    resetBrowser();

    if (hasSearched && !isSearching) {
      console.log('[DEBUG] handleModeChange: triggering automatic search with new mode:', nextMode);
      const searchResults = await performSearch(resetBrowser, nextMode);
      if (searchResults && searchResults.length === 1 && nextMode === MEDIA_TYPES.TV) {
        const parsedSeason = Number.parseInt(season, 10);
        if (Number.isFinite(parsedSeason)) {
          handleDirectBrowse(searchResults[0], parsedSeason);
        } else {
          handleBrowseTv(searchResults[0]);
        }
      }
    }
  };

  const handleProviderChange = async (nextProvider) => {
    console.log('[DEBUG] handleProviderChange called with nextProvider:', nextProvider, 'current provider:', provider);
    if (nextProvider === provider) {
      console.log('[DEBUG] handleProviderChange: nextProvider matches current provider. Bailing out.');
      return;
    }

    setProvider(nextProvider);
    resetBrowser();

    let nextMode = mode;
    if (scanMode === 'scenes') {
      nextMode = 'scene';
      setMode('scene');
    } else if (nextProvider === 'porndb') {
      console.log('[DEBUG] handleProviderChange: PornDB selected in non-scenes mode. Forcing mode to movie.');
      nextMode = 'movie';
      setMode('movie');
    }

    if (hasSearched && !isSearching) {
      console.log('[DEBUG] handleProviderChange: triggering automatic search with nextMode:', nextMode, 'nextProvider:', nextProvider);
      const searchResults = await performSearch(resetBrowser, nextMode, nextProvider);
      if (searchResults && searchResults.length === 1 && nextMode === MEDIA_TYPES.TV && nextProvider !== 'porndb') {
        const parsedSeason = Number.parseInt(season, 10);
        if (Number.isFinite(parsedSeason)) {
          handleDirectBrowse(searchResults[0], parsedSeason);
        } else {
          handleBrowseTv(searchResults[0]);
        }
      }
    }
  };

  const handleCandidateSelect = async (candidate) => {
    const mediaType = toMetadataMediaType(candidate.type || candidate.media_type || mode, mode);
    if (mediaType === MEDIA_TYPES.TV) {
      const parsedSeason = Number.parseInt(season, 10);
      if (Number.isFinite(parsedSeason)) {
        handleDirectBrowse(candidate, parsedSeason);
      } else {
        await handleBrowseTv(candidate);
      }
      return;
    }
    if (candidate.is_active) {
      toast(t('organizer.toasts.matchAlreadyActive'), 'info');
      return;
    }
    await handleResolve(candidate);
  };

  const handleApplyBucket = async () => {
    if (!browserState.tvCandidate || !browserState.selectedSeason || bucketEpisodeNumbers.length === 0) {
      return;
    }

    await handleResolve(
      {
        ...browserState.tvCandidate,
        episodes: bucketEpisodeNumbers,
      },
      {
        season: browserState.selectedSeason.season_number,
        episode: null,
      },
    );
  };

  const handleSelectEpisode = async (episodeEntry) => {
    if (!browserState.tvCandidate || !browserState.selectedSeason) {
      return;
    }

    await handleResolve(
      browserState.tvCandidate,
      {
        season: browserState.selectedSeason.season_number,
        episode: episodeEntry.episode_number,
      },
    );
  };

  const visibleResultCandidates = hasSearched ? results : existingCandidates;
  const shouldShowPosterResults = browserState.view === 'results' && !hasSearched && visibleResultCandidates.length > 0;
  const shouldShowListResults = browserState.view === 'results' && hasSearched && results.length > 0;

  return {
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
    handleProviderChange,
    handleResolve,
    handleBrowseSeason: handleBrowseSeasonClick,
    handleCandidateSelect,
    handleBrowserBack,
    toggleBucketEpisode,
    handleApplyBucket,
    handleSelectEpisode,
    confirmState,
    setConfirmState,
    provider,
    sessionMode,
  };
}
