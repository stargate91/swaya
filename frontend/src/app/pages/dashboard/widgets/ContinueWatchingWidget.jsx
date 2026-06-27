import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Play, X } from 'lucide-react';
import { useContinueWatchingQuery } from '../../../queries';
import { usePlayMediaMutation, useResetProgressMutation } from '../../../queries';
import { resolveMediaImageUrl } from '../../../lib/imageUrls';

const normalizeEpisodeNumbers = (episodeNumber) => {
  if (Array.isArray(episodeNumber)) {
    return episodeNumber;
  }

  if (typeof episodeNumber === 'string') {
    const trimmed = episodeNumber.trim();
    if (!trimmed) {
      return [];
    }

    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        const parsed = JSON.parse(trimmed);
        return Array.isArray(parsed) ? parsed : [parsed];
      } catch {
        return trimmed
          .slice(1, -1)
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean);
      }
    }

    if (trimmed.includes(',')) {
      return trimmed.split(',').map((value) => value.trim()).filter(Boolean);
    }
  }

  return [episodeNumber];
};

const formatEpisodeCode = (seasonNumber, episodeNumber) => {
  if (!seasonNumber || !episodeNumber) {
    return null;
  }

  const episodeNumbers = normalizeEpisodeNumbers(episodeNumber);
  const normalizedEpisodes = [...new Set(
    episodeNumbers
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value) && value > 0)
  )].sort((a, b) => a - b);

  if (!normalizedEpisodes.length) {
    return null;
  }

  const ranges = [];
  let rangeStart = normalizedEpisodes[0];
  let rangeEnd = normalizedEpisodes[0];

  for (let index = 1; index < normalizedEpisodes.length; index += 1) {
    const current = normalizedEpisodes[index];
    if (current === rangeEnd + 1) {
      rangeEnd = current;
      continue;
    }
    ranges.push([rangeStart, rangeEnd]);
    rangeStart = current;
    rangeEnd = current;
  }
  ranges.push([rangeStart, rangeEnd]);

  const episodeCodes = ranges
    .map(([start, end]) => (
      start === end
        ? `E${String(start).padStart(2, '0')}`
        : `E${String(start).padStart(2, '0')}-E${String(end).padStart(2, '0')}`
    ))
    .join(',');

  return `S${String(seasonNumber).padStart(2, '0')}${episodeCodes}`;
};

const ContinueWatchingWidget = ({ T }) => {
  const { data: items = [], isLoading } = useContinueWatchingQuery();
  const playMutation = usePlayMediaMutation();
  const resetProgressMutation = useResetProgressMutation();

  if (isLoading || !items.length) {
    return null;
  }

  return (
    <div className="continue-watching-widget">
      <div className="continue-watching-header">
        <Play size={20} className="continue-watching-header__icon" fill="var(--color-accent-blue)" color="var(--color-accent-blue)" />
        {T('dashboard.continue_watching.title') || 'Continue Watching'}
      </div>
      <div className="continue-watching-row custom-scrollbar">
        {items.map((item) => {
          const progressPercent = Math.min(100, (item.resume_position / item.duration) * 100);
          const episodeCode = formatEpisodeCode(item.season_number, item.episode_number);
          const minutesLeft = Math.max(0, Math.floor(item.duration / 60) - Math.floor(item.resume_position / 60));
          const episodeMeta = episodeCode ? `${episodeCode} - ${item.episode_title || item.title}` : null;
          const imagePath = item.still_path || item.backdrop_path;
          const resolvedImageUrl = resolveMediaImageUrl(imagePath, item.still_path ? 'still' : 'backdrop');

          return (
            <div
              key={`cw-${item.id}`}
              className="continue-watching-card"
              onClick={() => {
                if (item.type === 'episode' || item.type === 'movie') {
                  playMutation.mutate(item.id);
                }
              }}
            >
              <button
                className="continue-watching-remove"
                onClick={async (e) => {
                  e.stopPropagation();
                  resetProgressMutation.mutate(item.id);
                }}
                title={T('dashboard.continue_watching.remove') || 'Remove progress'}
              >
                <X size={14} color="var(--color-text-primary)" />
              </button>

              {resolvedImageUrl ? (
                <img
                  src={resolvedImageUrl}
                  alt=""
                  className="continue-watching-image"
                />
              ) : (
                <div className="continue-watching-fallback" />
              )}

              <div className="continue-watching-overlay" />

              <div className="continue-watching-play-shell">
                <div className="continue-watching-play-pill">
                  <Play fill="var(--color-text-primary)" color="var(--color-text-primary)" size={24} />
                </div>
              </div>

              <div className="continue-watching-progress-track">
                <svg viewBox="0 0 100 4" preserveAspectRatio="none" className="continue-watching-progress-svg">
                  <rect x="0" y="0" width="100" height="4" className="continue-watching-progress-bg" />
                  <rect x="0" y="0" width={progressPercent} height="4" className="continue-watching-progress-fill" />
                </svg>
              </div>

              <div className="continue-watching-copy">
                <div className="continue-watching-title">
                  {item.series_title || item.title}
                </div>
                <div className={`continue-watching-meta${episodeMeta ? ' continue-watching-meta--has-episode' : ''}`}>
                  <span className="continue-watching-meta-default">
                    {T('dashboard.continue_watching.minutes_left', { minutes: minutesLeft }) || `${minutesLeft}m left`}
                  </span>
                  {episodeMeta ? (
                    <span className="continue-watching-meta-episode">
                      {episodeMeta}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

ContinueWatchingWidget.propTypes = {
  T: PropTypes.func.isRequired,
};

export default ContinueWatchingWidget;
