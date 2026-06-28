import { useParams, useNavigate } from 'react-router-dom';
import {
  Users, BadgeInfo, Layers3, Tags, Clapperboard,
  SlidersHorizontal, CheckCheck, Image as ImageIcon, Flame, ExternalLink
} from 'lucide-react';
import { useTranslation } from '@/providers/LanguageContext';
import { useUi } from '@/providers/UiProvider';
import { normalizeMediaType } from '@/lib/mediaTypes';
import UniversalImagePickerModal from './modals/UniversalImagePickerModal';

// Context
import { MediaDetailProvider } from './components/detail/MediaDetailContext';

// Hook
import useMediaDetail from './hooks/useMediaDetail';

import MediaHeaderInfo from './components/detail/MediaHeaderInfo';
import UserRatingSection from './components/detail/UserRatingSection';
import MediaOverview from './components/detail/MediaOverview';
import MediaActions from './components/detail/MediaActions';
import DetailPageShell from './components/detail/DetailPageShell';

// Panels
import SeasonsPanel from './components/detail/panels/SeasonsPanel';
import CastPanel from './components/detail/panels/CastPanel';
import DetailsPanel from './components/detail/panels/DetailsPanel';
import TechnicalPanel from './components/detail/panels/TechnicalPanel';
import ExtrasPanel from './components/detail/panels/ExtrasPanel';
import WatchedPanel from './components/detail/panels/WatchedPanel';
import TagsPanel from './components/detail/panels/TagsPanel';
import BackdropsPanel from './components/detail/panels/BackdropsPanel';
import PeaksPanel from './components/detail/panels/PeaksPanel';

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
    activePanel,
    isSideNavVisible,
    backdropUrl,
    posterUrl,
    item,
    isLoading,
    hasTechnicalPanel,
    isMovie,
    isScene,
    isOwned
  } = state;

  const {
    togglePanel,
    handleToggleSideNav
  } = actions;

  const handleOpenBackdropModal = () => {
    openModal({
      title: t('library.details.chooseBackdrop') || 'Choose Backdrop',
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

  const renderPanelContent = () => {
    if (!item) return null;

    switch (activePanel) {
      case 'seasons':
        return <SeasonsPanel />;
      case 'cast':
        return <CastPanel />;
      case 'details':
        return <DetailsPanel />;
      case 'technical':
        return <TechnicalPanel />;
      case 'extras':
        return <ExtrasPanel />;
      case 'watched':
        return <WatchedPanel />;
      case 'peaks':
        return <PeaksPanel />;
      case 'tags':
        return <TagsPanel />;
      default:
        return null;
    }
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
        activePanel={activePanel}
        isSideNavVisible={isSideNavVisible}
        onToggleSideNav={handleToggleSideNav}
        onClosePanel={() => togglePanel(null)}
        topRightControls={(
          <button
            type="button"
            onClick={handleOpenBackdropModal}
            className="media-detail-page__side-nav-toggle"
            title={t('library.details.backdrops') || 'Choose Backdrop'}
          >
            <ImageIcon size={18} />
          </button>
        )}
        renderPanelContent={renderPanelContent}
        sideNav={(
          <>
            {isMovie || isScene ? (
              <>
                {item?.type !== 'scene' && (
                  <button
                    onClick={() => togglePanel('details')}
                    className={`media-detail-page__side-nav-btn ${activePanel === 'details' ? 'active' : ''}`}
                    title={t('library.details.details') || 'Details'}
                  >
                    <BadgeInfo size={20} />
                  </button>
                )}
                {item?.cast && item.cast.length > 0 && (
                  <button
                    onClick={() => togglePanel('cast')}
                    className={`media-detail-page__side-nav-btn ${activePanel === 'cast' ? 'active' : ''}`}
                    title={t('library.details.cast') || 'Cast & Crew'}
                  >
                    <Users size={20} />
                  </button>
                )}
              </>
            ) : (
              <>
                {!isMovie && item?.seasons && item.seasons.length > 0 && (
                  <button
                    onClick={() => togglePanel('seasons')}
                    className={`media-detail-page__side-nav-btn ${activePanel === 'seasons' ? 'active' : ''}`}
                    title={t('library.details.seasons') || 'Seasons'}
                  >
                    <Layers3 size={20} />
                  </button>
                )}
                <button
                  onClick={() => togglePanel('details')}
                  className={`media-detail-page__side-nav-btn ${activePanel === 'details' ? 'active' : ''}`}
                  title={t('library.details.details') || 'Details'}
                >
                  <BadgeInfo size={20} />
                </button>
                {item?.cast && item.cast.length > 0 && (
                  <button
                    onClick={() => togglePanel('cast')}
                    className={`media-detail-page__side-nav-btn ${activePanel === 'cast' ? 'active' : ''}`}
                    title={t('library.details.cast') || 'Cast & Crew'}
                  >
                    <Users size={20} />
                  </button>
                )}
              </>
            )}

            <button
              onClick={() => togglePanel('tags')}
              className={`media-detail-page__side-nav-btn ${activePanel === 'tags' ? 'active' : ''}`}
              title={t('library.details.tagger') || 'Tagger'}
            >
              <Tags size={20} />
            </button>

            {item?.extras && item.extras.length > 0 && (
              <button
                onClick={() => togglePanel('extras')}
                className={`media-detail-page__side-nav-btn ${activePanel === 'extras' ? 'active' : ''}`}
                title={t('library.details.extras') || 'Film Extras'}
              >
                <Clapperboard size={20} />
              </button>
            )}

            {item && (
              <button
                onClick={() => togglePanel('watched')}
                className={`media-detail-page__side-nav-btn ${activePanel === 'watched' ? 'active' : ''}`}
                title={t('library.details.watchedPanel') || 'Watched Panel'}
              >
                <CheckCheck size={20} />
              </button>
            )}

            {item && item.is_adult && isOwned && (
              <button
                onClick={() => togglePanel('peaks')}
                className={`media-detail-page__side-nav-btn ${activePanel === 'peaks' ? 'active' : ''}`}
                title={t('library.details.peaksPanel') || 'Peaks Panel'}
              >
                <Flame size={20} />
              </button>
            )}

            {item?.external_ids?.stash_id && (
              <a
                href={
                  item.external_ids.source === 'fansdb'
                    ? `https://fansdb.cc/scenes/${item.external_ids.stash_id}`
                    : (item.external_ids.source === 'porndb' || item.external_ids.source === 'theporndb')
                    ? `https://theporndb.net/scenes/${item.external_ids.stash_id}`
                    : `https://stashdb.org/scenes/${item.external_ids.stash_id}`
                }
                target="_blank"
                rel="noopener noreferrer"
                className="media-detail-page__side-nav-btn"
                title={
                  item.external_ids.source === 'fansdb'
                    ? 'FansDB Link'
                    : (item.external_ids.source === 'porndb' || item.external_ids.source === 'theporndb')
                    ? 'ThePornDB Link'
                    : 'StashDB Link'
                }
              >
                <ExternalLink size={20} />
              </a>
            )}

            {hasTechnicalPanel && (
              <button
                onClick={() => togglePanel('technical')}
                className={`media-detail-page__side-nav-btn ${activePanel === 'technical' ? 'active' : ''}`}
                title={t('library.details.technicalInfo') || 'Technical Info'}
              >
                <SlidersHorizontal size={20} />
              </button>
            )}
          </>
        )}
      >
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
        <MediaActions />
      </DetailPageShell>
    </MediaDetailProvider>
  );
}
