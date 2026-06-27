import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import Pill from '@/ui/Pill';
import { Layers, User, PenLine, Sliders, Heart, Check, Minus, Plus, Star, ChevronDown, Info, Bookmark } from 'lucide-react';
import { OverviewContent } from './EntityDetailSections';
import Tooltip from '@/ui/Tooltip';
import './EntityDetailHeroSection.css';

export default function EntityDetailHeroSection({
  isPeople,
  item,
  isScrolled,
  onScrollArrowClick,
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

  const candidateAliases = (isPeople && item?.alternate_names) ? item.alternate_names.slice(0, 4) : [];
  let accumulatedLength = 0;
  const sidebarAliases = candidateAliases.map((alias, idx) => {
    accumulatedLength += alias.length + (idx > 0 ? 2 : 0);
    const isTruncated = accumulatedLength > 20 || idx >= 2;
    return {
      original: alias,
      isTruncated
    };
  });

  const drawerAliases = [
    ...sidebarAliases.filter(a => a.isTruncated).map(a => a.original),
    ...((isPeople && item?.alternate_names) ? item.alternate_names.slice(4) : [])
  ];

  const countryISO = (() => {
    if (!isPeople || !item?.place_of_birth) return null;
    const place = item.place_of_birth.trim().toUpperCase();
    const parts = place.split(',').map(p => p.trim());
    const lastPart = parts[parts.length - 1];
    
    const map = {
      'USA': 'US', 'UNITED STATES': 'US', 'UNITED STATES OF AMERICA': 'US',
      'HUNGARY': 'HU', 'MAGYARORSZÁG': 'HU',
      'GERMANY': 'DE', 'DEUTSCHLAND': 'DE',
      'UNITED KINGDOM': 'GB', 'UK': 'GB', 'GREAT BRITAIN': 'GB', 'ENGLAND': 'GB',
      'CANADA': 'CA', 'FRANCE': 'FR', 'SPAIN': 'ES', 'ITALY': 'IT',
      'RUSSIA': 'RU', 'RUSSIAN FEDERATION': 'RU',
      'AUSTRALIA': 'AU', 'JAPAN': 'JP', 'BRAZIL': 'BR',
      'NETHERLANDS': 'NL', 'POLAND': 'PL', 'UKRAINE': 'UA', 'SWEDEN': 'SE',
      'CZECH REPUBLIC': 'CZ', 'CZECHIA': 'CZ', 'SLOVAKIA': 'SK', 'AUSTRIA': 'AT',
      'CUBA': 'CU', 'COLOMBIA': 'CO', 'MEXICO': 'MX', 'ROMANIA': 'RO',
      'ARGENTINA': 'AR', 'BELGIUM': 'BE', 'SWITZERLAND': 'CH', 'CHINA': 'CN',
      'SOUTH KOREA': 'KR', 'KOREA': 'KR', 'PHILIPPINES': 'PH', 'THAILAND': 'TH',
      'VIETNAM': 'VN', 'NORWAY': 'NO', 'DENMARK': 'DK', 'FINLAND': 'FI',
      'BULGARIA': 'BG', 'GREECE': 'GR', 'TURKEY': 'TR', 'PORTUGAL': 'PT',
      'SOUTH AFRICA': 'ZA', 'NEW ZEALAND': 'NZ', 'VENEZUELA': 'VE',
    };
    return map[lastPart] || (lastPart.length === 2 ? lastPart : null);
  })();

  const flagEmoji = (() => {
    if (!countryISO) return '';
    const codePoints = countryISO
      .split('')
      .map(char => 127397 + char.charCodeAt(0));
    try {
      return String.fromCodePoint(...codePoints);
    } catch (e) {
      return '';
    }
  })();

  return (
    <div className="entity-detail-page__hero-section-wrapper">
      <section className="entity-detail-page__hero-grid">
        <div className="entity-detail-page__media-column">
          {/* 1. Elegant Header (Name & Aliases) */}
          <div className="entity-detail-page__headline-block">
            <h1 className="entity-detail-page__title">
              {item?.name || item?.title || (isPeople ? 'Unknown Person' : 'Unknown Collection')}
            </h1>
            {candidateAliases.length > 0 && (
              <span className="entity-detail-page__sidebar-aliases">
                {candidateAliases.join(', ')}
              </span>
            )}
          </div>

          {/* 2. Visual Centerpiece (Profile Picture) */}
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

            {/* Subtle Country Flag Badge overlay */}
            {flagEmoji && (
              <div 
                className="entity-detail-page__media-flag-badge"
                title={item.place_of_birth}
              >
                {flagEmoji}
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

          {/* 3. Integrated Sidebar Action Toolbar (Clean 3-button row, no rating pill) */}
          {isPeople && (
            <div className="entity-detail-page__sidebar-actions">
              <button
                type="button"
                className={`entity-detail-page__sidebar-action entity-detail-page__sidebar-action--favorite ${item?.is_favorite ? 'is-active' : ''}`}
                onClick={handleToggleFavorite}
                title={t('library.details.favorite') || 'Favorite'}
              >
                <Heart size={15} fill={item?.is_favorite ? 'currentColor' : 'none'} />
              </button>
              <button
                type="button"
                className={`entity-detail-page__sidebar-action entity-detail-page__sidebar-action--activate ${item?.is_active ? 'is-active' : ''}`}
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
                className="entity-detail-page__sidebar-action"
                onClick={handleOpenReviewModal}
                title={t('library.details.writeReview') || 'Write Review'}
              >
                <PenLine size={15} />
              </button>
            </div>
          )}

          {/* 4. Interactive rating bar */}
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

          {/* 5. Elegant 2x2 Metadata Table */}
          {isPeople && (() => {
            const calculateAge = (birthdayStr) => {
              if (!birthdayStr) return '';
              const birthDate = new Date(birthdayStr);
              if (isNaN(birthDate.getTime())) return '';
              const today = new Date();
              let age = today.getFullYear() - birthDate.getFullYear();
              const m = today.getMonth() - birthDate.getMonth();
              if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
                age--;
              }
              return t('library.details.yearsOld', { count: age, defaultValue: `${age} Years Old` });
            };

            const getGenderLabel = (gender) => {
              if (gender === 1 || gender === '1') return t('library.details.female') || 'Female';
              if (gender === 2 || gender === '2') return t('library.details.male') || 'Male';
              if (gender === 3 || gender === '3') return t('library.details.nonBinary') || 'Non-binary';
              return null;
            };

            const genderVal = getGenderLabel(item?.gender);
            const deptVal = item?.known_for_department || (item?.is_adult ? 'Performer' : 'Artist');

            return (
              <div className="entity-detail-page__sidebar-info-table">
                <div className="entity-detail-page__info-row">
                  <div className="entity-detail-page__info-cell">
                    <span className="entity-detail-page__info-label">{t('library.details.gender') || 'Gender'}</span>
                    <span className="entity-detail-page__info-value">{genderVal || '—'}</span>
                  </div>
                  <div className="entity-detail-page__info-cell">
                    <span className="entity-detail-page__info-label">{t('library.details.role') || 'Role'}</span>
                    <span className="entity-detail-page__info-value">{deptVal}</span>
                  </div>
                </div>
                <div className="entity-detail-page__info-row">
                  <div className="entity-detail-page__info-cell">
                    <span className="entity-detail-page__info-label">{t('library.details.born') || 'Born'}</span>
                    <span className="entity-detail-page__info-value">{item?.birthday || '—'}</span>
                  </div>
                  <div className="entity-detail-page__info-cell">
                    <span className="entity-detail-page__info-label">{t('library.details.age') || 'Age'}</span>
                    <span className="entity-detail-page__info-value">
                      {item?.birthday ? calculateAge(item.birthday) : '—'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Need More / Biography Drawer Trigger */}
          {isPeople && (
            <button
              type="button"
              className="entity-detail-page__sidebar-more-btn"
              onClick={() => setIsDrawerOpen(true)}
            >
              <Info size={13} style={{ marginRight: '6px' }} />
              {t('library.details.needMoreBtn') || 'Biography & Details'}
            </button>
          )}
        </div>

        {/* Right column containing Known For aligned to the bottom */}
        <div className="entity-detail-page__summary">
          {isPeople && item?.known_for?.length > 0 && (
            <div className="entity-detail-page__known-for-section">
              <h3 className="entity-detail-page__known-for-title">
                {t('library.details.knownForTitle') || 'Known For'}
              </h3>
              <div className="entity-detail-page__known-for-grid">
                {item.known_for.map((credit) => {
                  const creditTitle = credit.title || credit.name || 'Unknown';
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
                        {/* Bookmark badge to represent "In Library" / "Owned" */}
                        {credit.in_library && (
                          <div className="entity-detail-page__known-for-library-badge" title={t('library.details.inLibrary') || 'In Library'}>
                            <Bookmark size={10} />
                          </div>
                        )}
                      </div>
                      <span className="entity-detail-page__known-for-card-title">{creditTitle}</span>
                      {credit.character && (
                        <span className="entity-detail-page__known-for-card-role">{credit.character}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </section>

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
        const hasAnySpecs = item?.height || item?.weight || item?.measurements || item?.breast_type || item?.hair_color || item?.eye_color || item?.ethnicity || item?.tattoos || item?.piercings || item?.career_start_year || item?.place_of_birth;

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
                {drawerAliases.length > 0 && (
                  <div className="entity-detail-page__drawer-section">
                    <h4 className="entity-detail-page__drawer-section-title">
                      {t('library.details.alsoKnownAs') || 'Also known as'}
                    </h4>
                    <div className="entity-detail-page__drawer-aliases-text">
                      {drawerAliases.join(', ')}
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
                      {item.place_of_birth && (
                        <div className="entity-detail-page__specs-item entity-detail-page__specs-item--full">
                          <span className="entity-detail-page__specs-label">Place of Birth</span>
                          <span className="entity-detail-page__specs-value">{item.place_of_birth}</span>
                        </div>
                      )}
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
  );
}
