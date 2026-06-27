import { useState } from 'react';
import { Clapperboard } from 'lucide-react';
import Badge from '@/ui/Badge';
import MetaRow from '@/ui/MetaRow';
import PosterCard from '@/ui/PosterCard';
import BackdropCard from '@/ui/BackdropCard';
import { resolveMediaImageUrl } from '@/lib/imageUrls';
import { MEDIA_TYPES, isTvLikeMediaType, toMetadataMediaType } from '@/lib/mediaTypes';
import { API_BASE } from '@/lib/backend';

const getDisplayTitle = (candidate, mediaType, t) => (
  candidate?.title
  || candidate?.name
  || candidate?.original_title
  || candidate?.original_name
  || (mediaType === MEDIA_TYPES.TV ? t('organizer.details.matchModal.unknownTv') : t('organizer.details.matchModal.unknownMovie'))
);

const getDisplayYear = (candidate, mediaType) => {
  const rawDate = mediaType === MEDIA_TYPES.TV
    ? candidate?.first_air_date
    : candidate?.release_date;
  return rawDate ? String(rawDate).slice(0, 4) : null;
};

const getImageUrl = (path, mediaType) => {
  if (!path) return '';
  const pathStr = String(path);

  if (pathStr.startsWith(API_BASE) || pathStr.startsWith('http://localhost') || pathStr.startsWith('http://127.0.0.1')) {
    return pathStr;
  }

  if (pathStr.startsWith('/media/') || pathStr.startsWith('media/')) {
    return resolveMediaImageUrl(path, mediaType === 'scene' ? 'backdrop' : 'poster', API_BASE);
  }

  if (pathStr.startsWith('http://') || pathStr.startsWith('https://') || pathStr.startsWith('//')) {
    const url = pathStr.startsWith('//') ? `https:${pathStr}` : pathStr;
    return `${API_BASE}/api/v1/media/image-proxy?url=${encodeURIComponent(url)}`;
  }

  return resolveMediaImageUrl(path, mediaType === 'scene' ? 'backdrop' : 'poster', API_BASE);
};

export default function MatchCandidateCard({
  candidate,
  sourceLabel,
  variant = 'list',
  mode,
  isResolvingId,
  isBrowserLoading,
  onSelect,
  t,
  rowStatus,
}) {
  const mediaType = mode === 'scene' ? 'scene' : toMetadataMediaType(candidate.type || candidate.media_type, mode);
  const displayTitle = getDisplayTitle(candidate, mediaType, t);
  const displayYear = getDisplayYear(candidate, mediaType);
  const candidateId = candidate.tmdb_id || candidate.id;
  const posterUrl = getImageUrl(candidate.poster_path, mediaType);
  const isDisabled = isResolvingId === candidateId || isBrowserLoading;
  const [prevPosterUrl, setPrevPosterUrl] = useState(posterUrl);
  const [imageError, setImageError] = useState(false);

  if (prevPosterUrl !== posterUrl) {
    setPrevPosterUrl(posterUrl);
    setImageError(false);
  }

  if (variant === 'poster') {
    if (mediaType === 'scene') {
      return (
        <BackdropCard
          key={`${sourceLabel}-${candidateId}`}
          className={`organizer-match-modal__poster-card is-scene${candidate.is_active ? ' is-active' : ''}`}
          imageUrl={posterUrl}
          onClick={() => onSelect(candidate)}
          disabled={isDisabled}
          infoLeft={displayTitle}
          infoRight={displayYear}
        >
          {candidate.is_active && (
            <div className="organizer-match-modal__candidate-badge-wrapper">
              {rowStatus === 'uncertain' ? (
                <Badge family="status" variant="overlay" tone="warning" className="ui-status-badge ui-status-badge--warning ui-status-badge--overlay">
                  {t('organizer.status.uncertain')}
                </Badge>
              ) : (
                <Badge family="status" variant="overlay" tone="accent" className="ui-status-badge ui-status-badge--accent ui-status-badge--overlay">
                  {t('organizer.details.matchModal.current')}
                </Badge>
              )}
            </div>
          )}
        </BackdropCard>
      );
    }

    return (
      <PosterCard
        key={`${sourceLabel}-${candidateId}`}
        className={`organizer-match-modal__poster-card${mediaType === 'scene' ? ' is-scene' : ''}`}
        active={candidate.is_active}
        imageUrl={posterUrl}
        icon={Clapperboard}
        onClick={() => onSelect(candidate)}
        disabled={isDisabled}
        title={displayTitle}
        subtitle={
          <MetaRow
            className="organizer-match-modal__poster-card-meta"
            items={[
              displayYear,
              mediaType === 'scene' ? t('organizer.details.matchModal.scene') : (isTvLikeMediaType(mediaType) ? t('organizer.details.matchModal.tv') : t('organizer.details.matchModal.movie')),
            ]}
          />
        }
        badge={
          candidate.is_active ? (
            rowStatus === 'uncertain' ? (
              <Badge family="status" variant="overlay" tone="warning" className="ui-status-badge ui-status-badge--warning ui-status-badge--overlay">
                {t('organizer.status.uncertain')}
              </Badge>
            ) : (
              <Badge family="status" variant="overlay" tone="accent" className="ui-status-badge ui-status-badge--accent ui-status-badge--overlay">
                {t('organizer.details.matchModal.current')}
              </Badge>
            )
          ) : null
        }
      />
    );
  }

  return (
    <button
      key={`${sourceLabel}-${candidateId}`}
      type="button"
      className={`organizer-match-modal__result-card${candidate.is_active ? ' is-active' : ''}${mediaType === 'scene' ? ' is-scene' : ''}`.trim()}
      onClick={() => onSelect(candidate)}
      disabled={isDisabled}
    >
      <div className="organizer-match-modal__poster">
        {posterUrl && !imageError ? (
          <img
            src={posterUrl}
            alt=""
            className="organizer-match-modal__poster-image"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="organizer-match-modal__poster-placeholder">
            <Clapperboard size={18} />
          </div>
        )}
      </div>
      <div className="organizer-match-modal__result-copy">
        <div className="organizer-match-modal__result-topline">
          <strong className="organizer-match-modal__result-title">{displayTitle}</strong>
          {candidate.is_active ? (
            rowStatus === 'uncertain' ? (
              <Badge family="status" tone="warning" variant="inline" className="ui-status-badge ui-status-badge--warning ui-status-badge--inline">
                {t('organizer.status.uncertain')}
              </Badge>
            ) : (
              <Badge family="status" tone="accent" variant="inline" className="ui-status-badge ui-status-badge--accent ui-status-badge--inline">
                {t('organizer.details.matchModal.current')}
              </Badge>
            )
          ) : null}
        </div>
        <MetaRow
          className="organizer-match-modal__result-meta"
          items={[
            mediaType === 'scene' ? t('organizer.details.matchModal.scene') : (isTvLikeMediaType(mediaType) ? t('organizer.details.matchModal.tv') : t('organizer.details.matchModal.movie')),
            displayYear,
          ]}
        />
        {candidate.overview ? (
          <p className="organizer-match-modal__result-overview">{candidate.overview}</p>
        ) : null}
        {isResolvingId === candidateId && (
          <span className="organizer-match-modal__result-action">
            {t('organizer.details.matchModal.applying')}
          </span>
        )}
      </div>
    </button>
  );
}
