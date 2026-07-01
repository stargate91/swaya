import { useState, useRef, useEffect, useMemo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, ChevronLeft, Check, Eye, Play, Clapperboard, Calendar, Tv, Star, Flame, Trash2 } from 'lucide-react';
import IconButton from '@/ui/IconButton';
import Pill from '@/ui/Pill';
import { resolveMediaImageUrl } from '@/lib/imageUrls';
import { formatEpisodeNumber, formatTime } from '../../../utils/detailUtils';
import { useMediaDetailContext } from '../MediaDetailContext';
import { useTranslation as useLangTranslation } from '@/providers/LanguageContext';
import api from '@/lib/api';
import './SeasonsPanel.css';

const LPAR = '(';
const RPAR = ')';
const EPISODES_BATCH_SIZE = 20;

export default function SeasonsPanel() {
  const { state, mutations, t } = useMediaDetailContext();
  const { locale } = useLangTranslation();
  const metadataLanguage = locale === 'en' ? 'en-US' : locale;
  const { item, cleanId, nextEpisodeInfo } = state;
  const { updateStatusMutation, playMutation, bulkUpdateWatchedMutation, addPeakMutation, deletePeakMutation } = mutations;
  const queryClient = useQueryClient();

  const seasonsList = useMemo(() => item.seasons || [], [item.seasons]);
  const seasonsCount = seasonsList.length;
  const initialSeasonNumber = nextEpisodeInfo?.seasonNumber ?? seasonsList[0]?.season_number ?? 1;
  const initialExpandedEpisodes = nextEpisodeInfo?.episode?.id
    ? { [nextEpisodeInfo.episode.id]: true }
    : {};
  const initialTargetSeason = seasonsList.find((season) => season.season_number === initialSeasonNumber);
  const initialTargetEpisodeIndex = nextEpisodeInfo?.episode?.id
    ? initialTargetSeason?.episodes?.findIndex((episode) => episode.id === nextEpisodeInfo.episode.id) ?? -1
    : -1;
  const initialVisibleEpisodesCount = initialTargetEpisodeIndex >= 0
    ? Math.max(EPISODES_BATCH_SIZE, initialTargetEpisodeIndex + 1)
    : EPISODES_BATCH_SIZE;

  const [selectedSeasonNumber, setSelectedSeasonNumber] = useState(initialSeasonNumber);
  const [expandedEpisodes, setExpandedEpisodes] = useState(initialExpandedEpisodes);
  const [visibleEpisodesCount, setVisibleEpisodesCount] = useState(initialVisibleEpisodesCount);
  const [prevSelectedSeasonNumber, setPrevSelectedSeasonNumber] = useState(selectedSeasonNumber);

  const scrollContainerRef = useRef(null);
  const loadMoreTriggerRef = useRef(null);

  if (selectedSeasonNumber !== prevSelectedSeasonNumber) {
    setPrevSelectedSeasonNumber(selectedSeasonNumber);

    const targetSeason = seasonsList.find((season) => season.season_number === selectedSeasonNumber);
    const targetEpisodeIndex = selectedSeasonNumber === nextEpisodeInfo?.seasonNumber
      ? targetSeason?.episodes?.findIndex((episode) => episode.id === nextEpisodeInfo?.episode?.id) ?? -1
      : -1;
    setVisibleEpisodesCount(
      targetEpisodeIndex >= 0
        ? Math.max(EPISODES_BATCH_SIZE, targetEpisodeIndex + 1)
        : EPISODES_BATCH_SIZE
    );
  }

  // Automatically scroll the selected season card into view without affecting outer scroll containers
  useEffect(() => {
    const activeBtn = scrollContainerRef.current?.querySelector('.season-poster-card.is-active');
    const container = scrollContainerRef.current;
    if (activeBtn && container) {
      // Center the active card inside the carousel container
      const scrollLeftOffset = activeBtn.offsetLeft - (container.clientWidth / 2) + (activeBtn.clientWidth / 2);
      container.scrollTo({
        left: scrollLeftOffset,
        behavior: 'smooth',
      });
    }
  }, [selectedSeasonNumber]);

  const getPosterUrl = (path) => {
    if (!path) return '';
    return resolveMediaImageUrl(path, 'poster');
  };

  const getStillUrl = (path) => {
    if (!path) return '';
    return resolveMediaImageUrl(path, 'still');
  };

  const selectedSeasonIndex = seasonsList.findIndex((s) => s.season_number === selectedSeasonNumber);

  const handlePrevSeason = () => {
    if (selectedSeasonIndex > 0) {
      setSelectedSeasonNumber(seasonsList[selectedSeasonIndex - 1].season_number);
    }
  };

  const handleNextSeason = () => {
    if (selectedSeasonIndex < seasonsCount - 1) {
      setSelectedSeasonNumber(seasonsList[selectedSeasonIndex + 1].season_number);
    }
  };

  const toggleEpisodeOverview = (episodeId) => {
    setExpandedEpisodes((prev) => ({
      ...prev,
      [episodeId]: !prev[episodeId],
    }));
  };

  // Find active season
  const activeSeason = seasonsList.find((s) => s.season_number === selectedSeasonNumber) || seasonsList[0];

  useEffect(() => {
    if (!item?.progressive_seasons || !activeSeason) return;
    if (activeSeason.episodes_complete !== false) return;

    let cancelled = false;
    const run = async () => {
      try {
        const seasonPayload = await api.library.getTvSeasonDetail(cleanId, activeSeason.season_number);
        if (cancelled) return;
        queryClient.setQueryData(['library-tv-detail', cleanId, metadataLanguage], (current) => {
          if (!current || !seasonPayload) return current;
          const existingSeasons = Array.isArray(current.seasons) ? current.seasons : [];
          const nextMap = new Map(existingSeasons.map((season) => [Number(season?.season_number), season]));
          nextMap.set(Number(seasonPayload.season_number), {
            ...(nextMap.get(Number(seasonPayload.season_number)) || {}),
            ...seasonPayload,
          });
          return {
            ...current,
            seasons: Array.from(nextMap.values()).sort((a, b) => Number(a?.season_number || 0) - Number(b?.season_number || 0)),
          };
        });
      } catch {
        // Ignore season prefetch failures here; the shell stays usable.
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [activeSeason, cleanId, item?.in_library, item?.progressive_seasons, queryClient, metadataLanguage]);

  const totalEpisodesCount = activeSeason?.episode_count ?? 0;

  const localEpisodesCount = activeSeason?.local_episode_count ?? 0;

  const isSeasonWatched = activeSeason?.episodes
    ? activeSeason.episodes.length > 0 && activeSeason.episodes.every((ep) => ep.is_watched)
    : false;

  const isSeasonPartiallyWatched = activeSeason?.episodes
    ? activeSeason.episodes.length > 0 && activeSeason.episodes.some((ep) => ep.is_watched) && !isSeasonWatched
    : false;

  const isSeasonWatchedWithDate = activeSeason?.episodes
    ? activeSeason.episodes.length > 0 && activeSeason.episodes.every((ep) => ep.last_watched_at)
    : false;

  const visibleEpisodes = activeSeason?.episodes?.slice(0, visibleEpisodesCount) || [];
  const hasMoreEpisodes = visibleEpisodes.length < (activeSeason?.episodes?.length || 0);

  useEffect(() => {
    const trigger = loadMoreTriggerRef.current;
    if (!trigger || !hasMoreEpisodes) return undefined;

    const scrollRoot = trigger.closest('.media-detail-page__side-panel-content');
    const observer = new IntersectionObserver(
      (entries) => {
        const firstEntry = entries[0];
        if (!firstEntry?.isIntersecting) return;

        setVisibleEpisodesCount((prev) => (
          Math.min(prev + EPISODES_BATCH_SIZE, activeSeason?.episodes?.length || prev)
        ));
      },
      {
        root: scrollRoot || null,
        rootMargin: '0px 0px 960px 0px',
        threshold: 0.01,
      }
    );

    observer.observe(trigger);
    return () => observer.disconnect();
  }, [activeSeason?.episodes?.length, hasMoreEpisodes, visibleEpisodes.length]);

  if (!activeSeason) {
    return (
      <div className="seasons-panel__empty">
        {t('library.details.noSeasonsFound') || 'No seasons found.'}
      </div>
    );
  }

  const handleSeasonWatchedToggle = (e) => {
    e.stopPropagation();
    if (!activeSeason || !activeSeason.episodes || activeSeason.episodes.length === 0) return;
    const episodeIds = activeSeason.episodes.map((ep) => ep.id);
    bulkUpdateWatchedMutation.mutate({
      itemIds: episodeIds,
      isWatched: !isSeasonWatched,
      tvId: cleanId,
    });
  };

  return (
    <div className="seasons-panel">
      {/* Title with navigation arrows */}
      <div className="seasons-panel__header">
        <h4 className="details-panel__section-title">
          {t('library.details.seasons') || 'Seasons'}
        </h4>
        <div className="seasons-panel__nav-arrows">
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={handlePrevSeason}
            disabled={selectedSeasonIndex <= 0}
            className="seasons-panel__nav-arrow-btn"
            title="Previous Season"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            onMouseDown={(e) => e.preventDefault()}
            onClick={handleNextSeason}
            disabled={selectedSeasonIndex >= seasonsCount - 1}
            className="seasons-panel__nav-arrow-btn"
            title="Next Season"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Seasons Posters Carousel (no absolute scroll buttons) */}
      <div className="seasons-carousel-wrapper">
        <div className="seasons-carousel" ref={scrollContainerRef}>
          {seasonsList.map((season) => {
            const isActive = season.season_number === selectedSeasonNumber;
            const posterUrl = getPosterUrl(season.poster_path);
            const title = season.title || `Season ${season.season_number}`;

            return (
              <button
                key={season.season_number}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                className={`season-poster-card ${isActive ? 'is-active' : ''}`}
                onClick={() => setSelectedSeasonNumber(season.season_number)}
              >
                <div className="season-poster-card__image-wrapper">
                  {posterUrl ? (
                    <img src={posterUrl} alt={title} className="season-poster-card__image" />
                  ) : (
                    <div className="season-poster-card__placeholder">
                      <Clapperboard size={32} />
                    </div>
                  )}
                </div>
                <span className="season-poster-card__title" title={title}>
                  {title}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Selected Season Header / Details */}
      <div className="active-season-info">
        <div className="active-season-info__header">
          <div>
            <h3 className="active-season-info__title">
              {activeSeason.title || `Season ${activeSeason.season_number}`}
            </h3>
            <div className="active-season-info__meta">
              {activeSeason.air_date && (
                <span className="active-season-info__meta-date">
                  <Calendar size={12} />
                  {String(activeSeason.air_date).slice(0, 10)}
                </span>
              )}
              {activeSeason.air_date && totalEpisodesCount > 0 && <span className="active-season-info__meta-spacer" />}
              {totalEpisodesCount > 0 && (
                <span className="active-season-info__meta-episodes">
                  <Tv size={12} />
                  {localEpisodesCount < totalEpisodesCount
                    ? `Available ${localEpisodesCount}/${totalEpisodesCount}`
                    : `${totalEpisodesCount} ${t('library.details.episodes') || 'Episodes'}`}
                </span>
              )}
            </div>
          </div>

          {!isSeasonWatchedWithDate && (
            <button
              type="button"
              className={`season-watch-btn ${isSeasonWatched ? 'season-watch-btn--watched' : ''}`}
              onClick={handleSeasonWatchedToggle}
            >
              <Check size={16} />
              <span>
                {isSeasonWatched
                  ? (t('library.details.watched') || 'Watched')
                  : isSeasonPartiallyWatched
                  ? `${t('library.details.markWatched') || 'Mark Watched'} (-)`
                  : (t('library.details.markWatched') || 'Mark Watched')}
              </span>
            </button>
          )}
        </div>

        {activeSeason.overview && (
          <p className="active-season-info__overview">{activeSeason.overview}</p>
        )}
      </div>

      {/* Episode Cards List */}
      <div className="episodes-cards-list">
        {visibleEpisodes.map((episode) => {
          const isExpanded = !!expandedEpisodes[episode.id];
          const stillUrl = getStillUrl(episode.still_path);
          const formattedEpNum = formatEpisodeNumber(episode.episode_number);
          const episodeText = `${formattedEpNum.padStart(2, '0')}. ${episode.title || `Episode ${episode.episode_number}`}`;
          const episodeTmdbRating = episode.vote_average ?? episode.rating_tmdb ?? episode.rating;

          // Format metadata tags
          const durationMins = episode.runtime
            ? `${episode.runtime}m`
            : episode.technical?.duration
            ? `${Math.round(episode.technical.duration / 60)}m`
            : '';

          const metaItems = [
            episode.air_date ? String(episode.air_date).slice(0, 10) : null,
            durationMins || null,
            episode.technical?.resolution || null,
            episode.technical?.video_codec || null,
            episode.technical?.hdr_type || null,
          ].filter(Boolean);

          return (
            // eslint-disable-next-line jsx-a11y/no-static-element-interactions
            <div
              key={episode.id}
              className={`episode-card ${isExpanded ? 'is-expanded' : ''} ${
                episode.is_watched ? 'is-watched' : ''
              } ${!episode.path || episode.is_missing ? 'is-unowned' : ''}`}
              onClick={() => toggleEpisodeOverview(episode.id)}
            >
              {/* Left Side: Still Image */}
              <div className="episode-card__media-column">
                <div className="episode-card__still-wrapper">
                  {stillUrl ? (
                    <img src={stillUrl} alt="" className="episode-card__still" />
                  ) : (
                    <div className="episode-card__still-placeholder">
                      <Clapperboard size={24} />
                    </div>
                  )}
                  {episode.is_watched && (
                    <div className="episode-card__still-watched-overlay">
                      <Check size={16} />
                    </div>
                  )}
                  {episode.path && !episode.is_missing && (
                    <IconButton
                      variant="play-overlay"
                      onClick={(e) => {
                        e.stopPropagation();
                        playMutation.mutate(episode.id);
                      }}
                      title="Play episode"
                    >
                      <Play size={12} fill="currentColor" />
                    </IconButton>
                  )}
                </div>
              </div>

              {/* Center: Info copy */}
              <div className="episode-card__details">
                <h4 className="episode-card__title">{episodeText}</h4>
                
                {(metaItems.length > 0 || episode.is_multi_episode || (episodeTmdbRating !== undefined && episodeTmdbRating !== null && episodeTmdbRating !== '' && Number(episodeTmdbRating) > 0)) && (
                  <div className="episode-card__meta">
                    {episode.is_multi_episode && (
                      <Pill variant="neutral" className="episode-card__shared-pill">
                        {t('library.details.sharedFile') || 'Shared File'}
                      </Pill>
                    )}
                    {metaItems.map((meta, idx) => (
                      <span key={idx} className="episode-card__meta-item">
                        {meta}
                      </span>
                    ))}
                    {(episodeTmdbRating !== undefined && episodeTmdbRating !== null && episodeTmdbRating !== '' && Number(episodeTmdbRating) > 0) && (
                      <Pill variant="tmdb" className="episode-card__tmdb-pill">
                        <Star size={10} fill="currentColor" strokeWidth={1.8} />
                        {isNaN(parseFloat(episodeTmdbRating))
                          ? episodeTmdbRating
                          : parseFloat(episodeTmdbRating).toFixed(1)}
                      </Pill>
                    )}
                  </div>
                )}

                {episode.overview && (
                  <p className={`episode-card__overview ${isExpanded ? '' : 'is-truncated'}`}>
                    {episode.overview}
                  </p>
                )}

                {item.is_adult && episode.peaks_history && episode.peaks_history.length > 0 && isExpanded && (
                  <div className="episode-card__peaks-list" role="presentation" onClick={(e) => e.stopPropagation()}>
                    <div className="episode-card__peaks-title">
                      <Flame size={12} fill="currentColor" />
                      <span>{t('library.details.peaksTitle') || 'Peak Moments'} {LPAR}{episode.peaks_history.length}{RPAR}</span>
                    </div>
                    <div className="episode-card__peaks-items">
                      {episode.peaks_history.map((log) => (
                        <div key={log.id} className="episode-card__peak-item">
                          <span className="episode-card__peak-date">
                            {new Date(log.watched_at).toLocaleString()}
                          </span>
                          {log.video_position != null && (
                            <span className="episode-card__peak-position">
                              {formatTime(log.video_position)}
                            </span>
                          )}
                          <button
                            type="button"
                            className="episode-card__peak-delete"
                            onClick={(e) => {
                              e.stopPropagation();
                              deletePeakMutation.mutate({ itemId: episode.id, logId: log.id });
                            }}
                            disabled={deletePeakMutation.isPending}
                            title={t('library.details.deletePeakBtn') || 'Delete Peak'}
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Right Side: Actions */}
              {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
              <div className="episode-card__actions" onClick={(e) => e.stopPropagation()}>
                {isExpanded && (
                  <>
                    {/* Flame/Peak button */}
                    {item.is_adult && episode.path && !episode.is_missing && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          addPeakMutation.mutate(episode.id);
                        }}
                        disabled={addPeakMutation.isPending}
                        className="episode-card__action-btn episode-card__action-btn--peak"
                        title={t('library.details.addPeak') || 'Add Peak'}
                      >
                        <Flame size={16} />
                      </button>
                    )}

                    {/* Watch toggle */}
                    {!episode.last_watched_at && (
                      <button
                        type="button"
                        onClick={() =>
                          updateStatusMutation.mutate({
                            itemId: episode.id,
                            tvId: cleanId,
                            payload: {
                              is_watched: !episode.is_watched,
                              media_type: 'episode',
                            },
                          })
                        }
                        className={`episode-card__action-btn episode-card__action-btn--watch ${
                          episode.is_watched ? 'is-watched' : ''
                        }`}
                        title={episode.is_watched ? 'Mark unwatched' : 'Mark watched'}
                      >
                        {episode.is_watched ? <Check size={16} /> : <Eye size={16} />}
                      </button>
                    )}


                  </>
                )}

                {/* Chevron expand toggle */}
                <button
                  type="button"
                  className={`episode-card__action-btn episode-card__action-btn--chevron ${
                    isExpanded ? 'is-expanded' : ''
                  }`}
                  onClick={() => toggleEpisodeOverview(episode.id)}
                  aria-label="Toggle details"
                >
                  <ChevronDown size={16} />
                </button>
              </div>
            </div>
          );
        })}

        {(!activeSeason.episodes || activeSeason.episodes.length === 0) && (
          <div className="episodes-list__empty">
            {item?.progressive_seasons && activeSeason.episodes_complete === false
              ? (t('library.details.loadingSeason') || 'Loading season...')
              : (t('library.details.noEpisodesFound') || 'No episodes found.')}
          </div>
        )}

        {hasMoreEpisodes && (
          <div ref={loadMoreTriggerRef} className="episodes-list__load-more-trigger" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}
