import { useState, useMemo, useEffect } from 'react';
import { MEDIA_TYPES, toMetadataMediaType } from '@/lib/mediaTypes';
import { useLibraryModeStore } from '@/stores/useLibraryModeStore';
import { useSettingsQuery } from '@/queries';
import { getFirstEnabledProvider, getOrganizerProviderOptions } from '@/lib/providerAvailability';
import api from '@/lib/api';

const getDefaultType = (row) => toMetadataMediaType(row?.rawType, MEDIA_TYPES.MOVIE);

const getBetterTitle = (alternative, episode) => {
  if (!alternative) return episode || '';
  if (!episode) return alternative || '';
  return alternative.length >= episode.length ? alternative : episode;
};

const getDefaultQuery = (row) => {
  const payload = row?.rawPayload || {};
  const parsed = payload.parsed_info;
  if (parsed) {
    const fn = parsed.fn || {};
    const it = parsed.it || {};
    const fd = parsed.fd || {};

    if (fn.alternative_title || fn.episode_title) {
      return getBetterTitle(fn.alternative_title, fn.episode_title);
    }
    if (it.alternative_title || it.episode_title) {
      return getBetterTitle(it.alternative_title, it.episode_title);
    }
    if (fd.alternative_title || fd.episode_title) {
      return getBetterTitle(fd.alternative_title, fd.episode_title);
    }
  }
  return payload.title || payload.fn_title || payload.fd_title || row?.source || '';
};

const getDefaultYear = (row) => {
  const payload = row?.rawPayload || {};
  return payload.year || payload.fn_year || payload.fd_year || '';
};

const getDefaultSeason = (row) => {
  const payload = row?.rawPayload || {};
  return payload.season ?? payload.fn_season ?? payload.fd_season ?? payload.it_season ?? '';
};

const getDefaultEpisode = (row) => {
  const payload = row?.rawPayload || {};
  return payload.episode ?? payload.fn_episode ?? payload.fd_episode ?? payload.it_episode ?? '';
};

export function useMatchSearch({ rows = [], t, toast, scanMode }) {
  const primaryRow = rows[0] || null;
  const isBulk = rows.length > 1;
  const settingsQuery = useSettingsQuery();
  const settings = settingsQuery.data || null;
  const providerOptions = useMemo(() => getOrganizerProviderOptions(scanMode, settings), [scanMode, settings]);
  const [query, setQuery] = useState(() => (isBulk ? '' : getDefaultQuery(primaryRow)));
  const [mode, setMode] = useState(() => {
    const isSceneModeOrType = scanMode === 'scenes' || primaryRow?.rawType === 'scene' || primaryRow?.rawPayload?.scan_mode === 'scenes';
    if (isSceneModeOrType) {
      return 'scene';
    }
    return isBulk ? MEDIA_TYPES.TV : getDefaultType(primaryRow);
  });
  const [year, setYear] = useState(() => (isBulk ? '' : String(getDefaultYear(primaryRow) || '')));
  const [season, setSeason] = useState(() => (isBulk ? '' : String(getDefaultSeason(primaryRow) || '')));
  const [episode, setEpisode] = useState(() => (isBulk ? '' : String(getDefaultEpisode(primaryRow) || '')));
  const [results, setResults] = useState([]);
  const [hasSearched, setHasSearched] = useState(false);
  const sessionMode = useLibraryModeStore((state) => state.sessionMode);
  const includeAdult = sessionMode === 'nsfw';
  const [provider, setProvider] = useState(() => {
    const isSceneModeOrType = scanMode === 'scenes' || primaryRow?.rawType === 'scene' || primaryRow?.rawPayload?.scan_mode === 'scenes';
    const fallbackProvider = isSceneModeOrType ? 'stashdb' : 'tmdb';
    return getFirstEnabledProvider(providerOptions, fallbackProvider);
  });
  const isTvMode = mode === MEDIA_TYPES.TV && provider !== 'porndb';

  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    const isSceneModeOrType = scanMode === 'scenes' || primaryRow?.rawType === 'scene' || primaryRow?.rawPayload?.scan_mode === 'scenes';
    const fallbackProvider = isSceneModeOrType ? 'stashdb' : 'tmdb';
    const nextProvider = getFirstEnabledProvider(providerOptions, provider || fallbackProvider);
    if (nextProvider !== provider) {
      setProvider(nextProvider);
    }
  }, [primaryRow?.rawPayload?.scan_mode, primaryRow?.rawType, provider, providerOptions, scanMode]);

  const existingCandidates = useMemo(
    () => {
      if (rows.length > 1) {
        return [];
      }
      const isSceneModeOrType = scanMode === 'scenes' || primaryRow?.rawType === 'scene' || primaryRow?.rawPayload?.scan_mode === 'scenes';
      return (primaryRow?.rawPayload?.matches || [])
        .map((match) => ({
          id: match.external_id || match.tmdb_id || match.id,
          tmdb_id: match.external_id || match.tmdb_id || match.id,
          type: match.type || (isSceneModeOrType ? 'scene' : null),
          title: match.title,
          release_date: match.year ? `${match.year}-01-01` : null,
          first_air_date: match.year ? `${match.year}-01-01` : null,
          poster_path: match.image_path || match.poster_path,
          vote_average: match.vote_average,
          confidence: match.confidence,
          is_active: match.is_active,
          source: 'existing',
          provider: match.provider || 'tmdb',
        }));
    },
    [primaryRow, rows.length, scanMode],
  );

  const performSearch = async (resetBrowser, searchMode = mode, searchProvider = provider) => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      toast(t('organizer.toasts.matchSearchMissingQuery'), 'danger');
      return false;
    }

    setHasSearched(true);
    resetBrowser();
    setIsSearching(true);
    try {
      const data = await api.metadata.search({
        query: trimmedQuery,
        itemType: searchMode,
        year,
        season,
        episode,
        includeAdult,
        provider: searchProvider,
      });
      const searchResults = Array.isArray(data)
        ? data.map((candidate) => ({
          ...candidate,
          media_type: toMetadataMediaType(candidate.media_type || candidate.type || searchMode, searchMode),
        }))
        : [];
      setResults(searchResults);
      return searchResults;
    } catch (error) {
      toast(error.message || t('organizer.toasts.matchSearchFailed'), 'danger');
      return false;
    } finally {
      setIsSearching(false);
    }
  };

  return {
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
    setResults,
    hasSearched,
    setHasSearched,
    isSearching,
    isTvMode,
    existingCandidates,
    performSearch,
    provider,
    setProvider,
    sessionMode,
    providerOptions,
  };
}
