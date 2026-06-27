import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import Pill from '@/ui/Pill';
import { Layers, User, PenLine, Sliders, Heart, Check, Minus, Plus, Star } from 'lucide-react';
import { OverviewContent } from './EntityDetailSections';
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
  const navigate = useNavigate();
  const [isAliasesExpanded, setIsAliasesExpanded] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isHoveringBar, setIsHoveringBar] = useState(false);

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

        {isPeople && (
          <div className="entity-detail-page__segmented-rating-container">
            <div
              className="entity-detail-page__segmented-rating-bar"
              onMouseMove={(e) => {
                setIsHoveringBar(true);
                handlePeopleRatingMouseMove(e);
              }}
              onMouseLeave={() => {
                setIsHoveringBar(false);
                handlePeopleRatingMouseLeave();
              }}
              onMouseUp={handlePeopleRatingClick}
              role="slider"
              tabIndex={0}
              aria-label={t('library.details.yourRating') || 'Your Rating'}
              aria-valuemin={0}
              aria-valuemax={10}
              aria-valuenow={displayRating ?? 0}
            >
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((val) => {
                let fill = 0;
                if (displayRating >= val) {
                  fill = 100;
                } else if (displayRating > val - 1) {
                  fill = (displayRating - (val - 1)) * 100;
                }
                return (
                  <div key={val} className="entity-detail-page__rating-segment">
                    <div 
                      className="entity-detail-page__rating-segment-fill" 
                      style={{ width: `${fill}%` }}
                    />
                  </div>
                );
              })}
            </div>
            <span className="entity-detail-page__segmented-rating-label">
              {isHoveringBar && displayRating !== null && displayRating !== undefined
                ? `${t('library.details.yourRating') || 'Your Rating'}: ${displayRating.toFixed(1)}`
                : (item?.user_rating !== null && item?.user_rating !== undefined
                  ? `${t('library.details.yourRating') || 'Your Rating'}: ${item.user_rating.toFixed(1)}`
                  : (t('library.details.yourRating') || 'Your Rating'))}
            </span>
          </div>
        )}
      </div>

      <div className="entity-detail-page__summary">
        <div className="entity-detail-page__headline-block">
          <div className="entity-detail-page__title-row">
            <h1 className="entity-detail-page__title">
              {item?.name || item?.title || (isPeople ? 'Unknown Person' : 'Unknown Collection')}
            </h1>
            {isPeople && (
              <div className="entity-detail-page__headline-actions">
                <button
                  type="button"
                  className={`entity-detail-page__headline-action entity-detail-page__headline-action--favorite ${item?.is_favorite ? 'is-active' : ''}`}
                  onClick={handleToggleFavorite}
                  title={t('library.details.favorite') || 'Favorite'}
                >
                  <Heart size={15} fill={item?.is_favorite ? 'currentColor' : 'none'} />
                </button>
                <button
                  type="button"
                  className={`entity-detail-page__headline-action entity-detail-page__headline-action--activate ${item?.is_active ? 'is-active' : ''}`}
                  onClick={handleToggleActive}
                  onMouseEnter={() => setIsActivateHovered(true)}
                  onMouseLeave={() => setIsActivateHovered(false)}
                  title={t('library.people.addPeopleBtn') || 'Activate'}
                >
                  {item?.is_active
                    ? (isActivateHovered ? <Minus size={15} /> : <Check size={15} />)
                    : <Plus size={15} />}
                </button>
                <button
                  type="button"
                  className="entity-detail-page__headline-action"
                  onClick={handleOpenReviewModal}
                  title={t('library.details.writeReview') || 'Write Review'}
                >
                  <PenLine size={15} />
                </button>
                {displayRating !== undefined && displayRating !== null && (
                  <div className="entity-detail-page__headline-rating-badge">
                    <Star size={12} fill="currentColor" style={{ marginRight: '4px' }} />
                    {displayRating.toFixed(1)}
                  </div>
                )}
              </div>
            )}
          </div>
          {metaPills.length > 0 && (() => {
            const placeOfBirthPill = metaPills.find(pill => pill.key === 'place-of-birth');
            const primaryMetaPills = metaPills.filter(pill => pill.key !== 'place-of-birth');
            return (
              <>
                {primaryMetaPills.length > 0 && (
                  <div className="entity-detail-page__meta-row">
                    {primaryMetaPills.map((metaItem) => (
                      <Pill key={metaItem.key} variant="meta">{metaItem.content}</Pill>
                    ))}
                  </div>
                )}
                {(placeOfBirthPill || isPeople) && (
                  <div className="entity-detail-page__meta-row entity-detail-page__meta-row--secondary">
                    {placeOfBirthPill && (
                      <Pill key={placeOfBirthPill.key} variant="meta">{placeOfBirthPill.content}</Pill>
                    )}
                    {isPeople && (
                      <button
                        type="button"
                        className="entity-detail-page__more-details-btn"
                        onClick={() => setIsDrawerOpen(true)}
                      >
                        <Sliders size={13} style={{ marginRight: '4px' }} />
                        {t('library.details.needMoreBtn') || 'Need more?'}
                      </button>
                    )}
                  </div>
                )}
              </>
            );
          })()}
          
          {/* Known For Grid */}
          {isPeople && item?.known_for?.length > 0 && (
            <div className="entity-detail-page__known-for-section">
              <div className="entity-detail-page__known-for-grid">
              {item.known_for.map((credit) => {
                const creditTitle = credit.title || credit.name || 'Unknown';
                const isClickable = true;
                const handleCardClick = () => {
                  const isScene = credit.media_type === 'scene' || credit.type === 'scene';
                  if (isScene) {
                    const itemSource = credit.source || (credit.rating_porndb ? 'porndb' : (item?.external_ids?.stashdb_id ? 'stashdb' : 'fansdb'));
                    const prefix = itemSource === 'porndb' || itemSource === 'theporndb' ? 'porndb' : (itemSource === 'fansdb' ? 'fansdb' : 'stash');
                    const sceneId = credit.in_library ? (credit.library_item_id || credit.id) : `${prefix}_${credit.stash_id || credit.id}`;
                    navigate(`/library/scene/${sceneId}`);
                    return;
                  }

                  const isTv = credit.media_type === 'tv' || credit.type === 'tv';
                  if (isTv) {
                    const tvId = credit.library_tv_tmdb_id || credit.tv_tmdb_id || credit.tmdb_id || credit.id;
                    navigate(`/library/tv/${tvId}`);
                    return;
                  }

                  const movieId = credit.in_library
                    ? (credit.library_item_id || credit.id)
                    : (credit.source === 'porndb' ? `porndb_${credit.tmdb_id || credit.id}` : `tmdb_${credit.tmdb_id || credit.id}`);
                  navigate(`/library/movie/${movieId}`);
                };
                
                return (
                  <div 
                    key={`${credit.id}-${credit.type || 'movie'}`} 
                    className="entity-detail-page__known-for-card is-clickable"
                    onClick={handleCardClick}
                    title={creditTitle}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        handleCardClick();
                      }
                    }}
                  >
                    <div className="entity-detail-page__known-for-poster-container">
                      {credit.poster_path ? (
                        <img
                          src={credit.poster_path}
                          alt={creditTitle}
                          className="entity-detail-page__known-for-poster"
                          loading="lazy"
                        />
                      ) : (
                        <div className="entity-detail-page__known-for-placeholder">
                          <Layers size={20} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>



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
