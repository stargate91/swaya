/* eslint-disable react/jsx-no-literals, react-hooks/set-state-in-effect */
import { useState, useRef, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight, ChevronLeft, Check, Eye, Play,
  Clapperboard, Calendar, Tv, Star, Flame, Trash2, X
} from 'lucide-react';
import IconButton from '@/ui/IconButton';
import Pill from '@/ui/Pill';
import { resolveMediaImageUrl } from '@/lib/imageUrls';
import { formatEpisodeNumber, formatTime } from '../../utils/detailUtils';
import { useMediaDetailContext } from './MediaDetailContext';
import { useTranslation as useLangTranslation } from '@/providers/LanguageContext';
import api from '@/lib/api';
import './BespokeSeasonsSection.css';

const LPAR = '(';
const RPAR = ')';

export default function BespokeSeasonsSection() {
  const { state, mutations, t } = useMediaDetailContext();
  const { locale } = useLangTranslation();
  const metadataLanguage = locale === 'en' ? 'en-US' : locale;
  const { item, cleanId, nextEpisodeInfo } = state;
  const { updateStatusMutation, playMutation, bulkUpdateWatchedMutation, addPeakMutation, deletePeakMutation } = mutations;
  const queryClient = useQueryClient();

  const [lightboxUrl, setLightboxUrl] = useState(null);

  const handleOpenLightbox = (url) => {
    if (url) {
      setLightboxUrl(url);
    }
  };

  const seasonsList = useMemo(() => item?.seasons || [], [item?.seasons]);
  const seasonsCount = seasonsList.length;

  // Determine initial season and episode selection
  const initialSeasonNumber = nextEpisodeInfo?.seasonNumber ?? seasonsList[0]?.season_number ?? 1;
  const [selectedSeasonNumber, setSelectedSeasonNumber] = useState(initialSeasonNumber);

  const activeSeason = useMemo(() => {
    return seasonsList.find((s) => s.season_number === selectedSeasonNumber) || seasonsList[0];
  }, [seasonsList, selectedSeasonNumber]);

  // Load season detail (episodes) progressive loading
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
        // Ignore prefetch failures
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [activeSeason, cleanId, item?.progressive_seasons, queryClient, metadataLanguage]);

  const episodes = useMemo(() => activeSeason?.episodes || [], [activeSeason?.episodes]);
  const initialEpisodeId = useMemo(() => {
    if (nextEpisodeInfo?.seasonNumber === selectedSeasonNumber && nextEpisodeInfo?.episode?.id) {
      return nextEpisodeInfo.episode.id;
    }
    return episodes[0]?.id;
  }, [selectedSeasonNumber, nextEpisodeInfo, episodes]);

  const [selectedEpisodeId, setSelectedEpisodeId] = useState(initialEpisodeId);

  // Sync selected episode when season or episodes change
  useEffect(() => {
    if (episodes.length > 0) {
      const match = episodes.find(ep => ep.id === selectedEpisodeId);
      if (!match) {
        const nextUpEp = episodes.find(ep => ep.id === nextEpisodeInfo?.episode?.id);
        setSelectedEpisodeId(nextUpEp ? nextUpEp.id : episodes[0]?.id);
      }
    } else {
      setSelectedEpisodeId(null);
    }
  }, [selectedSeasonNumber, episodes, nextEpisodeInfo, selectedEpisodeId]);

  const activeEpisodeIndex = useMemo(() => {
    return episodes.findIndex(ep => ep.id === selectedEpisodeId);
  }, [episodes, selectedEpisodeId]);

  const activeEpisode = episodes[activeEpisodeIndex];

  // Carousel scroll handling
  const seasonsScrollRef = useRef(null);
  const episodesScrollRef = useRef(null);



  const scrollSeasons = (direction) => {
    const container = seasonsScrollRef.current;
    if (!container) return;
    const scrollAmount = container.clientWidth * 0.6;
    container.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth'
    });
  };

  const scrollEpisodes = (direction) => {
    const container = episodesScrollRef.current;
    if (!container) return;
    const scrollAmount = container.clientWidth * 0.6;
    container.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth'
    });
  };

  // Episode stepping
  const stepEpisode = (direction) => {
    if (episodes.length === 0) return;
    let nextIndex = activeEpisodeIndex + (direction === 'left' ? -1 : 1);
    if (nextIndex >= 0 && nextIndex < episodes.length) {
      setSelectedEpisodeId(episodes[nextIndex].id);
      // Auto-scroll pill into view
      setTimeout(() => {
        const activePill = episodesScrollRef.current?.querySelector('.bespoke-episode-pill.is-active');
        if (activePill && episodesScrollRef.current) {
          activePill.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
      }, 50);
    }
  };

  const getPosterUrl = (path) => path ? resolveMediaImageUrl(path, 'poster') : '';
  const getStillUrl = (path) => path ? resolveMediaImageUrl(path, 'still') : '';
  const getOriginalPosterUrl = (path) => path ? resolveMediaImageUrl(path, 'originalPoster') : '';
  const getOriginalStillUrl = (path) => path ? resolveMediaImageUrl(path, 'originalStill') : '';

  const isSeasonWatched = useMemo(() => {
    return episodes.length > 0 && episodes.every((ep) => ep.is_watched);
  }, [episodes]);

  const isSeasonPartiallyWatched = useMemo(() => {
    return episodes.length > 0 && episodes.some((ep) => ep.is_watched) && !isSeasonWatched;
  }, [episodes, isSeasonWatched]);

  const handleSeasonWatchedToggle = (e) => {
    e.stopPropagation();
    if (episodes.length === 0) return;
    const episodeIds = episodes.map((ep) => ep.id);
    bulkUpdateWatchedMutation.mutate({
      itemIds: episodeIds,
      isWatched: !isSeasonWatched,
      tvId: cleanId,
    });
  };

  if (seasonsCount === 0) return null;

  return (
    <div className="bespoke-seasons-section">
      {/* Unified Season & Episode Browser Card */}
      <div className="bespoke-unified-browser-card">
        
        {/* Row 1 Header: Seasons Horizontal Pills */}
        <div className="bespoke-browser-card__pills-header">
          <button
            type="button"
            className="bespoke-carousel-nav bespoke-carousel-nav--left"
            onClick={() => scrollSeasons('left')}
          >
            <ChevronLeft size={14} />
          </button>

          <div className="bespoke-seasons-pills" ref={seasonsScrollRef}>
            {seasonsList.map((season) => {
              const isActive = season.season_number === selectedSeasonNumber;
              const title = season.title || `Season ${season.season_number}`;

              return (
                <button
                  key={season.season_number}
                  type="button"
                  className={`bespoke-season-pill ${isActive ? 'is-active' : ''} ${
                    season.is_watched ? 'is-watched' : ''
                  }`}
                  onClick={() => setSelectedSeasonNumber(season.season_number)}
                >
                  <span>{title}</span>
                </button>
              );
            })}
          </div>

          <button
            type="button"
            className="bespoke-carousel-nav bespoke-carousel-nav--right"
            onClick={() => scrollSeasons('right')}
          >
            <ChevronRight size={14} />
          </button>
        </div>

        {/* Row 1 Body: Season Details */}
        <div className="bespoke-browser-card__body bespoke-browser-card__body--season">
          {/* Left Column: Large Season Poster */}
          <div className="bespoke-season-detail-card__poster-col">
            <div
              className="bespoke-season-detail-card__poster-wrapper"
              style={{ cursor: getPosterUrl(activeSeason.poster_path) ? 'pointer' : 'default' }}
              onClick={() => handleOpenLightbox(getOriginalPosterUrl(activeSeason.poster_path))}
            >
              {getPosterUrl(activeSeason.poster_path) ? (
                <img
                  src={getPosterUrl(activeSeason.poster_path)}
                  alt={activeSeason.title}
                  className="bespoke-season-detail-card__poster"
                />
              ) : (
                <div className="bespoke-season-detail-card__poster-placeholder">
                  <Clapperboard size={36} />
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Metadata & Overview */}
          <div className="bespoke-season-meta__content-col">
            <div className="bespoke-season-meta__header">
              <div>
                <h3 className="bespoke-season-meta__title">
                  {activeSeason.title || `Season ${activeSeason.season_number}`}
                </h3>
                <div className="bespoke-season-meta__sub">
                  {activeSeason.air_date && (
                    <span className="bespoke-season-meta__item">
                      <Calendar size={12} />
                      {String(activeSeason.air_date).slice(0, 10)}
                    </span>
                  )}
                  {activeSeason.episode_count > 0 && (
                    <span className="bespoke-season-meta__item">
                      <Tv size={12} />
                      {`${activeSeason.episode_count} ${t('library.details.episodes') || 'Episodes'}`}
                    </span>
                  )}
                </div>
              </div>

              <button
                type="button"
                className={`bespoke-season-watch-btn ${isSeasonWatched ? 'is-watched' : ''}`}
                onClick={handleSeasonWatchedToggle}
              >
                <Check size={14} />
                <span>
                  {isSeasonWatched
                    ? (t('library.details.watched') || 'Watched')
                    : isSeasonPartiallyWatched
                    ? `${t('library.details.markWatched') || 'Mark Watched'} (-)`
                    : (t('library.details.markWatched') || 'Mark Watched')}
                </span>
              </button>
            </div>

            {activeSeason.overview && (
              <p className="bespoke-season-meta__overview">{activeSeason.overview}</p>
            )}
          </div>
        </div>

        {/* Subtle Divider Line */}
        <div className="bespoke-browser-card__divider" />

        {/* Row 2 Header: Episode Pills */}
        {episodes.length > 0 && (
          <div className="bespoke-browser-card__pills-header">
            <button
              type="button"
              className="bespoke-carousel-nav bespoke-carousel-nav--left"
              onClick={() => scrollEpisodes('left')}
            >
              <ChevronLeft size={14} />
            </button>

            <div className="bespoke-episodes-pills" ref={episodesScrollRef}>
              {episodes.map((episode) => {
                const isActive = episode.id === selectedEpisodeId;
                const formattedEpNum = formatEpisodeNumber(episode.episode_number);
                const isNextUp = nextEpisodeInfo?.episode?.id === episode.id;

                return (
                  <button
                    key={episode.id}
                    type="button"
                    className={`bespoke-episode-pill ${isActive ? 'is-active' : ''} ${
                      episode.is_watched ? 'is-watched' : ''
                    } ${!episode.path || episode.is_missing ? 'is-unowned' : ''} ${isNextUp ? 'is-next-up' : ''}`}
                    onClick={() => setSelectedEpisodeId(episode.id)}
                  >
                    {isNextUp && <span className="bespoke-episode-pill__next-dot" />}
                    <span>{formattedEpNum}</span>
                  </button>
                );
              })}
            </div>

            <button
              type="button"
              className="bespoke-carousel-nav bespoke-carousel-nav--right"
              onClick={() => scrollEpisodes('right')}
            >
              <ChevronRight size={14} />
            </button>
          </div>
        )}

        {/* Row 2 Body: Episode Details */}
        {activeEpisode ? (
          <div className="bespoke-browser-card__body bespoke-browser-card__body--episode">
            {/* Overlaid Nav Chevrons */}
            <button
              type="button"
              className="bespoke-card-nav bespoke-card-nav--left"
              disabled={activeEpisodeIndex <= 0}
              onClick={() => stepEpisode('left')}
              title="Previous Episode"
            >
              <ChevronLeft size={24} />
            </button>

            <button
              type="button"
              className="bespoke-card-nav bespoke-card-nav--right"
              disabled={activeEpisodeIndex >= episodes.length - 1}
              onClick={() => stepEpisode('right')}
              title="Next Episode"
            >
              <ChevronRight size={24} />
            </button>

            {/* Left Column: Large Cinematic 16:9 Still */}
            <div className="bespoke-episode-detail-card__still-col">
              <div
                className="bespoke-episode-detail-card__still-wrapper"
                style={{ cursor: getStillUrl(activeEpisode.still_path) ? 'pointer' : 'default' }}
                onClick={() => handleOpenLightbox(getOriginalStillUrl(activeEpisode.still_path))}
              >
                {getStillUrl(activeEpisode.still_path) ? (
                  <img
                    src={getStillUrl(activeEpisode.still_path)}
                    alt={activeEpisode.title}
                    className="bespoke-episode-detail-card__still"
                  />
                ) : (
                  <div className="bespoke-episode-detail-card__still-placeholder">
                    <Clapperboard size={48} />
                  </div>
                )}



                {activeEpisode.path && !activeEpisode.is_missing && (
                  <IconButton
                    variant="play-overlay"
                    onClick={(e) => {
                      e.stopPropagation();
                      playMutation.mutate(activeEpisode.id);
                    }}
                    title="Play episode"
                  >
                    <Play size={20} fill="currentColor" />
                  </IconButton>
                )}
              </div>
            </div>

            {/* Right Column: Metadata & Copy */}
            <div className="bespoke-episode-detail-card__content-col">
              <div className="bespoke-episode-detail-card__header">
                <h4 className="bespoke-episode-detail-card__title">
                  {`${formatEpisodeNumber(activeEpisode.episode_number)}. ${
                    activeEpisode.title || `Episode ${activeEpisode.episode_number}`
                  }`}
                </h4>

                <div className="bespoke-episode-detail-card__actions">
                  {/* Flame/Peak button */}
                  {item.is_adult && activeEpisode.path && !activeEpisode.is_missing && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        addPeakMutation.mutate(activeEpisode.id);
                      }}
                      disabled={addPeakMutation.isPending}
                      className="bespoke-action-btn bespoke-action-btn--peak"
                      title={t('library.details.addPeak') || 'Add Peak'}
                    >
                      <Flame size={15} />
                    </button>
                  )}

                  {/* Watch toggle */}
                  {!activeEpisode.last_watched_at && (
                    <button
                      type="button"
                      onClick={() =>
                        updateStatusMutation.mutate({
                          itemId: activeEpisode.id,
                          tvId: cleanId,
                          payload: {
                            is_watched: !activeEpisode.is_watched,
                            media_type: 'episode',
                          },
                        })
                      }
                      className={`bespoke-action-btn bespoke-action-btn--watch ${
                        activeEpisode.is_watched ? 'is-watched' : ''
                      }`}
                      title={activeEpisode.is_watched ? 'Mark unwatched' : 'Mark watched'}
                    >
                      {activeEpisode.is_watched ? <Check size={15} /> : <Eye size={15} />}
                    </button>
                  )}
                </div>
              </div>

              {/* Episode Meta details */}
              <div className="bespoke-episode-detail-card__meta">
                {activeEpisode.air_date && (
                  <span className="bespoke-episode-detail-card__meta-item">
                    {String(activeEpisode.air_date).slice(0, 10)}
                  </span>
                )}
                {activeEpisode.runtime && (
                  <span className="bespoke-episode-detail-card__meta-item">
                    {`${activeEpisode.runtime}m`}
                  </span>
                )}
                {activeEpisode.technical?.resolution && (
                  <span className="bespoke-episode-detail-card__meta-item">
                    {activeEpisode.technical.resolution}
                  </span>
                )}
                {activeEpisode.vote_average != null && activeEpisode.vote_average > 0 && (
                  <Pill variant="tmdb" className="bespoke-episode-detail-card__tmdb-pill">
                    <Star size={10} fill="currentColor" strokeWidth={1.8} />
                    {parseFloat(activeEpisode.vote_average).toFixed(1)}
                  </Pill>
                )}
              </div>

              {/* Episode description */}
              {activeEpisode.overview && (
                <p className="bespoke-episode-detail-card__overview">
                  {activeEpisode.overview}
                </p>
              )}

              {/* Adult Peaks History */}
              {item.is_adult && activeEpisode.peaks_history && activeEpisode.peaks_history.length > 0 && (
                <div className="bespoke-episode-detail-card__peaks">
                  <div className="bespoke-episode-detail-card__peaks-title">
                    <Flame size={12} fill="currentColor" />
                    <span>{t('library.details.peaksTitle') || 'Peak Moments'} {LPAR}{activeEpisode.peaks_history.length}{RPAR}</span>
                  </div>
                  <div className="bespoke-episode-detail-card__peaks-list">
                    {activeEpisode.peaks_history.map((log) => (
                      <div key={log.id} className="bespoke-episode-detail-card__peak-item">
                        <span className="bespoke-episode-detail-card__peak-date">
                          {new Date(log.watched_at).toLocaleDateString()}
                        </span>
                        {log.video_position != null && (
                          <span className="bespoke-episode-detail-card__peak-position">
                            {formatTime(log.video_position)}
                          </span>
                        )}
                        <button
                          type="button"
                          className="bespoke-episode-detail-card__peak-delete"
                          onClick={(e) => {
                            e.stopPropagation();
                            deletePeakMutation.mutate({ itemId: activeEpisode.id, logId: log.id });
                          }}
                          disabled={deletePeakMutation.isPending}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="bespoke-episode-browser-card__empty">
            {item?.progressive_seasons && activeSeason.episodes_complete === false
              ? (t('library.details.loadingSeason') || 'Loading season...')
              : (t('library.details.noEpisodesFound') || 'No episodes found.')}
          </div>
        )}
      </div>
      {lightboxUrl && typeof document !== 'undefined' ? createPortal(
        <div
          className="organizer-details__lightbox"
          role="button"
          tabIndex={0}
          aria-label={t('common.close') || 'Close image preview'}
          onClick={() => setLightboxUrl(null)}
          onKeyDown={(event) => {
            if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              setLightboxUrl(null);
            }
          }}
        >
          <button
            type="button"
            className="organizer-details__lightbox-close"
            aria-label={t('common.close') || 'Close image preview'}
            onClick={(event) => {
              event.stopPropagation();
              setLightboxUrl(null);
            }}
          >
            <X size={18} />
          </button>
          <img
            src={lightboxUrl}
            alt="Enlarged preview"
            className="organizer-details__lightbox-image"
            onClick={(event) => event.stopPropagation()}
          />
        </div>,
        document.body
      ) : null}
    </div>
  );
}
