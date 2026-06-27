import { useCallback, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { Check, ChevronLeft, ChevronRight, Star } from 'lucide-react';
import { useUi } from '../../../providers/UiProvider';
import { resolveMediaImageUrl } from '../../../lib/imageUrls';
import {
  useRecommendationsQuery,
  useAddToWatchlistMutation,
  useRemoveFromWatchlistMutation,
} from '../../../queries/dashboardQueries';
import Button from '../../../ui/Button';
import DashboardWidgetShell from './DashboardWidgetShell';

const SpotlightBanner = ({ item, watchlistIds, onWatchlist, onCardClick, T }) => {
  if (!item) return null;
  const imageUrl = resolveMediaImageUrl(item.backdrop_path, 'backdrop');
  const title = item.title || item.name;
  const isWatchlisted = watchlistIds.includes(item.id);
  const rating = item.vote_average;
  const year = item.release_date ? new Date(item.release_date).getFullYear() : null;

  return (
    <div className="recommend-spotlight" onClick={() => onCardClick(item)}>
      {imageUrl && <img src={imageUrl} alt={title} className="recommend-spotlight-image" />}
      <div className="recommend-spotlight-gradient recommend-spotlight-gradient--side" />
      <div className="recommend-spotlight-gradient recommend-spotlight-gradient--bottom" />

      <div className="recommend-spotlight-copy">
        <h2 className="recommend-spotlight-title">{title}</h2>
        <div className="recommend-spotlight-meta">
          {rating ? (
            <span className="recommend-spotlight-rating is-tmdb">
              <Star size={14} fill="currentColor" /> {rating.toFixed(1)}
            </span>
          ) : null}
          {year ? <span className="recommend-spotlight-year">{year}</span> : null}
        </div>
        <p className="recommend-spotlight-overview">{item.overview}</p>
        <div className="recommend-spotlight-actions" style={{ display: 'flex', gap: '12px' }}>
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
                <span>+ </span> {T('dashboard.watchlist.add') || 'Watchlist'}
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

const RecommendationCarousel = ({ title, items, watchlistIds, onWatchlist, onCardClick, T }) => {
  const scrollRef = useRef(null);
  const [showLeft, setShowLeft] = useState(false);
  const [showRight, setShowRight] = useState(true);

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
          <Button
            className="recommend-carousel-arrow is-left"
            onClick={() => scroll('left')}
            variant="secondary-neutral"
          >
            <ChevronLeft size={22} />
          </Button>
        )}

        {showRight && (
          <Button
            className="recommend-carousel-arrow is-right"
            onClick={() => scroll('right')}
            variant="secondary-neutral"
          >
            <ChevronRight size={22} />
          </Button>
        )}

        <div
          ref={scrollRef}
          onScroll={updateArrows}
          className="recommend-carousel-track custom-scrollbar"
        >
          {items.map((item) => {
            const isWatchlisted = watchlistIds.includes(item.id);
            const posterUrl = resolveMediaImageUrl(item.poster_path, 'poster');
            const year = item.release_date ? new Date(item.release_date).getFullYear() : null;
            const rating = item.vote_average;
            return (
              <div
                key={item.id}
                className="recommend-card"
                onClick={() => onCardClick(item)}
              >
                <div className="recommend-card-poster-shell">
                  {posterUrl && <img src={posterUrl} alt={item.title || item.name} className="recommend-card-image" />}
                  <div className="recommend-card-overlay">
                    <Button
                      onClick={(e) => {
                        e.stopPropagation();
                        onWatchlist(item.id, item.title ? 'movie' : 'tv');
                      }}
                      className={`ui-card-action-pill ${isWatchlisted ? 'is-active' : ''}`}
                      variant="unstyled"
                    >
                      {isWatchlisted ? (
                        <>
                          <Check size={14} /> {T('dashboard.watchlist.added') || 'Watchlisted'}
                        </>
                      ) : (
                        `+ ${T('dashboard.watchlist.add_short') || 'Watchlist'}`
                      )}
                    </Button>
                  </div>
                </div>

                <div className="recommend-card-meta">
                  <div className="recommend-card-name">{item.title || item.name}</div>
                  {(year || rating) ? (
                    <div className="recommend-card-secondary">
                      {year ? <span className="recommend-card-year">{year}</span> : null}
                      {rating ? (
                        <span className="library-card-rating-pill is-inline is-tmdb">
                          <Star size={10} fill="currentColor" /> {rating.toFixed(1)}
                        </span>
                      ) : null}
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
    const type = item.title ? 'movie' : 'tv';
    navigate(`/library/${type}/${item.id}`);
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
    </>
  );
};

RecommendationsWidget.propTypes = {
  language: PropTypes.string,
  T: PropTypes.func.isRequired,
};

export default RecommendationsWidget;
