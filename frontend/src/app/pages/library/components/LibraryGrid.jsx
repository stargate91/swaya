import { useState, useEffect, useMemo, useCallback, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import './entityDetail/EntityDetailHeroSection.css';
import { usePlayMediaMutation, useSettingsQuery } from '@/queries';
import api from '@/lib/api';
import Badge from '@/ui/Badge';
import PosterGrid from '@/ui/PosterGrid';
import PosterCard from '@/ui/PosterCard';
import EmptyState from '@/ui/EmptyState';
import Button from '@/ui/Button';
import IconButton from '@/ui/IconButton';
import NavButton from '@/ui/NavButton';
import { useUi } from '@/providers/UiProvider';
import UniversalImagePickerModal from '../modals/UniversalImagePickerModal';
import {
  getPosterImagePath,
  getProfileImagePath,
  getTvPosterImagePath,
  resolveMediaImageUrl,
} from '@/lib/imageUrls';
import {
  getLibraryTagBucketKeys,
  isLibraryMovieTab,
  isLibraryPeopleTab,
  isLibraryTvTab,
  isLibraryTagsTab,
  isLibraryScenesTab,
} from '@/lib/libraryTabs';
import { isMovieMediaType, isPersonMediaType, isTvLikeMediaType, isSceneMediaType } from '@/lib/mediaTypes';
import { Heart, Pencil, Play, Plus, Trash2, UserPlus } from 'lucide-react';

const renderUserRatingBadge = (item) => {
  const rating = Number(item?.user_rating);
  if (!Number.isFinite(rating) || rating <= 0) return null;
  const label = Number.isInteger(rating) ? String(rating) : rating.toFixed(1);
  return (
    <Badge className="ui-poster-card__user-rating-badge">
      {label}
    </Badge>
  );
};

const renderFavoriteBadge = (item, t) => {
  if (!item?.is_favorite) return null;
  return (
    <div
      className="ui-poster-card__favorite-badge"
      title={t('library.filter.favorite') || 'Favourite'}
      aria-label={t('library.filter.favorite') || 'Favourite'}
    >
      <Heart size={14} fill="currentColor" strokeWidth={2.2} />
    </div>
  );
};

const LibraryPosterCard = memo(({
  item,
  index,
  resolvedTab,
  isCollections,
  emptyIcon,
  t,
  playMutationPending,
  onItemClick,
  onPlayOverlayClick,
  onEditImageClick,
  settings,
}) => {
  const navigate = useNavigate();
  const isLibraryPeople = isLibraryPeopleTab(resolvedTab);
  const isLibraryTv = isLibraryTvTab(resolvedTab);
  const isLibraryMovie = isLibraryMovieTab(resolvedTab);

  const isLibraryScenes = isLibraryScenesTab(resolvedTab);

  const resolvePosterUrl = (path) => resolveMediaImageUrl(path, 'poster');

  // Compute props stably
  let title = item.title;
  let subtitle;
  let imageUrl;
  let ratingImdb = item.rating_imdb;
  let ratingTmdb = item.rating;
  let ratingPorndb;
  const isScene = isSceneMediaType(item.type) || isLibraryScenes;

  if (isScene || isLibraryPeople) {
    ratingTmdb = undefined;
    ratingImdb = undefined;
    if (!isLibraryPeople) {
      ratingPorndb = item.rating_porndb;
    } else {
      ratingPorndb = undefined;
    }
  } else {
    ratingPorndb = item.rating_porndb;
  }

  let topRightAction;
  let badge = renderUserRatingBadge(item);
  let topRightBadge = null;
  let playOverlay = null;
  let className = '';

  const handleEditClick = (e) => {
    e.stopPropagation();
    onEditImageClick(item);
  };

  const editButton = (
    <button
      type="button"
      className="ui-poster-card__edit-badge"
      title={isLibraryPeople
        ? (t('library.details.changeProfile') || 'Change Profile Picture')
        : (t('library.details.changePoster') || 'Change Poster')}
      aria-label={isLibraryPeople
        ? (t('library.details.changeProfile') || 'Change Profile Picture')
        : (t('library.details.changePoster') || 'Change Poster')}
      onClick={handleEditClick}
    >
      <Pencil size={14} />
    </button>
  );

  if (isCollections) {
    title = item.name || item.title;
    subtitle = t('library.collections.partsCount', { owned: item.owned_count, total: item.total_count });
    imageUrl = resolvePosterUrl(getPosterImagePath(item));
    topRightAction = editButton;
  } else if (isLibraryPeople) {
    title = item.name || item.title;
    subtitle = item.people_role ? t(`library.people.roles.${item.people_role}`, { defaultValue: item.people_role }) : '';
    imageUrl = resolvePosterUrl(getProfileImagePath(item));
    className = 'library-person-card';
    topRightBadge = renderFavoriteBadge(item, t);
    topRightAction = editButton;
  } else if (isLibraryScenes) {
    const displayDate = item.release_date ? item.release_date.substring(0, 10) : item.year;
    imageUrl = resolvePosterUrl(item.backdrop_path) || item.displayPosterRemote || resolvePosterUrl(getPosterImagePath(item));
    className = 'library-scene-card';
    topRightAction = editButton;

    const genderPref = settings?.adult_gender_preference;
    const allPeople = item.people || [];
    const filteredPeople = genderPref && genderPref !== 'all'
      ? allPeople.filter(p => {
        if (genderPref === 'female') return p.gender === 1;
        if (genderPref === 'male') return p.gender === 2;
        return true;
      })
      : allPeople;
    const performers = filteredPeople.slice(0, 4);

    subtitle = (
      <div className="library-scene-card__subtitle-inner">
        <span className="library-scene-card__performers">
          {performers.map((p, idx) => (
            <span key={p.id}>
              {idx > 0 && ', '}
              <span
                role="button"
                tabIndex={0}
                className="library-scene-card__performer-link"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/library/people/${p.id}`, { state: { allowAdult: true } });
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.stopPropagation();
                    navigate(`/library/people/${p.id}`, { state: { allowAdult: true } });
                  }
                }}
              >
                {p.name}
              </span>
            </span>
          ))}
        </span>
        {displayDate && <span className="library-scene-card__date">{displayDate}</span>}
      </div>
    );

    if (item.in_library !== false) {
      const playTitle = ((item.resume_position || 0) > 0 ? (t('library.details.resume') || 'Resume') : (t('library.details.play') || 'Play'));
      playOverlay = {
        onClick: (event) => {
          onPlayOverlayClick(event, item);
        },
        title: playTitle,
        label: playTitle,
        disabled: playMutationPending,
        icon: <Play size={12} fill="currentColor" />,
      };
    }
  } else {
    const subtitleParts = [];
    const displayDate = (isLibraryMovie && item.release_date)
      ? item.release_date.substring(0, 4)
      : item.year;
    if (displayDate) subtitleParts.push(displayDate);
    if (item.info) {
      subtitleParts.push(item.info);
    }
    subtitle = subtitleParts.join(' • ');
    imageUrl = resolvePosterUrl(isLibraryTv ? getTvPosterImagePath(item) : getPosterImagePath(item));
    topRightAction = editButton;

    if (item.in_library !== false && (isLibraryMovie || isLibraryTv)) {
      const playTitle = isLibraryTv
        ? (t('library.details.continue') || 'Continue')
        : ((item.resume_position || 0) > 0 ? (t('library.details.resume') || 'Resume') : (t('library.details.play') || 'Play'));

      playOverlay = {
        onClick: (event) => {
          onPlayOverlayClick(event, item);
        },
        title: playTitle,
        label: playTitle,
        disabled: playMutationPending,
        icon: <Play size={12} fill="currentColor" />,
      };
    }
  }

  return (
    <PosterCard
      customStyle={{ '--item-index': index }}
      onClick={() => onItemClick(item)}
      isWatched={item.is_watched}
      title={title}
      subtitle={subtitle}
      imageUrl={imageUrl}
      icon={emptyIcon}
      backgroundColor={item.color}
      ratingImdb={ratingImdb}
      ratingTmdb={ratingTmdb}
      ratingPorndb={ratingPorndb}
      topRightAction={topRightAction}
      badge={badge}
      topRightBadge={topRightBadge}
      playOverlay={playOverlay}
      className={className}
    />
  );
});

LibraryPosterCard.displayName = 'LibraryPosterCard';

const TagPosterCard = memo(({
  item,
  t,
  resolvePosterUrl,
  emptyIcon,
  isFocusMode,
  onClick,
}) => {
  const isPerson = isPersonMediaType(item.type);
  const ratingImdb = item.rating_imdb;
  const ratingTmdb = item.rating;
  const ratingPorndb = item.rating_porndb;
  let cardProps;
  if (isPerson) {
    cardProps = {
      variant: isFocusMode ? 'overlay-title' : 'default',
      title: item.name || item.title,
      subtitle: item.people_role ? t(`library.people.roles.${item.people_role}`, { defaultValue: item.people_role }) : '',
      imageUrl: resolvePosterUrl(getProfileImagePath(item)),
      icon: emptyIcon,
      className: 'library-person-card',
      badge: renderUserRatingBadge(item),
      topRightBadge: renderFavoriteBadge(item, t),
    };
  } else {
    const subtitleParts = [];
    if (item.year) subtitleParts.push(item.year);
    if (item.info) subtitleParts.push(item.info);
    cardProps = {
      variant: isFocusMode ? 'overlay-title' : 'default',
      title: item.title,
      subtitle: subtitleParts.join(' • '),
      imageUrl: resolvePosterUrl(
        isTvLikeMediaType(item.type) ? getTvPosterImagePath(item) : getPosterImagePath(item)
      ),
      icon: emptyIcon,
      backgroundColor: item.color,
      badge: renderUserRatingBadge(item),
      ratingImdb: ratingImdb,
      ratingTmdb: ratingTmdb,
      ratingPorndb: ratingPorndb,
    };
  }

  return (
    <PosterCard
      isWatched={item.is_watched}
      onClick={onClick}
      {...cardProps}
    />
  );
});

TagPosterCard.displayName = 'TagPosterCard';

export default function LibraryGrid({
  t,
  isDataLoading,
  paginatedItems,
  isTags,
  isCollections,
  resolvedTab,
  emptyTitle,
  emptyDescription,
  emptyStateVariant,
  emptyIcon,
  hasActiveFilters,
  onAddPeople,
  onCreateTag,
  onEditTag,
  onDeleteTag,
  focusedTag,
  onFocusTag,
  onExitTagFocus,
  activeSessionMode,
  onEditImage,
}) {
  const navigate = useNavigate();
  const playMutation = usePlayMediaMutation();
  const { data: settings } = useSettingsQuery();
  const { openModal, closeModal, toast } = useUi();

  const getNextOwnedEpisode = (tvDetail) => {
    const seasons = Array.isArray(tvDetail?.seasons) ? tvDetail.seasons : [];

    for (const season of seasons) {
      const ownedEpisodes = (season.episodes || []).filter((episode) => episode.path && !episode.is_missing);
      const inProgress = ownedEpisodes.find((episode) => episode.resume_position > 0);
      if (inProgress) return inProgress;
    }

    for (const season of seasons) {
      const ownedEpisodes = (season.episodes || []).filter((episode) => episode.path && !episode.is_missing);
      const unwatched = ownedEpisodes.find((episode) => !episode.is_watched);
      if (unwatched) return unwatched;
    }

    for (const season of seasons) {
      const ownedEpisodes = (season.episodes || []).filter((episode) => episode.path && !episode.is_missing);
      if (ownedEpisodes.length > 0) return ownedEpisodes[0];
    }

    return null;
  };

  const handlePlayOverlayClick = useCallback(async (event, item) => {
    event.stopPropagation();

    if (playMutation.isPending) return;

    const isTv = item.type === 'tv' || String(item.id).startsWith('tv_');
    if (!isTv) {
      playMutation.mutate(item.id);
      return;
    }

    try {
      const tvId = String(item.id).replace('tv_', '').replace('tmdb_', '');
      const tvDetail = await api.library.getTvDetail(tvId);
      const nextEpisode = getNextOwnedEpisode(tvDetail);
      if (nextEpisode?.id) {
        playMutation.mutate(nextEpisode.id);
      }
    } catch {
      // Ignore overlay play failures and leave normal card navigation intact.
    }
  }, [playMutation]);

  const handleItemClick = useCallback((item) => {
    if (isTags) return;

    if (isCollections) {
      navigate(`/library/collection/${item.tmdb_id || item.id}`);
    } else if (isLibraryPeopleTab(resolvedTab)) {
      navigate(`/library/people/${item.id}`, { state: { allowAdult: true } });
    } else if (isLibraryMovieTab(resolvedTab)) {
      navigate(`/library/movie/${item.id}`, { state: { allowAdult: true } });
    } else if (isLibraryTvTab(resolvedTab)) {
      navigate(`/library/tv/${item.id}`, { state: { allowAdult: true } });
    } else if (isLibraryScenesTab(resolvedTab)) {
      navigate(`/library/scene/${item.id}`, { state: { allowAdult: true } });
    }
  }, [isTags, isCollections, resolvedTab, navigate]);

  const openImagePicker = useCallback((item) => {
    const isPeopleCard = isLibraryPeopleTab(resolvedTab);
    const entityId = isCollections
      ? `collection_${item.tmdb_id || item.id}`
      : item.id;
    const entityType = isPeopleCard
      ? 'person'
      : isCollections
        ? 'collection'
        : (isLibraryTvTab(resolvedTab) ? 'tv' : 'movie');
    const imageType = isPeopleCard ? 'profile' : 'poster';
    const currentPath = isPeopleCard
      ? getProfileImagePath(item)
      : isLibraryTvTab(resolvedTab)
        ? getTvPosterImagePath(item)
        : getPosterImagePath(item);
    const tmdbId = isPeopleCard ? item.id : (item.tmdb_id || item.tv_tmdb_id || item.id);

    onEditImage({
      entityId,
      entityType,
      imageType,
      currentPath,
      tmdbId,
      externalIds: item?.external_ids || item,
      item,
      title: isPeopleCard
        ? (t('library.details.changeProfile') || 'Change Profile Picture')
        : (t('library.details.changePoster') || 'Change Poster'),
    });
  }, [resolvedTab, isCollections, t, onEditImage]);

  const resolvePosterUrl = useCallback((path) => {
    return resolveMediaImageUrl(path, 'poster');
  }, []);

  if (isDataLoading && paginatedItems.length === 0) {
    return (
      <div className="library-content">
        <div className="library-loading">
          <div className="library-spinner" />
        </div>
      </div>
    );
  }

  return (
    <div className="library-content">
      {focusedTag || paginatedItems.length > 0 ? (
        isTags ? (
          focusedTag ? (
            <div className="library-tag-focus-view">
              <div className="library-tag-focus-view__toolbar">
                <NavButton className="library-tag-focus-view__back" onClick={onExitTagFocus}>
                  {t('library.tags.backToTags') || 'Back to Tags'}
                </NavButton>
              </div>
              <ExpandedTagPanel
                key={focusedTag.name}
                tag={focusedTag}
                t={t}
                resolvePosterUrl={resolvePosterUrl}
                emptyIcon={emptyIcon}
                isFocusMode
                activeSessionMode={activeSessionMode}
              />
            </div>
          ) : (
            <div className="library-tags-grid">
              {paginatedItems.map((item, index) => {
                const samplePreviews = Array.isArray(item.sample_previews) ? item.sample_previews.slice(0, 3) : [];
                const previewCount = samplePreviews.length;
                const singlePreview = previewCount === 1 ? samplePreviews[0] : null;
                const singlePreviewImage = (() => {
                  if (!singlePreview) return '';
                  const isPerson = isPersonMediaType(singlePreview.kind);
                  if (isPerson) {
                    return singlePreview.backdrop ? resolveMediaImageUrl(singlePreview.backdrop, 'backdrop') : '';
                  }
                  const isScene = isSceneMediaType(singlePreview.kind);
                  if (isScene) {
                    return singlePreview.still ? resolveMediaImageUrl(singlePreview.still, 'backdrop') : '';
                  }
                  return resolveMediaImageUrl(singlePreview.backdrop || singlePreview.poster, 'backdrop');
                })();
                return (
                  <div
                    key={item.name}
                    role="button"
                    tabIndex={0}
                    className={`library-tag-card ${previewCount > 0 ? `library-tag-card--preview-${Math.min(previewCount, 3)}` : ''}`.trim()}
                    onClick={() => onFocusTag?.(item.name)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        onFocusTag?.(item.name);
                      }
                    }}
                    /* eslint-disable-next-line react/forbid-dom-props */
                    style={{
                      '--tag-color': item.color || 'var(--color-accent)',
                      '--item-index': index,
                    }}
                  >
                    {(previewCount > 1 || singlePreviewImage) ? (
                      <div className="library-tag-card__preview" aria-hidden="true">
                        {samplePreviews.map((preview, index) => (
                          <div
                            key={`${item.name}-preview-${index}`}
                            className="library-tag-card__preview-image"
                            /* eslint-disable-next-line react/forbid-dom-props */
                            style={{
                              backgroundImage: `url(${previewCount === 1 ? singlePreviewImage : resolvePosterUrl(preview.poster)})`,
                              backgroundPositionX: preview.position_x != null ? `${preview.position_x}%` : 'center',
                              backgroundPositionY: preview.position_y != null ? `${preview.position_y}%` : 'center',
                            }}
                          />
                        ))}
                      </div>
                    ) : null}
                    <div className="library-tag-card__actions">
                      <IconButton
                        type="button"
                        size="xs"
                        variant="ghost"
                        label={t('library.tags.editBtn') || 'Edit Tag'}
                        onClick={(event) => {
                          event.stopPropagation();
                          onEditTag?.(item);
                        }}
                      >
                        <Pencil size={12} />
                      </IconButton>
                      <IconButton
                        type="button"
                        size="xs"
                        variant="ghost"
                        label={t('library.tags.deleteBtn') || 'Delete Tag'}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteTag?.(item);
                        }}
                      >
                        <Trash2 size={12} />
                      </IconButton>
                    </div>
                    <div className="library-tag-card__content">
                      <span className="library-tag-card__name">{item.name}</span>
                      <span className="library-tag-card__count">
                        {t('library.tags.itemsCount', { count: item.total_count })}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        ) : (
          <PosterGrid className={isLibraryScenesTab(resolvedTab) ? 'library-scenes-grid' : ''}>
            {paginatedItems.map((item, index) => (
              <LibraryPosterCard
                key={item.id}
                item={item}
                index={index}
                resolvedTab={resolvedTab}
                isCollections={isCollections}
                emptyIcon={emptyIcon}
                t={t}
                playMutationPending={playMutation.isPending}
                onItemClick={handleItemClick}
                onPlayOverlayClick={handlePlayOverlayClick}
                onEditImageClick={openImagePicker}
                settings={settings}
              />
            ))}
          </PosterGrid>
        )
      ) : (
        <EmptyState
          variant={emptyStateVariant}
          title={emptyTitle}
          description={emptyDescription}
          icon={emptyIcon}
          actions={
            isLibraryPeopleTab(resolvedTab) && onAddPeople && !hasActiveFilters ? (
              <Button variant="primary" size="sm" onClick={onAddPeople}>
                <UserPlus size={16} />
                {t('library.people.addPeopleBtn') || 'Add People'}
              </Button>
            ) : isLibraryTagsTab(resolvedTab) && onCreateTag && !hasActiveFilters ? (
              <Button variant="primary" size="sm" onClick={onCreateTag}>
                <Plus size={16} />
                {t('library.tags.createBtn') || 'Create Tag'}
              </Button>
            ) : null
          }
        />
      )}
    </div>
  );
}

function ExpandedTagPanel({ tag, t, resolvePosterUrl, emptyIcon, isFocusMode = false, activeSessionMode }) {
  const navigate = useNavigate();
  const allItems = useMemo(() => {
    if (Array.isArray(tag.mode_items)) {
      return tag.mode_items;
    }
    return getLibraryTagBucketKeys(activeSessionMode).flatMap((key) => tag[key] || []);
  }, [tag, activeSessionMode]);

  const [visibleCount, setVisibleCount] = useState(20);
  const paginatedItems = allItems.slice(0, visibleCount);
  const hasMore = allItems.length > visibleCount;

  if (allItems.length === 0) {
    return (
      <div
        className={`library-tag-expanded-panel ${isFocusMode ? 'is-focus-mode' : ''}`.trim()}
        /* eslint-disable-next-line react/forbid-dom-props */
        style={{ '--tag-color': tag.color || 'var(--color-accent)' }}
      >
        {isFocusMode ? (
          <div className="library-tag-expanded-panel__header">
            <div className="library-tag-expanded-panel__title-row">
              <h2 className="library-tag-expanded-panel__title">
                {(t('library.tags.focusTitle') || 'Items tagged with "{name}"').replace('{name}', tag.name)}
              </h2>
            </div>
          </div>
        ) : null}
        <EmptyState
          variant="tag-focus"
          title={(t('library.tags.emptyFocusTitle') || 'This tag is ready to use.').replace('{name}', tag.name)}
          description={(t('library.tags.emptyFocusDescription') || 'Add this tag to movies, shows, or people and they will appear here.').replace('{name}', tag.name)}
        />
      </div>
    );
  }

  return (
    <div
      className={`library-tag-expanded-panel ${isFocusMode ? 'is-focus-mode' : ''}`.trim()}
      /* eslint-disable-next-line react/forbid-dom-props */
      style={{ '--tag-color': tag.color || 'var(--color-accent)' }}
    >
      {isFocusMode ? (
        <div className="library-tag-expanded-panel__header">
          <div className="library-tag-expanded-panel__title-row">
            <h2 className="library-tag-expanded-panel__title">
              {(t('library.tags.focusTitle') || 'Items tagged with "{name}"').replace('{name}', tag.name)}
            </h2>
          </div>
        </div>
      ) : null}
      <PosterGrid>
        {paginatedItems.map((item) => (
          <TagPosterCard
            key={item.id}
            item={item}
            t={t}
            resolvePosterUrl={resolvePosterUrl}
            emptyIcon={emptyIcon}
            isFocusMode={isFocusMode}
            onClick={() => {
              const isPerson = isPersonMediaType(item.type);
              if (isPerson) {
                navigate(`/library/people/${item.id}`, { state: { allowAdult: true } });
                return;
              }
              if (isMovieMediaType(item.type)) {
                navigate(`/library/movie/${item.id}`, { state: { allowAdult: true } });
              } else if (isTvLikeMediaType(item.type)) {
                navigate(`/library/tv/${item.id}`, { state: { allowAdult: true } });
              } else if (isSceneMediaType(item.type)) {
                navigate(`/library/scene/${item.id}`, { state: { allowAdult: true } });
              }
            }}
          />
        ))}
      </PosterGrid>

      {hasMore && (
        <div className="library-grid-load-more">
          <Button variant="secondary" onClick={() => setVisibleCount(prev => prev + 20)}>
            {t('common.showMore') || 'Show More'}
          </Button>
        </div>
      )}
    </div>
  );
}
