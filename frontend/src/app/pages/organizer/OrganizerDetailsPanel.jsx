import { useState } from 'react';
import { createPortal } from 'react-dom';
import UtilityButton from '../../ui/UtilityButton';
import Button from '../../ui/Button';
import Tooltip from '../../ui/Tooltip';
import MediaCard from '../../ui/MediaCard';
import PosterCard from '../../ui/PosterCard';
import BackdropCard from '../../ui/BackdropCard';
import { ChevronLeft, ChevronRight, FileJson, Info, X } from 'lucide-react';
import { API_BASE } from '../../lib/backend';
import { resolveMediaImageUrl } from '@/lib/imageUrls';
import { useTranslation } from '../../providers/LanguageContext';
import { useUi } from '../../providers/UiProvider';
import { useFullMetadataQuery } from '../../queries';
import '../../styles/OrganizerDetailsPanel.css';

const resolveOrganizerImageUrl = (path) => resolveMediaImageUrl(path, 'poster', API_BASE);

export default function OrganizerDetailsPanel({
  activeImage,
  activeImageIndex,
  activeImages,
  activeRow,
  isDetailsCollapsed,
  onSelectImage,
  onToggleDetails,
  shouldShowDetailsCarousel,
  shouldShowDetailsPoster,
}) {
  const { t } = useTranslation();
  const { openModal, toast } = useUi();
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  const { refetch: refetchFullMetadata } = useFullMetadataQuery(activeRow?.itemId, undefined, {
    enabled: false,
  });

  const activeImageUrl = activeImage ? resolveOrganizerImageUrl(activeImage.path) : undefined;

  const buildInspectPayload = async () => {
    if (!activeRow) {
      return '';
    }

    if (activeRow.rawType === 'extra') {
      return JSON.stringify({
        kind: 'extra',
        summary: {
          id: activeRow.itemId,
          source: activeRow.source,
          target: activeRow.target,
          source_path: activeRow.sourcePath,
          target_path: activeRow.targetPath,
        },
        organizer: activeRow.rawPayload,
      }, null, 2);
    }

    const { data: metadata, error } = await refetchFullMetadata();
    if (error) {
      throw error;
    }

    return JSON.stringify({
      kind: activeRow.rawType,
      summary: {
        id: activeRow.itemId,
        source: activeRow.source,
        target: activeRow.target,
        source_path: activeRow.sourcePath,
        target_path: activeRow.targetPath,
        status: activeRow.rawStatus,
        action: activeRow.rawAction || null,
        has_collision: activeRow.hasCollision,
      },
      organizer: activeRow.rawPayload,
      metadata,
    }, null, 2);
  };

  const handleOpenLightbox = () => {
    if (!activeImageUrl) {
      return;
    }
    setIsLightboxOpen(true);
  };

  const handleSelectRelativeImage = (direction) => {
    if (!onSelectImage || activeImages.length <= 1) {
      return;
    }
    const nextIndex = (activeImageIndex + direction + activeImages.length) % activeImages.length;
    onSelectImage(nextIndex);
  };

  const handleOpenInspect = async () => {
    if (!activeRow) {
      return;
    }

    try {
      const inspectJson = await buildInspectPayload();

      const handleCopyInspect = async () => {
        try {
          await navigator.clipboard.writeText(inspectJson);
          toast(t('organizer.toasts.inspectCopySuccess'), 'success');
        } catch {
          toast(t('organizer.toasts.inspectCopyFailed'), 'danger');
        }
      };

      const handleDownloadInspect = () => {
        const blob = new Blob([inspectJson], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${activeRow.source || 'organizer-item'}.json`;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);
      };

      openModal({
        title: t('organizer.details.inspect.title'),
        description: t('organizer.details.inspect.description'),
        icon: FileJson,
        content: (
          <pre className="organizer-details__inspect-json">
            {inspectJson}
          </pre>
        ),
        footer: (
          <>
            <Button type="button" variant="secondary-neutral" onClick={handleCopyInspect}>
              {t('organizer.details.inspect.copy')}
            </Button>
            <Button type="button" variant="secondary-neutral" onClick={handleDownloadInspect}>
              {t('organizer.details.inspect.download')}
            </Button>
          </>
        ),
      });
    } catch (error) {
      toast(error.message || t('organizer.toasts.inspectLoadFailed'), 'danger');
    }
  };

  const renderImageNavigation = () => shouldShowDetailsCarousel ? (
    <>
      <button
        type="button"
        className="organizer-details__image-nav organizer-details__image-nav--prev"
        aria-label="Previous image"
        onClick={(event) => {
          event.stopPropagation();
          handleSelectRelativeImage(-1);
        }}
      >
        <ChevronLeft size={18} />
      </button>
      <button
        type="button"
        className="organizer-details__image-nav organizer-details__image-nav--next"
        aria-label="Next image"
        onClick={(event) => {
          event.stopPropagation();
          handleSelectRelativeImage(1);
        }}
      >
        <ChevronRight size={18} />
      </button>
      <div className="organizer-details__image-count" aria-hidden="true">
        {activeImageIndex + 1} / {activeImages.length}
      </div>
    </>
  ) : null;

  const lightbox = isLightboxOpen ? (
    <div
      className="organizer-details__lightbox"
      role="button"
      tabIndex={0}
      aria-label={t('common.close') || 'Close image preview'}
      onClick={() => setIsLightboxOpen(false)}
      onKeyDown={(event) => {
        if (event.key === 'Escape' || event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          setIsLightboxOpen(false);
        }
      }}
    >
      <button
        type="button"
        className="organizer-details__lightbox-close"
        aria-label={t('common.close') || 'Close image preview'}
        onClick={(event) => {
          event.stopPropagation();
          setIsLightboxOpen(false);
        }}
      >
        <X size={18} />
      </button>
      <img
        src={activeImageUrl}
        alt={activeRow?.source || 'Organizer preview'}
        className="organizer-details__lightbox-image"
        onClick={(event) => event.stopPropagation()}
      />
    </div>
  ) : null;

  return (
    <aside className="organizer-details" aria-label={t('organizer.details.title')}>
      <div className="organizer-details__toggle-row">
        <Tooltip content={isDetailsCollapsed ? t('organizer.details.expand') : t('organizer.details.collapse')} side="left">
          <UtilityButton
            type="button"
            className="organizer-details__toggle"
            size="sm"
            aria-label={isDetailsCollapsed ? t('organizer.details.expand') : t('organizer.details.collapse')}
            onClick={onToggleDetails}
          >
            {isDetailsCollapsed ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
          </UtilityButton>
        </Tooltip>
      </div>

      <div className="organizer-details__sticky-container">
        <div className="organizer-details__panel">
          {activeRow ? (
            <>
              <div className="organizer-details__header">
                <span className="organizer-details__title">{t('organizer.details.title')}</span>
              </div>
              <div className="organizer-details__content">
                {shouldShowDetailsPoster ? (
                  activeRow?.rawType === 'scene' ? (
                    <BackdropCard
                      className="organizer-details__backdrop-card"
                      imageUrl={activeImageUrl}
                      onClick={handleOpenLightbox}
                    >
                      {renderImageNavigation()}
                    </BackdropCard>
                  ) : (
                    <PosterCard
                      className={`organizer-details__poster-card${activeImageUrl ? ' has-image' : ''}`}
                      imageUrl={activeImageUrl}
                      placeholderText={!activeImage ? t('organizer.details.posterPlaceholder') : undefined}
                      onClick={activeImageUrl ? handleOpenLightbox : undefined}
                    >
                      {renderImageNavigation()}
                    </PosterCard>
                  )
                ) : null}
                <MediaCard className="organizer-details__field">
                  <span className="organizer-details__label">{t('organizer.details.fields.source')}</span>
                  <span className="organizer-details__value" title={activeRow.sourcePath}>{activeRow.sourcePath}</span>
                </MediaCard>
                {(() => {
                  const unmatchedStatuses = ['new', 'no_match', 'uncertain', 'multiple', 'error'];
                  const isUnmatchedExtra = activeRow.rawType === 'extra' && activeRow.parentStatus && unmatchedStatuses.includes(activeRow.parentStatus.toLowerCase());
                  const isUnmatchedMedia = activeRow.rawType !== 'extra' && unmatchedStatuses.includes(activeRow.rawStatus);

                  if (isUnmatchedMedia || isUnmatchedExtra) {
                    return null;
                  }

                  return (
                    <MediaCard className="organizer-details__field">
                      <span className="organizer-details__label">{t('organizer.details.fields.target')}</span>
                      <span className="organizer-details__value" title={activeRow.targetPath}>{activeRow.targetPath}</span>
                    </MediaCard>
                  );
                })()}
                <div className="organizer-details__actions">
                  <Button
                    type="button"
                    variant="secondary-neutral"
                    size="sm"
                    className="organizer-details__inspect-button"
                    onClick={handleOpenInspect}
                  >
                    {t('organizer.details.inspect.open')}
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="organizer-details__empty-state">
              <div className="organizer-details__empty-icon-wrapper">
                <Info className="organizer-details__empty-icon" size={24} />
              </div>
              <h3 className="organizer-details__empty-title">{t('organizer.details.title')}</h3>
              <p className="organizer-details__empty-text">{t('organizer.details.empty')}</p>
            </div>
          )}
        </div>
      </div>
      {lightbox && typeof document !== 'undefined' ? createPortal(lightbox, document.body) : null}
    </aside>
  );
}
