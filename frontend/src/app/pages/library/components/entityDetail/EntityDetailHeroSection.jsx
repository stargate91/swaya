import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import Pill from '@/ui/Pill';
import { Layers, User, PenLine, Sliders } from 'lucide-react';
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
  const [isAliasesExpanded, setIsAliasesExpanded] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const aliasLimit = 4;
  const hasMoreAliases = item?.alternate_names?.length > aliasLimit;
  const displayedAliases = (isPeople && item?.alternate_names)
    ? item.alternate_names.slice(0, aliasLimit)
    : [];
  const extraAliases = (isPeople && item?.alternate_names)
    ? item.alternate_names.slice(aliasLimit)
    : [];

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
          {metaPills.length > 0 && (
            <div className="entity-detail-page__meta-row">
              {metaPills.map((metaItem) => (
                <Pill key={metaItem.key} variant="meta">{metaItem.content}</Pill>
              ))}
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

        {isPeople && (
          <div className="entity-detail-page__more-details-container">
            <button
              type="button"
              className="entity-detail-page__more-details-btn"
              onClick={() => setIsDrawerOpen(true)}
            >
              <Sliders size={13} style={{ marginRight: '4px' }} />
              {t('library.details.needMoreBtn') || 'Need more?'}
            </button>
          </div>
        )}



        {isDrawerOpen && (() => {
          const toTitleCase = (str) => {
            if (!str) return '';
            return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
          };

          const formatListAttr = (val) => {
            if (!val) return null;
            if (Array.isArray(val)) {
              if (val.length === 0) return null;
              const locations = val.map(i => i.location || i.description).filter(Boolean);
              if (locations.length === 0) return 'Yes';
              return toTitleCase(locations.join(', '));
            }
            if (typeof val === 'string') {
              const formatted = toTitleCase(val);
              if (formatted === 'No Piercings' || formatted === 'No Tattoos') return 'No';
              return formatted;
            }
            return null;
          };

          const tattooVal = formatListAttr(item.tattoos);
          const piercingVal = formatListAttr(item.piercings);
          const hasAnySpecs = item?.height || item?.weight || item?.measurements || item?.breast_type || item?.hair_color || item?.eye_color || item?.ethnicity || item?.tattoos || item?.piercings || item?.career_start_year;

          return createPortal(
            <>
              {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
              <div 
                className="entity-detail-page__drawer-backdrop" 
                onClick={() => setIsDrawerOpen(false)}
              />
              <div className="entity-detail-page__drawer">
                <div className="entity-detail-page__drawer-header">
                  <h3 className="entity-detail-page__drawer-title">{item?.name || overviewTitle}</h3>
                  <button 
                    type="button" 
                    className="entity-detail-page__drawer-close" 
                    onClick={() => setIsDrawerOpen(false)}
                  >
                    &times;
                  </button>
                </div>
                <div className="entity-detail-page__drawer-content">
                  {/* Section 1: Alternate Names */}
                  {item?.alternate_names?.length > 0 && (
                    <div className="entity-detail-page__drawer-section">
                      <h4 className="entity-detail-page__drawer-section-title">
                        {t('library.details.alsoKnownAs') || 'Also known as'}
                      </h4>
                      <div className="entity-detail-page__drawer-aliases-text">
                        {item.alternate_names.join(', ')}
                      </div>
                    </div>
                  )}

                  {/* Section 2: Physical Specs */}
                  {hasAnySpecs && (
                    <div className="entity-detail-page__drawer-section">
                      <h4 className="entity-detail-page__drawer-section-title">
                        {t('library.details.specsTitle') || 'Physical Specs'}
                      </h4>
                      <div className="entity-detail-page__drawer-specs-grid">
                        {item.career_start_year && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Active Years</span>
                            <span className="entity-detail-page__specs-value">
                              {item.career_start_year} - {item.career_end_year || 'Present'}
                            </span>
                          </div>
                        )}
                        {item.height && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Height</span>
                            <span className="entity-detail-page__specs-value">{item.height} cm</span>
                          </div>
                        )}
                        {item.weight && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Weight</span>
                            <span className="entity-detail-page__specs-value">{item.weight} kg</span>
                          </div>
                        )}
                        {item.measurements && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Measurements</span>
                            <span className="entity-detail-page__specs-value">{item.measurements}</span>
                          </div>
                        )}
                        {item.breast_type && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Breast Type</span>
                            <span className="entity-detail-page__specs-value">{toTitleCase(item.breast_type)}</span>
                          </div>
                        )}
                        {item.hair_color && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Hair Color</span>
                            <span className="entity-detail-page__specs-value">{toTitleCase(item.hair_color)}</span>
                          </div>
                        )}
                        {item.eye_color && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Eye Color</span>
                            <span className="entity-detail-page__specs-value">{toTitleCase(item.eye_color)}</span>
                          </div>
                        )}
                        {item.ethnicity && (
                          <div className="entity-detail-page__specs-item">
                            <span className="entity-detail-page__specs-label">Ethnicity</span>
                            <span className="entity-detail-page__specs-value">{toTitleCase(item.ethnicity)}</span>
                          </div>
                        )}
                        {tattooVal && (
                          <div className="entity-detail-page__specs-item entity-detail-page__specs-item--full">
                            <span className="entity-detail-page__specs-label">Tattoos</span>
                            <span className="entity-detail-page__specs-value">{tattooVal}</span>
                          </div>
                        )}
                        {piercingVal && (
                          <div className="entity-detail-page__specs-item entity-detail-page__specs-item--full">
                            <span className="entity-detail-page__specs-label">Piercings</span>
                            <span className="entity-detail-page__specs-value">{piercingVal}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Section 3: Biography */}
                  {overviewText && (
                    <div className="entity-detail-page__drawer-section">
                      <h4 className="entity-detail-page__drawer-section-title">
                        {t('library.details.biographyTitle') || 'Biography'}
                      </h4>
                      <div className="entity-detail-page__drawer-bio">
                        {overviewText.split(/\n{2,}/).map((paragraph, index) => (
                          <p key={index} className="entity-detail-page__drawer-paragraph">{paragraph}</p>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>,
            document.body
          );
        })()}
      </div>
    </section>
  );
}
