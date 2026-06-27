import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Star } from 'lucide-react';
import Pill from '@/ui/Pill';
import CreditCard from '@/ui/CreditCard';
import api from '@/lib/api';
import { getPosterImagePath } from '@/lib/imageUrls';
import { usePersonCreditsQuery } from '@/queries/metadataQueries';
import { isTvLikeMediaType } from '@/lib/mediaTypes';
import { API_BASE } from '@/lib/backend';
import { resolveDetailsImageUrl } from '../../utils/detailUtils';
import './PersonCreditsShared.css';

const PERSON_INITIAL_CREDITS_PAGE_SIZE = 12;

export default function PersonCreditsGridSection({ personId, mediaType, totalCount, initialPageData, navigate, t, onPaginationData, source }) {
  const shouldLoad = Boolean(personId) && (Number(totalCount) > 0 || !!source);
  const queryClient = useQueryClient();
  const containerRef = useRef(null);
  const [columns, setColumns] = useState(Math.max(1, Math.floor(PERSON_INITIAL_CREDITS_PAGE_SIZE / 2)));
  const [page, setPage] = useState(1);

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

  const itemsPerPage = Math.max(1, columns * 2);
  const creditsQuery = usePersonCreditsQuery(personId, mediaType, page, itemsPerPage, {
    enabled: shouldLoad,
    initialData: page === 1 && itemsPerPage === PERSON_INITIAL_CREDITS_PAGE_SIZE ? initialPageData : undefined,
    source,
  });
  const totalPages = Math.max(1, Number(creditsQuery.data?.total_pages) || Math.ceil(Number(totalCount) / itemsPerPage) || 1);

  if (page > totalPages) {
    setPage(totalPages);
  } else if (page < 1) {
    setPage(1);
  }

  const safePage = Math.min(page, totalPages);

  useEffect(() => {
    if (onPaginationData) {
      onPaginationData({ page: safePage, totalPages, setPage, totalCount: creditsQuery.data?.total_items });
    }
  }, [safePage, totalPages, setPage, onPaginationData, creditsQuery.data?.total_items]);
  const visibleItems = creditsQuery.data?.items || [];
  const fillerCount = Math.max(0, itemsPerPage - visibleItems.length);
  const isInitialPageLoading = creditsQuery.isLoading && visibleItems.length === 0;
  const resolvedPage = Number(creditsQuery.data?.page) || 1;
  const resolvedPageSize = Number(creditsQuery.data?.page_size) || itemsPerPage;
  const isPageFetching = creditsQuery.isFetching && (
    resolvedPage !== page || resolvedPageSize !== itemsPerPage
  );

  useEffect(() => {
    if (!shouldLoad || page !== 1 || !creditsQuery.data?.items?.length || totalPages <= 1) {
      return;
    }

    const nextPage = page + 1;
    if (nextPage > totalPages) {
      return;
    }

    queryClient.prefetchQuery({
      queryKey: ['person-credits', personId, mediaType, nextPage, itemsPerPage, false, source || null],
      queryFn: () => api.people.getCredits(personId, mediaType, { page: nextPage, pageSize: itemsPerPage, source }),
    });
  }, [
    creditsQuery.data?.items,
    itemsPerPage,
    mediaType,
    page,
    personId,
    queryClient,
    shouldLoad,
    totalPages,
    source,
  ]);

  if (!shouldLoad) {
    return null;
  }

  const openItem = (item) => {
    const isScene = item.media_type === 'scene' || item.type === 'scene';
    if (isScene) {
      const itemSource = item.source || source;
      const prefix = itemSource === 'porndb' || itemSource === 'theporndb' ? 'porndb' : itemSource === 'fansdb' ? 'fansdb' : 'stash';
      const sceneId = item.in_library ? (item.library_item_id || item.id) : `${prefix}_${item.stash_id || item.id}`;
      navigate(`/library/scene/${sceneId}`, { state: { allowAdult: true } });
      return;
    }

    if (isTvLikeMediaType(item.media_type || item.type)) {
      const tvId = item.library_tv_tmdb_id || item.tv_tmdb_id || item.tmdb_id || item.id;
      navigate(`/library/tv/${tvId}`, { state: { allowAdult: true } });
      return;
    }

    const movieId = item.in_library
      ? (item.library_item_id || item.id)
      : (item.source === 'porndb' || source === 'porndb')
      ? `porndb_${item.tmdb_id || item.id}`
      : `tmdb_${item.tmdb_id || item.id}`;
    navigate(`/library/movie/${movieId}`, { state: { allowAdult: true } });
  };

  return (
    <section className="entity-detail-page__content-section">
      <div
        ref={containerRef}
        className={`entity-detail-page__credits-list entity-detail-page__credits-list--people-grid${isPageFetching ? ' entity-detail-page__credits-list--fetching' : ''
          }`}
      >
        {isInitialPageLoading && Array.from({ length: itemsPerPage }).map((_, index) => (
          <div key={`credit-grid-skeleton-${mediaType}-${index}`} className="ui-credit-card ui-credit-card--people-grid entity-detail-page__skeleton-card">
            <div className="entity-detail-page__skeleton-block entity-detail-page__skeleton-block--credit-poster" />
            <div className="ui-credit-card__body">
              <div className="ui-credit-card__topline">
                <div className="entity-detail-page__skeleton-block entity-detail-page__skeleton-block--credit-title" />
              </div>
              <div className="ui-credit-card__meta">
                <div className="entity-detail-page__skeleton-block entity-detail-page__skeleton-block--credit-meta" />
                <div className="entity-detail-page__skeleton-block entity-detail-page__skeleton-block--credit-pill" />
                <div className="entity-detail-page__skeleton-block entity-detail-page__skeleton-block--credit-pill" />
              </div>
            </div>
          </div>
        ))}
        {visibleItems.map((item) => {
          const isTv = isTvLikeMediaType(item.media_type || item.type);
          const posterPath = getPosterImagePath(item) || item.backdrop_path || item.local_backdrop_path;
          const posterUrl = posterPath ? resolveDetailsImageUrl(posterPath, API_BASE, 'poster') : null;

          return (
            <CreditCard
              key={`credit-grid-${item.media_type || item.type || 'movie'}-${item.tmdb_id || item.id}`}
              title={item.title}
              imageUrl={posterUrl}
              isTv={isTv}
              isPeopleGrid={true}
              isCollectionItem={true}
              isKnownFor={item.is_known_for}
              isOwned={item.in_library}
              isMissing={!item.in_library}
              onClick={() => openItem(item)}
            >
              {mediaType === 'scenes' ? (
                <>
                  {item.studio && (
                    <div
                      className="person-credits-card__studio"
                      title={item.studio}
                    >
                      {item.studio}
                    </div>
                  )}
                  <div className="ui-credit-card__meta person-credits-card__meta-container">
                    {item.year && <span>{item.year}</span>}
                    {item.duration && <span>{item.duration}</span>}
                    {item.resolution && (
                      <Pill variant="accent" className="person-credits-card__res-pill">
                        {item.resolution}
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
                </>
              ) : (
                <div className="ui-credit-card__meta">
                  {item.year && <span>{item.year}</span>}
                  {(() => {
                    const imdbRating = Number(item.rating_imdb);
                    const tmdbRating = Number(item.rating_tmdb ?? item.rating);
                    const porndbRating = Number(item.rating_porndb);
                    const hasImdbRating = Number.isFinite(imdbRating) && imdbRating > 0;
                    const hasTmdbRating = Number.isFinite(tmdbRating) && tmdbRating > 0;
                    const hasPorndbRating = Number.isFinite(porndbRating) && porndbRating > 0;

                    if (!hasImdbRating && !hasTmdbRating && !hasPorndbRating) {
                      return null;
                    }

                    let variant = 'meta';
                    let label = '';
                    const isPornDbTab = String(mediaType || '').startsWith('porndb');

                    if (isPornDbTab && hasPorndbRating) {
                      variant = 'porndb';
                      label = porndbRating.toFixed(1);
                    } else if (hasImdbRating) {
                      variant = 'imdb';
                      label = imdbRating.toFixed(1);
                    } else if (hasTmdbRating) {
                      variant = 'tmdb';
                      label = tmdbRating.toFixed(1);
                    } else if (hasPorndbRating) {
                      variant = 'porndb';
                      label = porndbRating.toFixed(1);
                    }

                    return (
                      <Pill
                        variant={variant}
                        className="ui-credit-card__rating-pill"
                      >
                        <Star size={10} fill="currentColor" strokeWidth={1.8} />
                        {label}
                      </Pill>
                    );
                  })()}
                  <Pill
                    variant={item.in_library ? 'success' : 'missing'}
                    className="ui-credit-card__status-pill"
                  >
                    {item.in_library
                      ? (t('library.details.have') || 'Have')
                      : (t('library.details.missing') || 'Missing')}
                  </Pill>
                </div>
              )}
            </CreditCard>
          );
        })}
        {Array.from({ length: fillerCount }).map((_, index) => (
          <CreditCard
            key={`credit-grid-filler-${mediaType}-${safePage}-${index}`}
            isPlaceholder={true}
            isPeopleGrid={true}
            isCollectionItem={true}
          />
        ))}
      </div>
    </section>
  );
}
