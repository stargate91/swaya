import { useState, useMemo, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Users, BadgeInfo, Layers3, Tags, Clapperboard,
  SlidersHorizontal, CheckCheck, Image as ImageIcon, Flame, ExternalLink,
  Minus, Plus, ChevronUp, ChevronDown, ChevronLeft, ChevronRight
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
import SeasonsPanel from './components/detail/panels/SeasonsPanel';
import TechnicalPanel from './components/detail/panels/TechnicalPanel';
import ExtrasPanel from './components/detail/panels/ExtrasPanel';
import PeaksPanel from './components/detail/panels/PeaksPanel';
import BackdropsPanel from './components/detail/panels/BackdropsPanel';
import TagsPanel from './components/detail/panels/TagsPanel';
import WatchedPanel from './components/detail/panels/WatchedPanel';

function BespokeCastSection({ item, t, navigate }) {
  const settings = useMediaDetailContext()?.state?.settings;
  const isAdult = item.is_adult;
  const genderPref = settings?.adult_gender_preference;

  const filterPeople = (list) => {
    if (!list) return [];
    if (!isAdult || !genderPref || genderPref === 'all') return list;
    return list.filter(person => {
      if (genderPref === 'female') return person.gender === 1;
      if (genderPref === 'male') return person.gender === 2;
      return true;
    });
  };

  const filteredDirectors = filterPeople(item.directors);
  const filteredCast = filterPeople(item.cast);
  const resolvePersonAvatarUrl = (path) => resolveMediaImageUrl(path, 'person', API_BASE);

  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isShow = item?.type === 'tv' || item?.type === 'show';
  const isSmallScreen = windowWidth <= 1400;
  const maxTotal = isShow ? (isSmallScreen ? 6 : 7) : (isSmallScreen ? 12 : 14);

  const allPeople = useMemo(() => {
    const list = [];
    const maxDirectors = 2;

    // 1. Slice Directors (max 2)
    const slicedDirectors = filteredDirectors ? filteredDirectors.slice(0, maxDirectors) : [];
    slicedDirectors.forEach(p => {
      list.push({ ...p, displayRole: t('library.people.roles.director') || 'Director' });
    });

    // 2. Dynamically calculate remaining slots for Cast
    const remainingSlots = maxTotal - list.length;
    const slicedCast = filteredCast ? filteredCast.slice(0, remainingSlots) : [];
    slicedCast.forEach(p => {
      if (!list.some(x => x.id === p.id)) {
        list.push({ ...p, displayRole: p.character });
      }
    });

    return list;
  }, [filteredDirectors, filteredCast, maxTotal, t]);

  if (allPeople.length === 0) return null;

  return (
    <div className="dashboard-section">
      <h4 className="dashboard-section__title">{t('library.details.cast') || 'Cast & Crew'}</h4>
      <div className="dashboard-cast-carousel-container">
        <div className="dashboard-cast-grid">
          {allPeople.map(person => (
            <div
              key={person.id}
              className="dashboard-cast-card"
              onClick={() => navigate(`/library/people/${person.id}`, { state: { allowAdult: true } })}
            >
              <div className="dashboard-cast-card__avatar-wrapper">
                {person.profile_path ? (
                  <img
                    src={resolvePersonAvatarUrl(person.profile_path)}
                    alt={person.name}
                    className="dashboard-cast-card__avatar"
                  />
                ) : (
                  <div className="dashboard-cast-card__avatar-fallback">
                    <Users size={24} />
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
    </div>
  );
}

function BespokeDetailsSection({ item, t }) {
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

  const { state, actions } = detailState;
  const {
    backdropUrl,
    posterUrl,
    item,
    isLoading,
    hasTechnicalPanel,
    isMovie,
    isScene,
    isOwned
  } = state;

  const [isScrolled, setIsScrolled] = useState(false);
  const [isSocialExpanded, setIsSocialExpanded] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    setIsScrolled(false);
  }, [id]);

  useEffect(() => {
    const handleWheel = (e) => {
      if (Math.abs(e.deltaY) > 5) {
        if (e.deltaY > 0 && !isScrolled) {
          setIsScrolled(true);
        } else if (e.deltaY < 0 && isScrolled) {
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
    <MediaDetailProvider value={{ ...detailState, t, navigate, toast, type: normalizedType, id, handleOpenLogoModal, handleOpenPosterModal }}>
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

            {item && (
              <button
                type="button"
                onClick={() => {
                  openModal({
                    title: t('library.details.watchedPanel') || 'Watched Panel',
                    variant: 'wide',
                    content: (
                      <MediaDetailProvider value={{ ...detailState, t, navigate, toast, type: normalizedType, id }}>
                        <WatchedPanel />
                      </MediaDetailProvider>
                    ),
                  });
                }}
                className="media-detail-page__side-nav-toggle"
                title={t('library.details.watchedPanel') || 'Watched stats'}
              >
                <CheckCheck size={18} />
              </button>
            )}

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
            </div>
            <div className="media-detail-page__inline-side-col">
              {/* Empty for now */}
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
    </MediaDetailProvider>
  );
}

