import { useCallback, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { Check, ChevronLeft, ChevronRight, Star, Plus, Minus } from 'lucide-react';
import { useUi } from '../../../providers/UiProvider';
import { resolveMediaImageUrl } from '../../../lib/imageUrls';
import {
  useRecommendationsQuery,
  useAddToWatchlistMutation,
  useRemoveFromWatchlistMutation,
} from '../../../queries/dashboardQueries';
import Button from '../../../ui/Button';
import Pill from '../../../ui/Pill';
import { useLibraryModeStore } from '../../../stores/useLibraryModeStore';
import { API_BASE } from '../../../lib/backend';

const ADULT_LABEL = '18+';

const SpotlightBanner = ({ item, watchlistIds, onWatchlist, onCardClick, T }) => {
  if (!item) return null;
  const imageUrl = resolveMediaImageUrl(item.backdrop_path, 'backdrop');
  const title = item.title || item.name;
  const isWatchlisted = watchlistIds.includes(item.id);
  const imdbRating = item.rating_imdb;
  const tmdbRating = item.rating_tmdb || item.vote_average;
  const ratingToDisplay = imdbRating || tmdbRating;
  const ratingSource = imdbRating ? 'imdb' : 'tmdb';
  const year = item.release_date ? new Date(item.release_date).getFullYear() : null;

  return (
    <div className="recommend-spotlight">
      {imageUrl && <img src={imageUrl} alt={title} className="recommend-spotlight-image" />}
      <div className="recommend-spotlight-gradient recommend-spotlight-gradient--side" />
      <div className="recommend-spotlight-gradient recommend-spotlight-gradient--bottom" />

      <div className="recommend-spotlight-copy">
        <h2 className="recommend-spotlight-title" onClick={() => onCardClick(item)}>{title}</h2>
        <div className="recommend-spotlight-meta">
          {ratingToDisplay ? (
            <span className={`recommend-spotlight-rating is-${ratingSource}`}>
              <Star size={14} fill="currentColor" /> {ratingToDisplay.toFixed(1)}
            </span>
          ) : null}
          {year ? <span className="recommend-spotlight-year">{year}</span> : null}
        </div>
        <p className="recommend-spotlight-overview">{item.overview}</p>
        <div className="recommend-spotlight-actions">
          <Button
            onClick={(e) => {
              e.stopPropagation();
              onWatchlist(item.id, item.title ? 'movie' : 'tv');
            }}
            className={`recommend-watchlist-btn ${isWatchlisted ? 'is-watchlisted' : ''}`}
            variant="secondary"
          >
            {isWatchlisted ? (
              <>
                <Check size={16} /> {T('dashboard.watchlist.added') || 'Watchlisted'}
              </>
            ) : (
              <>
                <Plus size={16} /> {T('dashboard.watchlist.add') || 'Watchlist'}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
};

SpotlightBanner.propTypes = {
  item: PropTypes.object,
  watchlistIds: PropTypes.array.isRequired,
  onWatchlist: PropTypes.func.isRequired,
  onCardClick: PropTypes.func.isRequired,
  T: PropTypes.func.isRequired,
};

const RecommendationCarousel = ({ title, items, watchlistIds, onWatchlist, onCardClick, T, isAdultCarousel = false }) => {
  const scrollRef = useRef(null);
  const [showLeft, setShowLeft] = useState(false);
  const [showRight, setShowRight] = useState(true);
  const sessionMode = useLibraryModeStore((state) => state.sessionMode);

  const updateArrows = useCallback(() => {
    const element = scrollRef.current;
    if (!element) return;
    setShowLeft(element.scrollLeft > 10);
    setShowRight(element.scrollLeft < element.scrollWidth - element.clientWidth - 10);
  }, []);

  if (!items?.length) {
    return null;
  }

  const scroll = (direction) => {
    const element = scrollRef.current;
    if (!element) return;
    const amount = element.clientWidth * 0.75;
    element.scrollBy({ left: direction === 'left' ? -amount : amount, behavior: 'smooth' });
  };

  return (
    <div className="recommend-carousel">
      <h3 className="recommend-carousel-title">{title}</h3>

      <div className="recommend-carousel-shell">
        {showLeft && (
          <button
            className="recommend-carousel-arrow is-left"
            onClick={() => scroll('left')}
          >
            <ChevronLeft size={24} />
          </button>
        )}

        {showRight && (
          <button
            className="recommend-carousel-arrow is-right"
            onClick={() => scroll('right')}
          >
            <ChevronRight size={24} />
          </button>
        )}

        <div
          ref={scrollRef}
          onScroll={updateArrows}
          className="recommend-carousel-track"
        >
          {items.map((item) => {
            const isWatchlisted = watchlistIds.includes(item.id);
            const rawPosterUrl = resolveMediaImageUrl(item.poster_path, 'poster');
            const shouldBlur = isAdultCarousel && sessionMode !== 'nsfw';
            const posterUrl = (shouldBlur && rawPosterUrl)
              ? `${API_BASE}/api/v1/media/image-proxy?url=${encodeURIComponent(rawPosterUrl)}&blur=true`
              : rawPosterUrl;
            const ratingImdb = item.rating_imdb;
            const ratingTmdb = item.rating_tmdb || item.vote_average;
            const hasRating = (ratingImdb && ratingImdb > 0) || (ratingTmdb && ratingTmdb > 0);

            const isTv = item.media_type === 'tv' || !item.title;
            let yearLabel = null;
            if (isTv) {
              const firstAirYear = item.first_air_date ? new Date(item.first_air_date).getFullYear() : null;
              const lastAirYear = item.last_air_date ? new Date(item.last_air_date).getFullYear() : null;
              const isEnded = item.release_status?.toLowerCase() === 'ended' || !!lastAirYear;
              if (firstAirYear) {
                yearLabel = isEnded && lastAirYear
                  ? `${firstAirYear} - ${lastAirYear}`
                  : `${firstAirYear} -`;
              }
            } else {
              yearLabel = item.release_date ? new Date(item.release_date).getFullYear() : null;
            }

            return (
              <div
                key={item.id}
                className="recommend-card"
                onClick={() => onCardClick(item)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    onCardClick(item);
                  }
                }}
              >
                <div className={`recommend-card-poster-shell ${shouldBlur ? 'is-blurred' : ''}`}>
                  {posterUrl && (
                    <img
                      key={posterUrl}
                      src={posterUrl}
                      alt={item.title || item.name}
                      className="recommend-card-image"
                    />
                  )}
                  {shouldBlur && (
                    <div className="recommend-card-blur-overlay">
                      <span className="settings-badge settings-badge--danger">{ADULT_LABEL}</span>
                    </div>
                  )}
                  <div className="recommend-card-overlay">
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        onWatchlist(item.id, item.title ? 'movie' : 'tv');
                      }}
                      className={`recommend-card-watchlist-btn ${isWatchlisted ? 'is-active' : ''}`}
                      variant="unstyled"
                    >
                      {isWatchlisted ? (
                        <>
                          <span className="watchlist-btn-state-default">
                            <Check size={12} strokeWidth={3} /> {T('dashboard.watchlist.added') || 'Watchlisted'}
                          </span>
                          <span className="watchlist-btn-state-hover">
                            <Minus size={12} strokeWidth={3} /> {T('dashboard.watchlist.remove_short') || 'Remove'}
                          </span>
                        </>
                      ) : (
                        <>
                          <Plus size={12} strokeWidth={3} /> {T('dashboard.watchlist.add_short') || 'Watchlist'}
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                <div className="recommend-card-meta">
                  <div className="recommend-card-name">{item.title || item.name}</div>
                  {(yearLabel || hasRating) ? (
                    <div className="recommend-card-secondary">
                      {yearLabel ? <span className="recommend-card-year">{yearLabel}</span> : null}
                      <div className="recommend-card-ratings">
                        {ratingImdb && ratingImdb > 0 ? (
                          <Pill variant="imdb">
                            <Star size={10} fill="currentColor" /> {ratingImdb.toFixed(1)}
                          </Pill>
                        ) : null}
                        {ratingTmdb && ratingTmdb > 0 ? (
                          <Pill variant="tmdb">
                            <Star size={10} fill="currentColor" /> {ratingTmdb.toFixed(1)}
                          </Pill>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

RecommendationCarousel.propTypes = {
  title: PropTypes.string.isRequired,
  items: PropTypes.array,
  watchlistIds: PropTypes.array.isRequired,
  onWatchlist: PropTypes.func.isRequired,
  onCardClick: PropTypes.func.isRequired,
  T: PropTypes.func.isRequired,
  isAdultCarousel: PropTypes.bool,
};

const RecommendationSkeleton = ({ showBanner = false }) => (
  <div className="recommend-skeleton">
    {showBanner && (
      <div className="recommend-skeleton-banner dashboard-widget-shell-skeleton" />
    )}
    <div className="recommend-skeleton-title dashboard-widget-shell-skeleton" />
    <div className="recommend-skeleton-row">
      {Array.from({ length: 6 }).map((_, idx) => (
        <div
          key={idx}
          className="recommend-skeleton-card dashboard-widget-shell-skeleton"
        />
      ))}
    </div>
  </div>
);

RecommendationSkeleton.propTypes = {
  showBanner: PropTypes.bool,
};

const RecommendationsWidget = ({ language, T }) => {
  const { toast } = useUi();
  const navigate = useNavigate();
  const { data: recommendations = {}, isLoading } = useRecommendationsQuery(language);
  const addToWatchlist = useAddToWatchlistMutation();
  const removeFromWatchlist = useRemoveFromWatchlistMutation();

  const watchlistIds = recommendations.watchlist_item_ids || [];

  const handleWatchlist = async (tmdbId, type) => {
    const isWatchlisted = watchlistIds.includes(tmdbId);
    try {
      if (isWatchlisted) {
        await removeFromWatchlist.mutateAsync(tmdbId);
      } else {
        await addToWatchlist.mutateAsync({ tmdbId, type });
      }
    } catch (error) {
      console.error(error);
      toast(T(isWatchlisted ? 'dashboard.watchlist.remove_failed' : 'dashboard.watchlist.add_failed') || 'Action failed', 'danger');
    }
  };

  const handleCardClick = (item) => {
    const type = item.media_type || (item.title ? 'movie' : 'tv');
    const idToUse = item.in_library ? item.media_item_id : `tmdb_${item.id}`;
    navigate(`/library/${type}/${idToUse}`, { state: { allowAdult: true } });
  };

  return (
    <>
      {isLoading && <RecommendationSkeleton showBanner />}

      {!isLoading && recommendations?.trending?.length > 0 && (
        <SpotlightBanner
          item={recommendations.trending[0]}
          watchlistIds={watchlistIds}
          onWatchlist={handleWatchlist}
          onCardClick={handleCardClick}
          T={T}
        />
      )}

      {isLoading && <RecommendationSkeleton />}

      {!isLoading && recommendations?.discover_movies?.length > 0 && (
        <RecommendationCarousel
          title={T('dashboard.recommendations.discover_movies') || 'Discover Movies'}
          items={recommendations.discover_movies}
          watchlistIds={watchlistIds}
          onWatchlist={handleWatchlist}
          onCardClick={handleCardClick}
          T={T}
        />
      )}

      {!isLoading && recommendations?.discover_tv?.length > 0 && (
        <RecommendationCarousel
          title={T('dashboard.recommendations.discover_series') || 'Discover Series'}
          items={recommendations.discover_tv}
          watchlistIds={watchlistIds}
          onWatchlist={handleWatchlist}
          onCardClick={handleCardClick}
          T={T}
        />
      )}

      {!isLoading && recommendations?.discover_adult?.length > 0 && (
        <RecommendationCarousel
          title={T('dashboard.recommendations.discover_adult') || 'Discover Adult Movies'}
          items={recommendations.discover_adult}
          watchlistIds={watchlistIds}
          onWatchlist={handleWatchlist}
          onCardClick={handleCardClick}
          T={T}
          isAdultCarousel={true}
        />
      )}
    </>
  );
};

RecommendationsWidget.propTypes = {
  language: PropTypes.string,
  T: PropTypes.func.isRequired,
};

export default RecommendationsWidget;
