/* eslint-disable react/forbid-dom-props, react/jsx-no-literals, i18next/no-literal-string */
import { useState, useMemo, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  User, Tags, Image as ImageIcon,
  Minus, Plus, ChevronUp, ChevronDown, ChevronLeft, ChevronRight,
  DollarSign, TrendingUp, Coins
} from 'lucide-react';
import { useTranslation } from '@/providers/LanguageContext';
import { useUi } from '@/providers/UiProvider';
import { normalizeMediaType } from '@/lib/mediaTypes';
import UniversalImagePickerModal from './modals/UniversalImagePickerModal';
import { buildMediaExternalLinks } from './peopleCollectionDetailUtils.jsx';
import { API_BASE } from '@/lib/backend';
import { resolveMediaImageUrl, buildTmdbImageUrl, TMDB_IMAGE_SIZES } from '@/lib/imageUrls';

// Context
import { MediaDetailProvider, useMediaDetailContext } from './components/detail/MediaDetailContext';

// Hook
import useMediaDetail from './hooks/useMediaDetail';

import MediaHeaderInfo from './components/detail/MediaHeaderInfo';
import UserRatingSection from './components/detail/UserRatingSection';
import MediaOverview from './components/detail/MediaOverview';
import MediaActions from './components/detail/MediaActions';
import DetailPageShell from './components/detail/DetailPageShell';
import UtilityBarBottomPortal from '../../../components/UtilityBarBottomPortal';

// Panels
import BespokeSeasonsSection from './components/detail/BespokeSeasonsSection';
import TechnicalPanel from './components/detail/panels/TechnicalPanel';
import ExtrasPanel from './components/detail/panels/ExtrasPanel';
import BackdropsPanel from './components/detail/panels/BackdropsPanel';
import TagsPanel from './components/detail/panels/TagsPanel';
import './components/entityDetail/EntityDetailHeroSection.css';

function BespokeCastSection({ item, t, navigate }) {
  const settings = useMediaDetailContext()?.state?.settings;
  const isAdult = item.is_adult;
  const genderPref = settings?.adult_gender_preference;

  const processPeople = (list) => {
    if (!list) return [];
    if (!isAdult || !genderPref || genderPref === 'all') {
      return list.map(p => ({ ...p, isFilteredOut: false }));
    }
    return list.map(person => {
      let isFilteredOut = false;
      if (genderPref === 'female' && person.gender !== 1) {
        isFilteredOut = true;
      } else if (genderPref === 'male' && person.gender !== 2) {
        isFilteredOut = true;
      }
      return { ...person, isFilteredOut };
    });
  };

  const filteredDirectors = processPeople(item.directors);
  const filteredWriters = processPeople(item.writers);
  const filteredSound = processPeople(item.sound);
  const filteredCast = processPeople(item.cast);
  const resolvePersonAvatarUrl = (path) => resolveMediaImageUrl(path, 'person', API_BASE);

  const maxTotal = 15;

  const allPeople = useMemo(() => {
    const list = [];

    // 1. Directors (max 2) - Priority 1
    const slicedDirectors = filteredDirectors ? filteredDirectors.slice(0, 2) : [];
    slicedDirectors.forEach(p => {
      list.push({ ...p, displayRole: t('library.people.roles.director') || 'Director' });
    });

    // 2. Cast/Actors (up to remaining slots) - Priority 2
    const remainingForCast = maxTotal - list.length;
    const slicedCast = filteredCast ? filteredCast.slice(0, remainingForCast) : [];
    slicedCast.forEach(p => {
      if (!list.some(x => x.id === p.id)) {
        list.push({ ...p, displayRole: p.character });
      }
    });

    // 3. Writers (if limit not reached) - Priority 3
    if (list.length < maxTotal) {
      const remainingForWriters = maxTotal - list.length;
      const slicedWriters = filteredWriters ? filteredWriters.slice(0, Math.min(2, remainingForWriters)) : [];
      slicedWriters.forEach(p => {
        if (!list.some(x => x.id === p.id)) {
          list.push({ ...p, displayRole: t('library.people.roles.writer') || 'Writer' });
        }
      });
    }

    // 4. Sound/Music (if limit not reached) - Priority 4
    if (list.length < maxTotal) {
      const remainingForSound = maxTotal - list.length;
      const slicedSound = filteredSound ? filteredSound.slice(0, Math.min(2, remainingForSound)) : [];
      slicedSound.forEach(p => {
        if (!list.some(x => x.id === p.id)) {
          list.push({ ...p, displayRole: p.job || 'Composer' });
        }
      });
    }

    // Sort: Preferred gender (isFilteredOut === false) comes first
    list.sort((a, b) => {
      if (a.isFilteredOut && !b.isFilteredOut) return 1;
      if (!a.isFilteredOut && b.isFilteredOut) return -1;
      return 0;
    });

    return list;
  }, [filteredDirectors, filteredCast, filteredWriters, filteredSound, maxTotal, t]);

  const castScrollRef = useRef(null);
  const [castScrollState, setCastScrollState] = useState({ left: false, right: false });

  const handleScrollState = () => {
    const container = castScrollRef.current;
    if (!container) return;
    const { scrollLeft, scrollWidth, clientWidth } = container;
    setCastScrollState({
      left: scrollLeft > 4,
      right: scrollLeft < scrollWidth - clientWidth - 4
    });
  };

  useEffect(() => {
    const timer = setTimeout(handleScrollState, 100);
    return () => clearTimeout(timer);
  }, [allPeople]);

  const scrollCast = (direction) => {
    const container = castScrollRef.current;
    if (!container) return;
    const scrollAmount = container.clientWidth * 0.6;
    container.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth'
    });
  };

  if (allPeople.length === 0) return null;

  return (
    <div className="bespoke-cast-section">
      <div className="bespoke-cast-browser-card">
        <div className="bespoke-browser-card__pills-header">
          <span className="bespoke-cast-title">
            {t('library.details.cast') || 'Cast & Crew'}
          </span>
        </div>
        <div className="bespoke-cast-browser-card__body">
          <button
            type="button"
            className="bespoke-carousel-nav bespoke-carousel-nav--left"
            onClick={() => scrollCast('left')}
          >
            <ChevronLeft size={14} />
          </button>

          <div className={`dashboard-cast-carousel-container bespoke-fade-container ${castScrollState.left ? 'has-fade-left' : ''} ${castScrollState.right ? 'has-fade-right' : ''}`}>
            <div
              className="dashboard-cast-grid"
              ref={castScrollRef}
              onScroll={handleScrollState}
            >
              {allPeople.map(person => (
                <div
                  key={person.id}
                  className={`dashboard-cast-card ${person.isFilteredOut ? 'dashboard-cast-card--filtered' : ''}`}
                  onClick={person.isFilteredOut ? undefined : () => navigate(`/library/people/${person.id}`, { state: { allowAdult: true } })}
                >
                  <div className={`dashboard-cast-card__avatar-wrapper ${person.isFilteredOut ? 'dashboard-cast-card__avatar-wrapper--filtered' : ''}`}>
                    {person.profile_path && !person.isFilteredOut ? (
                      <img
                        src={resolvePersonAvatarUrl(person.profile_path)}
                        alt={person.name}
                        className="dashboard-cast-card__avatar"
                      />
                    ) : (
                      <div className="dashboard-cast-card__avatar-fallback">
                        <User size={24} />
                      </div>
                    )}
                  </div>
                  <span className="dashboard-cast-card__name">
                    {person.name}
                    {person.age_at_release != null && ` (${person.age_at_release})`}
                  </span>
                  {person.displayRole && (
                    <span className="dashboard-cast-card__role">{person.displayRole}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
          <button
            type="button"
            className="bespoke-carousel-nav bespoke-carousel-nav--right"
            onClick={() => scrollCast('right')}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

function BespokeCompaniesSection({ item, t }) {
  const companiesScrollRef = useRef(null);
  const [companiesScrollState, setCompaniesScrollState] = useState({ left: false, right: false });

  const handleScrollState = () => {
    const container = companiesScrollRef.current;
    if (!container) return;
    const { scrollLeft, scrollWidth, clientWidth } = container;
    setCompaniesScrollState({
      left: scrollLeft > 4,
      right: scrollLeft < scrollWidth - clientWidth - 4
    });
  };

  useEffect(() => {
    const timer = setTimeout(handleScrollState, 100);
    return () => clearTimeout(timer);
  }, [item?.companies]);

  const scrollCompanies = (direction) => {
    const container = companiesScrollRef.current;
    if (!container) return;
    const scrollAmount = container.clientWidth * 0.6;
    container.scrollBy({
      left: direction === 'left' ? -scrollAmount : scrollAmount,
      behavior: 'smooth'
    });
  };

  if (!item?.companies || item.companies.length === 0) return null;

  return (
    <div className="bespoke-companies-section">
      <div className="bespoke-companies-card">
        <div className="bespoke-browser-card__pills-header">
          <span className="bespoke-cast-title">
            {t('library.details.productionCompanies') || 'Production Companies'}
          </span>
        </div>
        <div className="bespoke-cast-browser-card__body">
          <button
            type="button"
            className="bespoke-carousel-nav bespoke-carousel-nav--left"
            onClick={() => scrollCompanies('left')}
          >
            <ChevronLeft size={14} />
          </button>

          <div className={`dashboard-cast-carousel-container bespoke-fade-container ${companiesScrollState.left ? 'has-fade-left' : ''} ${companiesScrollState.right ? 'has-fade-right' : ''}`}>
            <div
              className="bespoke-companies-body"
              ref={companiesScrollRef}
              onScroll={handleScrollState}
            >
              {item.companies.map((c, i) => (
                <div key={i} className="bespoke-company-item" title={c.name}>
                  {c.logo_path ? (
                    <img src={resolveMediaImageUrl(c.logo_path, 'logo', API_BASE)} alt={c.name} className="bespoke-company-logo" />
                  ) : (
                    <span className="bespoke-company-name-only">{c.name}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <button
            type="button"
            className="bespoke-carousel-nav bespoke-carousel-nav--right"
            onClick={() => scrollCompanies('right')}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}

export function BespokeDetailsSection({ item, t }) {
  const isSceneType = item?.type === 'scene';
  const hasImdb = !isSceneType && item?.rating_imdb != null && Number(item.rating_imdb) > 0;
  const hasTmdb = !isSceneType && item?.rating_tmdb != null && Number(item.rating_tmdb) > 0;
  const hasRotten = !isSceneType && item?.rating_rotten != null && item?.rating_rotten !== '';
  const hasMeta = !isSceneType && item?.rating_meta != null && Number(item.rating_meta) > 0;
  const hasPorndb = item?.rating_porndb != null && Number(item.rating_porndb) > 0;

  const ratings = [];
  if (hasImdb) ratings.push({ id: 'imdb', logo: '/rating/imdb.png', alt: 'IMDb', value: `${item.rating_imdb.toFixed(1)}/10` });
  if (hasTmdb) ratings.push({ id: 'tmdb', logo: '/rating/tmdb.png', alt: 'TMDb', value: `${item.rating_tmdb.toFixed(1)}/10` });
  if (hasRotten) ratings.push({ id: 'rotten', logo: '/rating/rottan_tomatoes.png', alt: 'Rotten Tomatoes', value: item.rating_rotten });
  if (hasMeta) ratings.push({ id: 'meta', logo: '/rating/metacritic.png', alt: 'Metacritic', value: `${item.rating_meta}/100` });
  if (hasPorndb) ratings.push({ id: 'porndb', logo: '/rating/theporndb.png', alt: 'ThePornDB', value: `${item.rating_porndb.toFixed(1)}/10` });

  const formatCurrency = (num) => {
    if (num === undefined || num === null || num === 0) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0
    }).format(num);
  };

  const profit = item.revenue && item.budget ? item.revenue - item.budget : 0;
  const companies = item.companies || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4xl)' }}>
      {ratings.length > 0 && (
        <div className="dashboard-section">
          <h4 className="dashboard-section__title">{t('library.details.ratingsSection') || 'Ratings'}</h4>
          <div className="dashboard-ratings-grid">
            {ratings.map(rating => (
              <div key={rating.id} className="dashboard-rating-box">
                <img src={rating.logo} alt={rating.alt} className="dashboard-rating-box__logo" />
                <span className="dashboard-rating-box__value">{rating.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="dashboard-section">
        <h4 className="dashboard-section__title">{t('library.details.details') || 'Details'}</h4>
        <div className="dashboard-metadata-grid">
          {item.release_date && (
            <div className="dashboard-metadata-card">
              <span className="dashboard-metadata-card__label">{t('library.details.releaseDate') || 'Release Date'}</span>
              <span className="dashboard-metadata-card__value">{item.release_date}</span>
            </div>
          )}
          {item.release_status && (
            <div className="dashboard-metadata-card">
              <span className="dashboard-metadata-card__label">{t('library.details.status') || 'Status'}</span>
              <span className="dashboard-metadata-card__value">{item.release_status}</span>
            </div>
          )}
          {item.budget > 0 && (
            <div className="dashboard-metadata-card">
              <span className="dashboard-metadata-card__label">{t('library.details.budget') || 'Budget'}</span>
              <span className="dashboard-metadata-card__value">{formatCurrency(item.budget)}</span>
            </div>
          )}
          {item.revenue > 0 && (
            <div className="dashboard-metadata-card">
              <span className="dashboard-metadata-card__label">{t('library.details.revenue') || 'Revenue'}</span>
              <span className="dashboard-metadata-card__value">{formatCurrency(item.revenue)}</span>
            </div>
          )}
          {item.budget > 0 && item.revenue > 0 && (
            <div className="dashboard-metadata-card dashboard-metadata-card--span-2">
              <span className="dashboard-metadata-card__label">{t('library.details.profit') || 'Profit'}</span>
              <span className={`dashboard-metadata-card__value ${profit >= 0 ? 'dashboard-metadata-card__value--success' : 'dashboard-metadata-card__value--danger'}`}>
                {formatCurrency(profit)}
              </span>
            </div>
          )}
        </div>
      </div>

      {companies.length > 0 && !isSceneType && (
        <div className="dashboard-section">
          <h4 className="dashboard-section__title">
            {item.is_adult ? (t('library.details.studio') || 'Studio') : (t('library.details.productionCompanies') || 'Production Companies')}
          </h4>
          <div className="dashboard-studios-list">
            {companies.map(it => {
              const logoUrl = it.logo_path
                ? (it.logo_path.startsWith('http') || it.logo_path.startsWith('/media/') || it.logo_path.startsWith('data/'))
                  ? resolveMediaImageUrl(it.logo_path, 'logo')
                  : buildTmdbImageUrl(it.logo_path, TMDB_IMAGE_SIZES.posterThumb)
                : null;
              if (!logoUrl) return null;
              return (
                <div key={it.id} className="dashboard-studio-logo" title={it.name}>
                  <img src={logoUrl} alt={it.name} />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function CompactWatchStatsSection({ item, isMovie, isScene, t }) {
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false);

  if (!item) return null;

  const formatLogDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const formatTime = (seconds) => {
    if (!seconds) return '0:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  let watchStatus;
  let watchCount;
  let progressPercent;
  let progressText;
  let lastWatchedText;

  const logs = isMovie || isScene
    ? (item.playback_logs || [])
    : (() => {
      const regularSeasons = (item.seasons || []).filter(s => s.season_number > 0);
      const watchStats = item.watch_stats;
      if (watchStats?.playback_logs) return watchStats.playback_logs;
      const list = [];
      regularSeasons.forEach(season => {
        (season.episodes || []).forEach(episode => {
          if (episode.playback_logs) {
            episode.playback_logs.forEach(log => {
              list.push({
                ...log,
                seasonNumber: season.season_number,
                episodeNumber: episode.episode_number,
              });
            });
          }
        });
      });
      list.sort((a, b) => new Date(b.watched_at) - new Date(a.watched_at));
      return list;
    })();

  if (isMovie || isScene) {
    const duration = item.technical?.duration || (item.runtime ? item.runtime * 60 : 0);
    progressPercent = duration > 0 && item.resume_position
      ? Math.round((item.resume_position / duration) * 100)
      : 0;

    watchStatus = item.is_watched
      ? (t('library.details.statusWatched') || 'Watched')
      : (item.resume_position > 0
        ? (t('library.details.statusInProgress') || 'In Progress')
        : (t('library.details.statusUnwatched') || 'Unwatched'));

    progressText = item.is_watched
      ? (t('library.details.statusWatched') || 'Watched')
      : (item.resume_position > 0
        ? `${formatTime(item.resume_position)} / ${formatTime(duration)}`
        : '0:00');

    watchCount = item.watch_count || 0;
    lastWatchedText = item.last_watched_at ? formatLogDate(item.last_watched_at) : (t('library.details.never') || 'Never');
  } else {
    // TV show
    const regularSeasons = (item.seasons || []).filter(s => s.season_number > 0);
    const allEpisodes = regularSeasons.flatMap(s => s.episodes || []);
    const watchStats = item.watch_stats;

    const totalEpisodesCount = watchStats
      ? watchStats.total_episodes_count
      : allEpisodes.length;

    const watchedEpisodesCount = watchStats
      ? watchStats.watched_episodes_count
      : allEpisodes.filter(ep => ep.is_watched).length;

    progressPercent = totalEpisodesCount > 0
      ? Math.round((watchedEpisodesCount / totalEpisodesCount) * 100)
      : 0;

    const inProgressEpisodes = watchStats
      ? watchStats.in_progress_episodes
      : allEpisodes.filter(e => e.resume_position > 0);

    const isInProgress = inProgressEpisodes.length > 0;

    watchStatus = watchedEpisodesCount === totalEpisodesCount && totalEpisodesCount > 0
      ? (t('library.details.statusWatched') || 'Watched')
      : (isInProgress || watchedEpisodesCount > 0
        ? (t('library.details.statusInProgress') || 'In Progress')
        : (t('library.details.statusUnwatched') || 'Unwatched'));

    progressText = `${watchedEpisodesCount} / ${totalEpisodesCount} ep`;

    let tvLastWatched = null;
    if (watchStats?.playback_logs && watchStats.playback_logs.length > 0) {
      tvLastWatched = watchStats.playback_logs[0].watched_at;
    } else {
      if (logs.length > 0) {
        tvLastWatched = logs[0].watched_at;
      }
    }

    watchCount = logs.length;
    lastWatchedText = tvLastWatched ? formatLogDate(tvLastWatched) : (t('library.details.never') || 'Never');
  }

  const statusClass = watchStatus === 'Watched' ? 'watched' : (watchStatus === 'In Progress' ? 'progress' : 'unwatched');

  return (
    <div className="bespoke-boxoffice-section compact-watch-stats-section">
      <div className="bespoke-boxoffice-card">
        <div className="bespoke-browser-card__pills-header">
          <span className="bespoke-cast-title">
            {t('library.details.watchStats') || 'Watch Stats'}
          </span>
        </div>
        <div className="bespoke-boxoffice-body">
          <div className="bespoke-boxoffice-stat">
            <div className="bespoke-boxoffice-info">
              <span className="bespoke-boxoffice-label">
                {t('library.details.watchStatus') || 'Status'}
              </span>
              <span className={`specs-card__value status-${statusClass} bespoke-boxoffice-value`}>
                {watchStatus}
                {((isMovie || isScene) && watchCount > 0) && (
                  <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginLeft: '6px', fontWeight: 'normal' }}>
                    ({watchCount}x)
                  </span>
                )}
              </span>
            </div>
          </div>

          <div className="bespoke-boxoffice-stat">
            <div className="bespoke-boxoffice-info" style={{ width: '100%' }}>
              <span className="bespoke-boxoffice-label">
                {t('library.details.movieProgress') || 'Progress'}
              </span>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'rgba(255,255,255,0.6)', marginBottom: '4px' }}>
                <span>{progressText}</span>
                <span>{progressPercent}%</span>
              </div>
              <progress
                className="specs-card__progress"
                value={progressPercent}
                max={100}
                style={{ width: '100%', height: '4px', borderRadius: '2px', background: 'rgba(255,255,255,0.1)' }}
              />
            </div>
          </div>

          <div className="bespoke-boxoffice-stat">
            <div className="bespoke-boxoffice-info">
              <span className="bespoke-boxoffice-label">
                {t('library.details.lastWatched') || 'Last Watched'}
              </span>
              <span className="bespoke-boxoffice-value" style={{ fontSize: '0.8rem', whiteSpace: 'normal' }}>{lastWatchedText}</span>
            </div>
          </div>

          {logs.length > 0 && (
            <div className="bespoke-boxoffice-stat" style={{ gridColumn: '1 / -1', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '10px', marginTop: '10px', flexDirection: 'column', alignItems: 'stretch', width: '100%' }}>
              <button
                type="button"
                onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', background: 'none', border: 'none', padding: 0, color: 'rgba(255,255,255,0.7)', cursor: 'pointer', fontSize: '0.85rem' }}
              >
                <span>{t('library.details.watchActivity') || 'Watch History'} ({logs.length})</span>
                {isHistoryExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>

              {isHistoryExpanded && (
                <div
                  style={{
                    marginTop: '8px',
                    maxHeight: logs.length > 3 ? '115px' : 'none',
                    overflowY: logs.length > 3 ? 'auto' : 'visible',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                    width: '100%',
                    paddingRight: logs.length > 3 ? '4px' : '0'
                  }}
                  className={logs.length > 3 ? 'custom-scrollbar' : ''}
                >
                  {logs.map((log, idx) => {
                    const dateStr = formatLogDate(log.watched_at);
                    const epText = log.seasonNumber != null && log.episodeNumber != null
                      ? `S${log.seasonNumber.toString().padStart(2, '0')}E${log.episodeNumber.toString().padStart(2, '0')}`
                      : '';
                    return (
                      <div key={log.id || idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', borderRadius: '4px', background: 'rgba(255,255,255,0.03)', fontSize: '0.75rem', color: 'rgba(255,255,255,0.8)', width: '100%' }}>
                        <span style={{ fontWeight: 'bold' }}>{epText || (t('library.details.playSession') || 'Session')}</span>
                        <span style={{ opacity: 0.6 }}>{dateStr}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function MediaDetailPage({ type = 'movie' }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { openModal, closeModal, toast } = useUi();

  const normalizedType = normalizeMediaType(type, type);

  const detailState = useMediaDetail({
    id,
    type: normalizedType,
    t,
    openModal,
    closeModal
  });

  const { state } = detailState;
  const {
    backdropUrl,
    posterUrl,
    item,
    isLoading,
    isMovie,
    isScene
  } = state;

  const [isScrolled, setIsScrolled] = useState(false);
  const [isSocialExpanded, setIsSocialExpanded] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsScrolled(false);
  }, [id]);

  useEffect(() => {
    const handleWheel = (e) => {
      if (Math.abs(e.deltaY) > 5) {
        if (e.deltaY > 0 && !isScrolled) {
          setIsScrolled(true);
        } else if (e.deltaY < 0 && isScrolled) {
          if (e.target.closest('.custom-scrollbar')) {
            return;
          }
          const isInsideSection = e.target.closest('.media-detail-page__inline-sections');
          if (isInsideSection) {
            if (isInsideSection.scrollTop > 0) {
              return;
            }
          }
          setIsScrolled(false);
        }
      }
    };

    window.addEventListener('wheel', handleWheel, { passive: true });
    return () => window.removeEventListener('wheel', handleWheel);
  }, [isScrolled]);

  const handleScrollToggle = () => {
    setIsScrolled(!isScrolled);
  };

  const externalLinks = useMemo(
    () => buildMediaExternalLinks(item, t, normalizedType),
    [item, t, normalizedType]
  );

  const socialLinks = useMemo(() => {
    if (!item) return [];
    const knownIcons = new Set([
      '/links/tmdb.png', '/links/stashdb.png', '/links/fansdb.webp', '/links/theporndb.png',
      '/links/imdb.png', '/links/instagram.ico', '/links/instagram.svg',
      '/links/facebook.ico', '/links/facebook.svg', '/links/x.svg',
      '/links/tiktok.png', '/links/tiktok.svg', '/links/youtube.ico', '/links/youtube.svg',
      '/links/onylfans.ico', '/links/fansly.png', '/links/pornhub.ico',
      '/links/manyvids.ico', '/links/patreon.ico', '/links/linktree.png',
      '/links/threads.png', '/links/twitch.jpg', '/links/kick.ico',
      '/links/bluesky.png', '/links/clip4sale.ico', '/links/allmylinks.ico',
      '/links/beacons.png', '/links/iafd.ico', '/links/babepedia.ico',
      '/links/freeones.png', '/links/data18.ico', '/links/homepage.png',
      '/links/twitter.png', '/links/website.svg',
    ]);
    const allLinks = externalLinks.filter(link =>
      link.iconSrc && knownIcons.has(link.iconSrc)
    );
    const order = ['theporndb', 'fansdb', 'stashdb', 'tmdb', 'imdb', 'website', 'instagram', 'facebook', 'x', 'twitter', 'tiktok', 'youtube'];
    const ordered = [];
    for (const key of order) {
      const found = allLinks.find(l => l.key === key);
      if (found) {
        ordered.push(found);
      }
    }
    for (const link of allLinks) {
      if (!order.includes(link.key)) {
        ordered.push(link);
      }
    }
    const seenIcons = new Set();
    const uniqueLinks = [];
    for (const link of ordered) {
      if (!link.iconSrc) continue;
      const isGeneric = link.iconSrc.includes('homepage') || link.iconSrc.includes('website');
      if (isGeneric || !seenIcons.has(link.iconSrc)) {
        seenIcons.add(link.iconSrc);
        uniqueLinks.push(link);
      }
    }
    return uniqueLinks;
  }, [externalLinks, item]);

  const hasExtraSocials = socialLinks.length > 4;
  const mainSocialLinks = hasExtraSocials ? socialLinks.slice(0, 4) : socialLinks;
  const extraSocialLinks = hasExtraSocials ? socialLinks.slice(4) : [];

  const handleOpenBackdropModal = () => {
    openModal({
      title: t('library.details.backdrops') || 'Choose Backdrop',
      variant: 'wide',
      content: (
        <MediaDetailProvider value={{ ...detailState, t, navigate, toast, type: normalizedType, id }}>
          <BackdropsPanel showTitle={false} />
        </MediaDetailProvider>
      ),
    });
  };

  const handleOpenPosterModal = () => {
    openModal({
      title: t('library.details.choosePoster') || 'Choose Poster',
      variant: 'wide',
      content: (
        <UniversalImagePickerModal
          entityId={id}
          tmdbId={item?.tmdb_id || item?.tv_tmdb_id}
          imageType="poster"
          entityType={normalizedType}
          currentPath={item?.poster_path}
          t={t}
          toast={toast}
          onClose={closeModal}
        />
      ),
    });
  };

  const handleOpenLogoModal = () => {
    openModal({
      title: t('library.details.chooseLogo') || 'Choose Logo',
      variant: 'wide',
      content: (
        <UniversalImagePickerModal
          entityId={id}
          tmdbId={item?.tmdb_id || item?.tv_tmdb_id}
          imageType="logo"
          entityType={normalizedType}
          currentPath={item?.logo_path}
          t={t}
          toast={toast}
          onClose={closeModal}
          item={item}
        />
      ),
    });
  };

  if (isLoading) {
    return <DetailPageShell isLoading />;
  }

  return (
    <MediaDetailProvider value={{
      ...detailState,
      t,
      navigate,
      toast,
      type: normalizedType,
      id,
      handleOpenLogoModal,
      handleOpenPosterModal,
      isDrawerOpen,
      setIsDrawerOpen
    }}>
      <DetailPageShell
        backdropUrl={backdropUrl}
        fallbackUrl={posterUrl}
        isScene={item?.type === 'scene'}
        backLabel={t('common.back') || 'Back'}
        pageClassName={`media-detail-page--scroll-transition ${isScrolled ? 'is-scrolled' : ''}`}
        containerRef={containerRef}
        topRightControls={(
          <>
            <button
              type="button"
              onClick={() => {
                openModal({
                  title: t('library.details.tagger') || 'Tagger',
                  variant: 'wide',
                  content: (
                    <MediaDetailProvider value={{ ...detailState, t, navigate, toast, type: normalizedType, id }}>
                      <TagsPanel />
                    </MediaDetailProvider>
                  ),
                });
              }}
              className="media-detail-page__side-nav-toggle"
              title={t('library.details.tagger') || 'Tagger'}
            >
              <Tags size={18} />
            </button>



            <button
              type="button"
              onClick={handleOpenBackdropModal}
              className="media-detail-page__side-nav-toggle"
              title={t('library.details.backdrops') || 'Choose Backdrop'}
            >
              <ImageIcon size={18} />
            </button>
          </>
        )}
      >
        <div className="media-detail-page__transition-wrapper">
          <div className="media-detail-page__hero-content-section">
            {(!state.logoUrl && !state.backdropUrl && state.posterUrl) ? (
              <div className="media-detail-page__fallback-grid">
                <div
                  className="media-detail-page__fallback-poster-col"
                  role="button"
                  tabIndex={0}
                  onClick={handleOpenPosterModal}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      handleOpenPosterModal();
                    }
                  }}
                  title={t('library.details.choosePoster') || 'Choose Poster'}
                >
                  <img src={state.posterUrl} alt={state.title} className="media-detail-page__fallback-poster" />
                </div>
                <div className="media-detail-page__fallback-content-col">
                  <MediaHeaderInfo isFallbackGrid={true} />
                  <UserRatingSection />
                  <MediaOverview />
                </div>
              </div>
            ) : (
              <>
                <MediaHeaderInfo />
                <UserRatingSection />
                <MediaOverview />
              </>
            )}
          </div>

          <div className="media-detail-page__inline-sections">
            <div className="media-detail-page__inline-main-col">
              {item && <BespokeCastSection item={item} t={t} navigate={navigate} />}
              {!isMovie && !isScene && item && <BespokeSeasonsSection />}

              {/* Box Office Section for Movies */}
              {isMovie && item && (item.budget > 0 || item.revenue > 0) && (() => {
                const formatCurrency = (val) => {
                  if (!val || val <= 0) return '-';
                  return new Intl.NumberFormat('en-US', {
                    style: 'currency',
                    currency: 'USD',
                    maximumFractionDigits: 0
                  }).format(val);
                };

                const budgetStr = formatCurrency(item.budget);
                const revenueStr = formatCurrency(item.revenue);
                const netProfit = (item.revenue || 0) - (item.budget || 0);
                const hasProfitInfo = item.budget > 0 && item.revenue > 0;
                const isProfit = netProfit >= 0;

                return (
                  <div className="bespoke-boxoffice-section">
                    <div className="bespoke-boxoffice-card">
                      <div className="bespoke-browser-card__pills-header">
                        <span className="bespoke-cast-title">
                          {t('library.details.boxOffice') || 'Box Office'}
                        </span>
                      </div>
                      <div className="bespoke-boxoffice-body">
                        {item.budget > 0 && (
                          <div className="bespoke-boxoffice-stat">
                            <div className="bespoke-boxoffice-icon-wrapper">
                              <DollarSign size={16} />
                            </div>
                            <div className="bespoke-boxoffice-info">
                              <span className="bespoke-boxoffice-label">
                                {t('library.details.budget') || 'Budget'}
                              </span>
                              <span className="bespoke-boxoffice-value">{budgetStr}</span>
                            </div>
                          </div>
                        )}

                        {item.revenue > 0 && (
                          <div className="bespoke-boxoffice-stat">
                            <div className="bespoke-boxoffice-icon-wrapper">
                              <Coins size={16} />
                            </div>
                            <div className="bespoke-boxoffice-info">
                              <span className="bespoke-boxoffice-label">
                                {t('library.details.revenue') || 'Revenue'}
                              </span>
                              <span className="bespoke-boxoffice-value">{revenueStr}</span>
                            </div>
                          </div>
                        )}

                        {hasProfitInfo && (
                          <div className={`bespoke-boxoffice-stat ${isProfit ? 'bespoke-boxoffice-stat--profit' : 'bespoke-boxoffice-stat--loss'}`}>
                            <div className="bespoke-boxoffice-icon-wrapper">
                              <TrendingUp size={16} />
                            </div>
                            <div className="bespoke-boxoffice-info">
                              <span className="bespoke-boxoffice-label">
                                {isProfit ? (t('library.details.profit') || 'Net Profit') : (t('library.details.loss') || 'Net Loss')}
                              </span>
                              <span className="bespoke-boxoffice-value">
                                {formatCurrency(Math.abs(netProfit))}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Production Companies Section for Movies */}
              {isMovie && <BespokeCompaniesSection item={item} t={t} />}
            </div>
            <div className="media-detail-page__inline-side-col">
              {item && (
                <CompactWatchStatsSection
                  item={item}
                  isMovie={isMovie}
                  isScene={isScene}
                  t={t}
                />
              )}
            </div>
          </div>
        </div>

        <UtilityBarBottomPortal side="left">
          <MediaActions />
        </UtilityBarBottomPortal>

        <UtilityBarBottomPortal side="center">
          <button
            type="button"
            className="entity-detail-page__scroll-toggle-btn"
            onClick={handleScrollToggle}
            title={isScrolled ? (t('library.details.backToProfile') || 'Back to Profile') : (t('library.details.scrollToCredits') || 'Scroll to Details')}
          >
            {isScrolled ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
        </UtilityBarBottomPortal>

        {socialLinks.length > 0 && (
          <UtilityBarBottomPortal side="right">
            <div className={`entity-detail-page__bottom-socials ${isSocialExpanded ? 'entity-detail-page__bottom-socials--expanded' : ''}`}>
              <div className="entity-detail-page__bottom-socials-wrapper">
                {hasExtraSocials && (
                  <div className="entity-detail-page__bottom-socials-extra">
                    {extraSocialLinks.map((link) => (
                      <a
                        key={link.key}
                        href={link.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="entity-detail-page__bottom-social-btn"
                        title={link.label}
                      >
                        <img src={link.iconSrc || '/links/website.svg'} alt={link.label} />
                      </a>
                    ))}
                  </div>
                )}

                <div className="entity-detail-page__bottom-socials-main">
                  {mainSocialLinks.map((link) => (
                    <a
                      key={link.key}
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="entity-detail-page__bottom-social-btn"
                      title={link.label}
                    >
                      <img src={link.iconSrc || '/links/website.svg'} alt={link.label} />
                    </a>
                  ))}
                </div>

                {hasExtraSocials && (
                  <button
                    type="button"
                    className="entity-detail-page__bottom-social-toggle"
                    onClick={() => setIsSocialExpanded(!isSocialExpanded)}
                    title={isSocialExpanded ? (t('common.less') || 'Show Less') : (t('common.more') || 'Show More')}
                  >
                    {isSocialExpanded ? <Minus size={14} /> : <Plus size={14} />}
                  </button>
                )}
              </div>
            </div>
          </UtilityBarBottomPortal>
        )}
      </DetailPageShell>

      {/* Details/Metadata Drawer */}
      {isDrawerOpen && (
        <>
          <div
            className="entity-detail-page__drawer-backdrop"
            role="button"
            tabIndex={-1}
            onClick={() => setIsDrawerOpen(false)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                setIsDrawerOpen(false);
              }
            }}
          />
          <div className="entity-detail-page__drawer">
            <div className="entity-detail-page__drawer-header">
              <h3 className="entity-detail-page__drawer-title">
                {t('library.details.details') || 'Details'}
              </h3>
              <button
                type="button"
                className="entity-detail-page__drawer-close"
                onClick={() => setIsDrawerOpen(false)}
              >
                &times;
              </button>
            </div>
            <div className="entity-detail-page__drawer-content">
              {/* Ratings section */}
              {(() => {
                const isSceneType = item?.type === 'scene';
                const hasImdb = !isSceneType && item?.rating_imdb != null && Number(item.rating_imdb) > 0;
                const hasTmdb = !isSceneType && item?.rating_tmdb != null && Number(item.rating_tmdb) > 0;
                const hasRotten = !isSceneType && item?.rating_rotten != null && item?.rating_rotten !== '';
                const hasMeta = !isSceneType && item?.rating_meta != null && Number(item.rating_meta) > 0;
                const hasPorndb = item?.rating_porndb != null && Number(item.rating_porndb) > 0;

                const ratings = [];
                if (hasImdb) ratings.push({ id: 'imdb', logo: '/rating/imdb.png', alt: 'IMDb', value: `${item.rating_imdb.toFixed(1)}/10` });
                if (hasTmdb) ratings.push({ id: 'tmdb', logo: '/rating/tmdb.png', alt: 'TMDb', value: `${item.rating_tmdb.toFixed(1)}/10` });
                if (hasRotten) ratings.push({ id: 'rotten', logo: '/rating/rottan_tomatoes.png', alt: 'Rotten Tomatoes', value: item.rating_rotten });
                if (hasMeta) ratings.push({ id: 'meta', logo: '/rating/metacritic.png', alt: 'Metacritic', value: `${item.rating_meta}/100` });
                if (hasPorndb) ratings.push({ id: 'porndb', logo: '/rating/theporndb.png', alt: 'ThePornDB', value: `${item.rating_porndb.toFixed(1)}/10` });

                if (ratings.length === 0) return null;

                return (
                  <div className="entity-detail-page__drawer-section">
                    <h4 className="entity-detail-page__drawer-section-title">
                      {t('library.details.ratingsSection') || 'Ratings'}
                    </h4>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-sm)', marginTop: 'var(--space-sm)' }}>
                      {ratings.map(rating => (
                        <div key={rating.id} style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid var(--color-border-default)', padding: '6px 12px', borderRadius: 'var(--radius-md, 8px)' }}>
                          <img src={rating.logo} alt={rating.alt} style={{ height: '18px', objectFit: 'contain' }} />
                          <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--color-text-primary)' }}>{rating.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Keywords section */}
              {item?.keywords && item.keywords.length > 0 && (
                <div className="entity-detail-page__drawer-section">
                  <h4 className="entity-detail-page__drawer-section-title">
                    {t('library.details.keywords') || 'Keywords'}
                  </h4>
                  <div className="bespoke-keywords-container is-expanded">
                    {item.keywords.map((kw, i) => (
                      <span key={i} className="bespoke-keyword-badge">
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Production Companies (for series only) */}
              {!isMovie && !isScene && item?.companies && item.companies.length > 0 && (
                <div className="entity-detail-page__drawer-section">
                  <h4 className="entity-detail-page__drawer-section-title">
                    {t('library.details.productionCompanies') || 'Production Companies'}
                  </h4>
                  <div className="bespoke-companies-body">
                    {item.companies.map((c, i) => (
                      <div key={i} className="bespoke-company-item" title={c.name}>
                        {c.logo_path ? (
                          <img src={resolveMediaImageUrl(c.logo_path, 'logo', API_BASE)} alt={c.name} className="bespoke-company-logo" />
                        ) : (
                          <span className="bespoke-company-name-only">{c.name}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Networks (for series only) */}
              {!isMovie && !isScene && item?.networks && item.networks.length > 0 && (
                <div className="entity-detail-page__drawer-section">
                  <h4 className="entity-detail-page__drawer-section-title">
                    {t('library.details.platformsNetworks') || 'Networks & Platforms'}
                  </h4>
                  <div className="bespoke-companies-body">
                    {item.networks.map((n, i) => (
                      <div key={i} className="bespoke-company-item" title={n.name}>
                        {n.logo_path ? (
                          <img src={resolveMediaImageUrl(n.logo_path, 'logo', API_BASE)} alt={n.name} className="bespoke-company-logo" />
                        ) : (
                          <span className="bespoke-company-name-only">{n.name}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Extras section */}
              {item?.extras && item.extras.length > 0 && <ExtrasPanel />}

              {/* Technical / Specs section */}
              {item?.technical && <TechnicalPanel />}
            </div>
          </div>
        </>
      )}
    </MediaDetailProvider>
  );
}

