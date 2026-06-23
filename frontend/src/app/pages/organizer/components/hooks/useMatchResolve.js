import { useState } from 'react';
import { useResolveMetadataMutation, useBulkResolveMetadataMutation } from '@/queries';
import { MEDIA_TYPES, isEpisodeMediaType, toMetadataMediaType } from '@/lib/mediaTypes';

const toOptionalNumber = (value) => {
  const normalized = String(value ?? '').trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number.parseInt(normalized, 10);
  return Number.isFinite(parsed) ? parsed : null;
};

const buildResolvePayload = (row, candidate, selectedMode, seasonValue, episodeValue, sessionMode) => {
  const episodeList = Array.isArray(candidate?.episodes) ? candidate.episodes : [];
  const mediaType = toMetadataMediaType(candidate?.type || candidate?.media_type || selectedMode, selectedMode);
  const season = toOptionalNumber(seasonValue);
  const episode = toOptionalNumber(episodeValue);

  const payload = {
    item_id: row.itemId,
    tmdb_id: candidate.tmdb_id || candidate.id,
    type: mediaType,
    media_type: mediaType,
    provider: candidate.provider || 'tmdb',
    is_adult: sessionMode === 'nsfw',
  };

  const isMatchedEpisode = isEpisodeMediaType(row.rawType)
    && (row.rawStatus === 'matched' || row.rawStatus === 'renamed' || row.rawStatus === 'organized');

  if (mediaType === MEDIA_TYPES.TV) {
    if (season != null) {
      payload.season_number = season;
    } else if (isMatchedEpisode) {
      payload.season_number = null;
    }

    if (episodeList.length > 0) {
      payload.episode_number = episodeList;
    } else if (episode != null) {
      payload.episode_number = episode;
    } else if (isMatchedEpisode) {
      payload.episode_number = null;
    }
  }

  return payload;
};

const getDefaultSeason = (row) => {
  const payload = row?.rawPayload || {};
  return payload.season ?? payload.fn_season ?? payload.fd_season ?? payload.it_season ?? '';
};

const getDefaultEpisode = (row) => {
  const payload = row?.rawPayload || {};
  return payload.episode ?? payload.fn_episode ?? payload.fd_episode ?? payload.it_episode ?? '';
};

export function useMatchResolve({ rows = [], t, toast, onResolved, mode, sessionMode }) {
  const [confirmState, setConfirmState] = useState(null);
  const [isResolvingId, setIsResolvingId] = useState(null);
  const resolveMutation = useResolveMetadataMutation();
  const bulkResolveMutation = useBulkResolveMetadataMutation();

  const requestConfirm = (type, skipKey, onConfirm) => {
    if (localStorage.getItem(skipKey) === 'true') {
      onConfirm();
      return;
    }

    let hasExisting = false;
    let existingDetails = '';

    for (const r of rows) {
      const isMatchedEpisode = isEpisodeMediaType(r.rawType)
        && (r.rawStatus === 'matched' || r.rawStatus === 'renamed' || r.rawStatus === 'organized');
      if (!isMatchedEpisode) {
        continue;
      }
      const defaultSeasonVal = getDefaultSeason(r);
      const defaultEpisodeVal = getDefaultEpisode(r);
      if (type === 'tv') {
        if (defaultSeasonVal != null || defaultEpisodeVal != null) {
          hasExisting = true;
          const parts = [];
          if (defaultSeasonVal != null) parts.push(`S${defaultSeasonVal}`);
          if (defaultEpisodeVal != null) parts.push(`E${defaultEpisodeVal}`);
          existingDetails = parts.join(' ');
          break;
        }
      } else if (type === 'season') {
        if (defaultEpisodeVal != null) {
          hasExisting = true;
          existingDetails = `E${defaultEpisodeVal}`;
          break;
        }
      }
    }

    setConfirmState({
      type,
      skipKey,
      hasExisting,
      existingDetails,
      onConfirm: () => {
        onConfirm();
        setConfirmState(null);
      },
    });
  };

  const handleResolve = async (candidate, overrides = {}) => {
    const candidateId = candidate.tmdb_id || candidate.id;
    const effectiveSeason = overrides.season !== undefined ? overrides.season : null;
    const effectiveEpisode = overrides.episode !== undefined ? overrides.episode : null;

    const isMatchedEpisode = rows.some((r) => (
      isEpisodeMediaType(r.rawType)
      && (r.rawStatus === 'matched' || r.rawStatus === 'renamed' || r.rawStatus === 'organized')
    ));

    const performResolve = async () => {
      setIsResolvingId(candidateId);
      try {
        await onResolved(async () => {
          if (rows.length > 1) {
            const episodeList = Array.isArray(candidate?.episodes) ? candidate.episodes : [];
            const mediaType = toMetadataMediaType(candidate?.type || candidate?.media_type || mode, mode);
            const seasonVal = toOptionalNumber(effectiveSeason);
            const episodeVal = toOptionalNumber(effectiveEpisode);

            const resolutions = rows.map((r) => {
              const payload = {
                item_id: r.itemId,
                tmdb_id: candidate.tmdb_id || candidate.id,
                type: mediaType,
                media_type: mediaType,
                provider: candidate.provider || 'tmdb',
                is_adult: sessionMode === 'nsfw',
              };

              if (mediaType === MEDIA_TYPES.TV) {
                if (seasonVal != null) {
                  payload.season_number = seasonVal;
                } else if (isMatchedEpisode) {
                  payload.season_number = null;
                }

                if (episodeList.length > 0) {
                  payload.episode_number = episodeList;
                } else if (episodeVal != null) {
                  payload.episode_number = episodeVal;
                } else if (isMatchedEpisode) {
                  payload.episode_number = null;
                }
              }

              return payload;
            });

            await bulkResolveMutation.mutateAsync({
              resolutions,
            });
          } else {
            const payload = buildResolvePayload(rows[0], candidate, mode, effectiveSeason, effectiveEpisode, sessionMode);
            console.log('[DEBUG] resolveMutation: candidate:', candidate);
            console.log('[DEBUG] resolveMutation: built payload:', payload);
            await resolveMutation.mutateAsync(payload);
          }
        });
        toast(t('organizer.toasts.matchResolveSuccess'), 'success');
      } catch (error) {
        toast(error.message || t('organizer.toasts.matchResolveFailed'), 'danger');
      } finally {
        setIsResolvingId(null);
      }
    };

    const isBucket = mode === MEDIA_TYPES.TV && effectiveSeason !== null && effectiveEpisode === null && Array.isArray(candidate?.episodes) && candidate.episodes.length > 0;

    if (isBucket) {
      requestConfirm('bucket', 'swaya_skip_confirm_bucket', performResolve);
      return;
    }

    if (isMatchedEpisode) {
      if (mode === MEDIA_TYPES.TV && effectiveSeason === null && effectiveEpisode === null) {
        requestConfirm('tv', 'swaya_skip_confirm_tv', performResolve);
        return;
      }
      if (mode === MEDIA_TYPES.TV && effectiveSeason !== null && effectiveEpisode === null) {
        requestConfirm('season', 'swaya_skip_confirm_season', performResolve);
        return;
      }
    }

    await performResolve();
  };

  return {
    confirmState,
    setConfirmState,
    isResolvingId,
    handleResolve,
  };
}
