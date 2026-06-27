import { useRef, useEffect, useState } from 'react';
import { Clapperboard, Check } from 'lucide-react';
import Badge from '../../../ui/Badge';
import MediaCard from '../../../ui/MediaCard';
import MetaRow from '../../../ui/MetaRow';
import Button from '../../../ui/Button';
import { buildTmdbImageUrl, TMDB_IMAGE_SIZES } from '@/lib/imageUrls';
import { API_BASE } from '@/lib/backend';

const getImageUrl = (path, size = TMDB_IMAGE_SIZES.thumbnail) => {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('//')) {
    const url = path.startsWith('//') ? `https:${path}` : path;
    return `${API_BASE}/api/v1/media/image-proxy?url=${encodeURIComponent(url)}`;
  }
  return buildTmdbImageUrl(path, size);
};

export default function MatchEpisodeCard({
  episodeEntry,
  isBucketed,
  isDisabled,
  onSelect,
  onToggle,
  isActive = false,
  isHighlighted = false,
  t,
}) {
  const stillUrl = getImageUrl(episodeEntry.still_path, TMDB_IMAGE_SIZES.thumbnail);
  const cardRef = useRef();
  const [prevStillUrl, setPrevStillUrl] = useState(stillUrl);
  const [stillError, setStillError] = useState(false);

  if (prevStillUrl !== stillUrl) {
    setPrevStillUrl(stillUrl);
    setStillError(false);
  }

  useEffect(() => {
    if (isHighlighted && cardRef.current) {
      // Small timeout to allow render/layout to stabilize before scrolling
      const timer = setTimeout(() => {
        cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [isHighlighted]);

  return (
    <div
      ref={cardRef}
      key={`episode-${episodeEntry.id || episodeEntry.episode_number}`}
      className={`organizer-match-modal__browser-card organizer-match-modal__browser-card--episode${isBucketed ? ' is-selected' : ''}${isHighlighted ? ' is-highlighted' : ''}`.trim()}
    >
      <button
        type="button"
        className="organizer-match-modal__browser-card-image organizer-match-modal__browser-card-image--still organizer-match-modal__browser-card--clickable"
        onClick={() => onToggle(episodeEntry.episode_number)}
      >
        <MediaCard>
          {stillUrl && !stillError ? (
            <img
              src={stillUrl}
              alt=""
              className="organizer-match-modal__poster-image"
              onError={() => setStillError(true)}
            />
          ) : (
            <div className="organizer-match-modal__poster-placeholder">
              <Clapperboard size={18} />
            </div>
          )}
          {isBucketed ? (
            <div className="organizer-match-modal__browser-card-bucket-indicator">
              <Check size={12} strokeWidth={3} />
            </div>
          ) : null}
          {isActive ? (
            <Badge family="status" variant="overlay" tone="accent" className="ui-status-badge ui-status-badge--accent ui-status-badge--overlay">
              {t('organizer.details.matchModal.current')}
            </Badge>
          ) : null}
        </MediaCard>
      </button>
      <div className="organizer-match-modal__browser-card-copy">
        <strong className="organizer-match-modal__browser-card-title">
          {episodeEntry.name || t('organizer.details.matchModal.episodeNum').replace('{number}', episodeEntry.episode_number)}
        </strong>
        <div className="organizer-match-modal__browser-card-meta-row">
          <MetaRow
            className="organizer-match-modal__browser-card-meta"
            items={[
              `E${episodeEntry.episode_number}`,
              episodeEntry.air_date ? String(episodeEntry.air_date).slice(0, 10) : null,
            ]}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="organizer-match-modal__select-button"
            onClick={() => onSelect(episodeEntry)}
            disabled={isDisabled}
          >
            {t('organizer.details.matchModal.select')}
          </Button>
        </div>
      </div>
    </div>
  );
}
