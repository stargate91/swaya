import Pill from '@/ui/Pill';
import { Layers, User, PenLine } from 'lucide-react';
import { OverviewContent } from './EntityDetailSections';
import PersonRatingControls from './PersonRatingControls';
import Tooltip from '@/ui/Tooltip';
import './EntityDetailHeroSection.css';

export default function EntityDetailHeroSection({
  isPeople,
  item,
  mediaUrl,
  profileLinks,
  socialLinks = [],
  metaPills,
  extraMetaPills,
  overviewText,
  overviewTitle,
  overviewEmptyText,
  displayRating,
  isActivateHovered,
  starsStyleSheetText,
  t,
  openModal,
  setIsActivateHovered,
  handleToggleFavorite,
  handleToggleActive,
  handleOpenReviewModal,
  handlePeopleRatingMouseMove,
  handlePeopleRatingMouseLeave,
  handlePeopleRatingClick,
  onMediaCardClick,
}) {
  return (
    <section className="entity-detail-page__hero-grid">
      <div className="entity-detail-page__media-column">
        {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions */}
        <div
          className={`entity-detail-page__media-card ${isPeople ? 'entity-detail-page__media-card--profile' : ''} entity-detail-page__media-card--editable`}
          onClick={onMediaCardClick}
          title={isPeople ? (t('library.details.changeProfile') || 'Change Profile Picture') : (t('library.details.changePoster') || 'Change Poster')}
        >
          {mediaUrl ? (
            <img
              src={mediaUrl}
              alt={item?.name || item?.title || 'Detail artwork'}
              className="entity-detail-page__media-image"
            />
          ) : (
            <div className="entity-detail-page__media-placeholder">
              {isPeople ? <User size={44} /> : <Layers size={44} />}
            </div>
          )}



          <button
            type="button"
            className="entity-detail-page__media-edit-badge"
            onClick={(event) => {
              event.stopPropagation();
              onMediaCardClick?.();
            }}
            title={isPeople ? (t('library.details.changeProfile') || 'Change Profile Picture') : (t('library.details.changePoster') || 'Change Poster')}
            aria-label={isPeople ? (t('library.details.changeProfile') || 'Change Profile Picture') : (t('library.details.changePoster') || 'Change Poster')}
          >
            <PenLine size={14} />
          </button>
        </div>
      </div>

      <div className="entity-detail-page__summary">
        <div className="entity-detail-page__headline-block">
          <h1 className="entity-detail-page__title">
            {item?.name || item?.title || (isPeople ? 'Unknown Person' : 'Unknown Collection')}
          </h1>
          {isPeople && item?.alternate_names?.length > 0 && (
            <div className="entity-detail-page__alternate-names">
              {item.alternate_names.join(', ')}
            </div>
          )}

          {metaPills.length > 0 && (
            <div className="entity-detail-page__meta-row">
              {metaPills.map((metaItem) => (
                <Pill key={metaItem.key} variant="meta">{metaItem.content}</Pill>
              ))}
            </div>
          )}

          {isPeople && extraMetaPills?.length > 0 && (
            <div className="entity-detail-page__meta-row entity-detail-page__meta-row--extra" style={{ marginTop: 'calc(-1 * var(--space-sm) + 2px)' }}>
              {extraMetaPills.map((metaItem) => {
                const pill = <Pill variant="meta">{metaItem.content}</Pill>;
                if (metaItem.tooltip) {
                  return (
                    <Tooltip key={metaItem.key} content={metaItem.tooltip} side="top">
                      {pill}
                    </Tooltip>
                  );
                }
                return <span key={metaItem.key}>{pill}</span>;
              })}
            </div>
          )}
        </div>

        {isPeople && (
          <PersonRatingControls
            item={item}
            displayRating={displayRating}
            isActivateHovered={isActivateHovered}
            starsStyleSheetText={starsStyleSheetText}
            t={t}
            setIsActivateHovered={setIsActivateHovered}
            handleToggleFavorite={handleToggleFavorite}
            handleToggleActive={handleToggleActive}
            handleOpenReviewModal={handleOpenReviewModal}
            handlePeopleRatingMouseMove={handlePeopleRatingMouseMove}
            handlePeopleRatingMouseLeave={handlePeopleRatingMouseLeave}
            handlePeopleRatingClick={handlePeopleRatingClick}
          />
        )}

        {overviewText && (
          <div className="entity-detail-page__summary-layout">
            <div className="entity-detail-page__summary-text">
              <OverviewContent
                text={overviewText}
                title={overviewTitle}
                emptyText={overviewEmptyText}
                t={t}
                openModal={openModal}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
