import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import PosterGrid from '@/ui/PosterGrid';
import PosterCard from '@/ui/PosterCard';
import Pill from '@/ui/Pill';
import EmptyState from '@/ui/EmptyState';
import CreditCard from '@/ui/CreditCard';
import BackdropCard from '@/ui/BackdropCard';
import ImageUploadPanel from '../../modals/ImageUploadPanel';
import { API_BASE } from '@/lib/backend';
import { isTvLikeMediaType, isSceneMediaType } from '@/lib/mediaTypes';
import { getPosterImagePath } from '@/lib/imageUrls';
import { ChevronLeft, ChevronRight, Film, ImageOff, Star, Tv } from 'lucide-react';
import { resolveDetailsImageUrl } from '../../utils/detailUtils';
import { normalizeBackdropKey } from '../../peopleCollectionDetailUtils.jsx';
import './PersonCreditsShared.css';

export function OverviewContent({ text, emptyText, t, openDrawer, className = '' }) {
  const overviewRef = useRef(null);
  const [isTruncated, setIsTruncated] = useState(false);

  useLayoutEffect(() => {
    const element = overviewRef.current;
    if (!element) {
      return undefined;
    }

    let frameId = null;
    let resizeObserver = null;

    const measure = () => {
      setIsTruncated(element.scrollHeight > element.clientHeight + 1);
    };

    const scheduleMeasure = () => {
      if (frameId !== null) {
        cancelAnimationFrame(frameId);
      }
      frameId = requestAnimationFrame(measure);
    };

    scheduleMeasure();

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        scheduleMeasure();
      });
      resizeObserver.observe(element);
    }

    window.addEventListener('resize', scheduleMeasure);

    return () => {
      if (frameId !== null) {
        cancelAnimationFrame(frameId);
      }
      resizeObserver?.disconnect();
      window.removeEventListener('resize', scheduleMeasure);
    };
  }, [text]);

  return (
    <div className={`media-detail-page__overview entity-detail-page__overview ${className}`.trim()}>
      {text ? (
        <>
          <div ref={overviewRef} className="media-detail-page__overview-text">
            {text}
          </div>
          {isTruncated && (
            <button
              type="button"
              className="media-detail-page__read-more-btn"
              onClick={openDrawer}
            >
              {t('library.details.readMore') || 'Read More'}
            </button>
          )}
        </>
      ) : (
        <p className="entity-detail-page__overview-text entity-detail-page__overview-text--muted">
          {emptyText}
        </p>
      )}
    </div>
  );
}

export function EntityCardGrid({ items, type, navigate, t }) {
  if (!items?.length) {
    return null;
  }

  const openItem = (item) => {
    const resolvedType = item.media_type || item.type || type;
    if (isTvLikeMediaType(resolvedType)) {
      const tvId = item.library_tv_tmdb_id || item.tv_tmdb_id || item.tmdb_id || item.id;
      navigate(`/library/tv/${tvId}`, { state: { allowAdult: true } });
      return;
    }

    if (isSceneMediaType(resolvedType)) {
      const itemSource = item.source;
      const prefix = itemSource === 'porndb' || itemSource === 'theporndb' ? 'porndb' : itemSource === 'fansdb' ? 'fansdb' : 'stash';
      const sceneId = item.in_library ? (item.library_item_id || item.id) : `${prefix}_${item.stash_id || item.id}`;
      navigate(`/library/scene/${sceneId}`, { state: { allowAdult: true } });
      return;
    }

    const movieId = item.in_library ? (item.library_item_id || item.id) : `tmdb_${item.tmdb_id || item.id}`;
    navigate(`/library/movie/${movieId}`, { state: { allowAdult: true } });
  };

  return (
    <PosterGrid>
      {items.map((item, index) => {
        const resolvedType = item.media_type || item.type || type;
        const posterPath = getPosterImagePath(item) || item.backdrop_path || item.local_backdrop_path;
        const subtitleParts = [];
        if (item.year) subtitleParts.push(String(item.year));
        if (item.job) subtitleParts.push(item.job);
        if (item.character) subtitleParts.push(item.character);
        if (item.episode_count) {
          subtitleParts.push(
            t('library.details.episodePlural', {
              count: item.episode_count,
              defaultValue: `${item.episode_count} Episodes`,
            })
          );
        }

        return (
          <PosterCard
            key={`${type}-${item.tmdb_id || item.id}`}
            title={item.title}
            subtitle={subtitleParts.join(' - ')}
            imageUrl={resolveDetailsImageUrl(posterPath, API_BASE, 'poster')}
            ratingImdb={item.rating_imdb}
            ratingTmdb={item.rating_tmdb ?? item.rating}
            icon={isTvLikeMediaType(resolvedType) ? Tv : Film}
            customStyle={{ '--item-index': index }}
            onClick={() => openItem(item)}
          />
        );
      })}
    </PosterGrid>
  );
}

function HorizontalCollectionItemsList({ items, navigate, t }) {
  if (!items?.length) {
    return null;
  }

  const openItem = (item) => {
    const resolvedType = item.media_type || item.type;
    if (isTvLikeMediaType(resolvedType)) {
      const tvId = item.library_tv_tmdb_id || item.tv_tmdb_id || item.tmdb_id || item.id;
      navigate(`/library/tv/${tvId}`, { state: { allowAdult: true } });
      return;
    }

    if (isSceneMediaType(resolvedType)) {
      const itemSource = item.source;
      const prefix = itemSource === 'porndb' || itemSource === 'theporndb' ? 'porndb' : itemSource === 'fansdb' ? 'fansdb' : 'stash';
      const sceneId = item.in_library ? (item.library_item_id || item.id) : `${prefix}_${item.stash_id || item.id}`;
      navigate(`/library/scene/${sceneId}`, { state: { allowAdult: true } });
      return;
    }

    const movieId = item.in_library ? (item.library_item_id || item.id) : `tmdb_${item.tmdb_id || item.id}`;
    navigate(`/library/movie/${movieId}`, { state: { allowAdult: true } });
  };

  return (
    <div className="entity-detail-page__credits-list entity-detail-page__credits-list--collection-items">
      {items.map((item) => {
        const isTv = isTvLikeMediaType(item.media_type || item.type);
        const imdbRating = Number(item.rating_imdb);
        const tmdbRating = Number(item.rating_tmdb ?? item.rating);
        const hasImdbRating = Number.isFinite(imdbRating) && imdbRating > 0;
        const hasTmdbRating = Number.isFinite(tmdbRating) && tmdbRating > 0;
        const posterPath = getPosterImagePath(item) || item.backdrop_path || item.local_backdrop_path;
        const posterUrl = posterPath ? resolveDetailsImageUrl(posterPath, API_BASE, 'poster') : null;

        return (
          <CreditCard
            key={`collection-item-${item.media_type || item.type || 'movie'}-${item.tmdb_id || item.id}`}
            title={item.title}
            imageUrl={posterUrl}
            isTv={isTv}
            isCollectionItem={true}
            isOwned={item.in_library}
            isMissing={!item.in_library}
            onClick={() => openItem(item)}
          >
            <div className="ui-credit-card__meta">
              {item.year && <span>{item.year}</span>}
              {(hasImdbRating || hasTmdbRating) && (
                <Pill
                  variant={hasImdbRating ? 'imdb' : 'tmdb'}
                  className="ui-credit-card__rating-pill"
                >
                  <Star size={10} fill="currentColor" strokeWidth={1.8} />
                  {(hasImdbRating ? imdbRating : tmdbRating).toFixed(1)}
                </Pill>
              )}
              <Pill
                variant={item.in_library ? 'success' : 'missing'}
                className="ui-credit-card__status-pill"
              >
                {item.in_library
                  ? (t('library.details.have') || 'Have')
                  : (t('library.details.missing') || 'Missing')}
              </Pill>
            </div>
          </CreditCard>
        );
      })}
    </div>
  );
}

export function CollectionBackdropsPanel({ item, collectionId, t, toast, overrideBackdropMutation, uploadBackdropMutation }) {
  const [selectedBackdropPath, setSelectedBackdropPath] = useState(item?.backdrop_path || '');
  const backdropOptions = useMemo(() => {
    const seen = new Set();
    const collectionBackdrops = [];

    for (const option of (item?.collection_backdrops || [])
      .map((bd, index) => ({
        backdrop_path: bd.file_path,
        backdrop_key: normalizeBackdropKey(bd.file_path),
        title: item?.title || 'Collection',
        subtitle: t('library.details.collectionBackdrop') || 'Collection backdrop',
        sort_score: Number(bd.vote_average) || 0,
        sort_votes: Number(bd.vote_count) || 0,
        sort_index: index,
        iso_639_1: bd.iso_639_1,
      }))
      .filter((option) => option.backdrop_path && option.backdrop_key && (!option.iso_639_1 || option.iso_639_1 === 'null'))
      .sort((a, b) => (
        (b.sort_score - a.sort_score)
        || (b.sort_votes - a.sort_votes)
        || (a.sort_index - b.sort_index)
      ))) {
      if (seen.has(option.backdrop_key)) {
        continue;
      }
      seen.add(option.backdrop_key);
      collectionBackdrops.push({
        backdrop_path: option.backdrop_path,
        backdrop_key: option.backdrop_key,
        title: option.title,
        subtitle: option.subtitle,
      });
    }

    return collectionBackdrops;
  }, [item, t]);

  const currentBackdropPath = selectedBackdropPath || item?.backdrop_path || '';
  const currentBackdropKey = normalizeBackdropKey(currentBackdropPath);

  const handleUploadBackdrop = async (file) => {
    if (!file || uploadBackdropMutation?.isPending) return;
    try {
      const data = await uploadBackdropMutation.mutateAsync({ itemId: 'collection_' + collectionId, file });
      setSelectedBackdropPath(data?.backdrop_path || item?.backdrop_path || '');
      toast(t('library.details.imageUploaded') || 'Image uploaded and updated successfully!', 'success');
    } catch (err) {
      toast(err.message || t('library.details.imageUploadFailed') || 'Failed to upload image', 'danger');
    }
  };

  const handleSelectBackdrop = async (backdropPath) => {
    setSelectedBackdropPath(backdropPath);
    try {
      await overrideBackdropMutation.mutateAsync({
        itemId: `collection_${collectionId}`,
        backdropPath,
      });
      toast(t('library.details.backdropUpdated') || 'Backdrop updated successfully!', 'success');
    } catch (err) {
      toast(err.message || t('library.details.backdropUpdateFailed') || 'Failed to update backdrop', 'danger');
    }
  };

  return (
    <div className="backdrops-panel">
      <ImageUploadPanel
        imageType="backdrop"
        isPending={overrideBackdropMutation.isPending || Boolean(uploadBackdropMutation?.isPending)}
        t={t}
        onSaveUrl={handleSelectBackdrop}
        onUploadFile={handleUploadBackdrop}
      />

      <div className="backdrops-grid">
        {backdropOptions.map((option, idx) => {
          const backdropUrl = resolveDetailsImageUrl(option.backdrop_path, API_BASE, 'backdrop');
          const isPending = overrideBackdropMutation.isPending && overrideBackdropMutation.variables?.backdropPath === option.backdrop_path;
          const isSelected = (currentBackdropKey !== '' && currentBackdropKey === option.backdrop_key) || isPending;
          const label = option.year ? `${option.title} (${option.year})` : option.title;

          return (
            <BackdropCard
              key={`${option.backdrop_path}-${idx}`}
              imageUrl={backdropUrl}
              alt={label}
              isSelected={isSelected}
              isPending={isPending || Boolean(uploadBackdropMutation?.isPending)}
              infoLeft={label}
              infoRight={option.subtitle}
              onClick={() => handleSelectBackdrop(option.backdrop_path)}
              title={label}
            />
          );
        })}
        {backdropOptions.length === 0 && (
          <EmptyState
            icon={ImageOff}
            title={t('library.details.noBackdropsAvailable') || 'No good backdrop options found for this title.'}
            className="backdrops-panel__empty-state"
          />
        )}
      </div>
    </div>
  );
}

export function CollectionItemsSection({ items, navigate, t }) {
  const containerRef = useRef(null);
  const [columns, setColumns] = useState(1);
  const [page, setPage] = useState(0);

  useLayoutEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return undefined;
    }

    let frameId = null;
    let resizeObserver = null;

    const measure = () => {
      const styles = window.getComputedStyle(element);
      const gap = Number.parseFloat(styles.columnGap || styles.gap || '16') || 16;
      const minCardWidth = 224;
      const width = element.clientWidth || 0;
      const nextColumns = Math.max(1, Math.floor((width + gap) / (minCardWidth + gap)));
      setColumns((current) => (current === nextColumns ? current : nextColumns));
    };

    const scheduleMeasure = () => {
      if (frameId !== null) {
        cancelAnimationFrame(frameId);
      }
      frameId = requestAnimationFrame(measure);
    };

    scheduleMeasure();

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        scheduleMeasure();
      });
      resizeObserver.observe(element);
    }

    window.addEventListener('resize', scheduleMeasure);

    return () => {
      if (frameId !== null) {
        cancelAnimationFrame(frameId);
      }
      resizeObserver?.disconnect();
      window.removeEventListener('resize', scheduleMeasure);
    };
  }, []);

  const itemsPerPage = Math.max(1, columns * 3);
  const totalPages = Math.max(1, Math.ceil((items?.length || 0) / itemsPerPage));

  if (page > totalPages - 1) {
    setPage(totalPages - 1);
  }

  const safePage = Math.min(page, totalPages - 1);
  const visibleItems = (items || []).slice(safePage * itemsPerPage, (safePage + 1) * itemsPerPage);

  return (
    <section className="entity-detail-page__content-section">
      <div className="entity-detail-page__section-header">
        <h2>{t('library.details.collectionItemsTitle') || 'Collection Items'}</h2>
        {totalPages > 1 && (
          <div className="entity-detail-page__section-pager">
            <button
              type="button"
              className="entity-detail-page__section-pager-btn"
              onClick={() => setPage((current) => Math.max(0, current - 1))}
              disabled={safePage === 0}
              aria-label={t('common.previous') || 'Previous'}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              type="button"
              className="entity-detail-page__section-pager-btn"
              onClick={() => setPage((current) => Math.min(totalPages - 1, current + 1))}
              disabled={safePage >= totalPages - 1}
              aria-label={t('common.next') || 'Next'}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>
      <div ref={containerRef}>
        <HorizontalCollectionItemsList items={visibleItems} navigate={navigate} t={t} />
      </div>
    </section>
  );
}
