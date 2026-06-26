import { useState, useEffect } from 'react';
import { Clapperboard } from 'lucide-react';
import Badge from '../../../ui/Badge';
import MediaCard from '../../../ui/MediaCard';
import MetaRow from '../../../ui/MetaRow';
import { buildTmdbImageUrl, TMDB_IMAGE_SIZES } from '@/lib/imageUrls';
import { API_BASE } from '@/lib/backend';

const getImageUrl = (path, size = TMDB_IMAGE_SIZES.posterThumb) => {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('//')) {
    const url = path.startsWith('//') ? `https:${path}` : path;
    return `${API_BASE}/api/v1/media/image-proxy?url=${encodeURIComponent(url)}`;
  }
  return buildTmdbImageUrl(path, size);
};

export default function MatchSeasonCard({
  seasonEntry,
  isBrowserLoading,
  onSelect,
  isActive = false,
  t,
}) {
  const posterUrl = getImageUrl(seasonEntry.poster_path, TMDB_IMAGE_SIZES.posterThumb);
  const [posterError, setPosterError] = useState(false);

  useEffect(() => {
    setPosterError(false);
  }, [posterUrl]);

  return (
    <div
      key={`season-${seasonEntry.season_number}`}
      className="organizer-match-modal__browser-card"
    >
      <button
        type="button"
        className="organizer-match-modal__browser-card-image organizer-match-modal__browser-card-image--poster organizer-match-modal__browser-card--clickable"
        onClick={() => onSelect(seasonEntry)}
        disabled={isBrowserLoading}
      >
        <MediaCard>
          {posterUrl && !posterError ? (
            <img
              src={posterUrl}
              alt=""
              className="organizer-match-modal__poster-image"
              onError={() => setPosterError(true)}
            />
          ) : (
            <div className="organizer-match-modal__poster-placeholder">
              <Clapperboard size={18} />
            </div>
          )}
          {isActive ? (
            <Badge family="status" variant="overlay" tone="accent" className="ui-status-badge ui-status-badge--accent ui-status-badge--overlay">
              {t('organizer.details.matchModal.current')}
            </Badge>
          ) : null}
        </MediaCard>
      </button>
      <div className="organizer-match-modal__browser-card-copy">
        <strong className="organizer-match-modal__browser-card-title">
          {seasonEntry.name || t('organizer.details.matchModal.seasonNum').replace('{number}', seasonEntry.season_number)}
        </strong>
        <MetaRow
          className="organizer-match-modal__browser-card-meta"
          items={[
            seasonEntry.episode_count ? `${seasonEntry.episode_count} eps` : null,
          ]}
        />
      </div>
    </div>
  );
}
