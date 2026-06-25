import { useEffect, useMemo, useRef, useState } from 'react';
import { ImageOff } from 'lucide-react';
import { useFullMetadataQuery, usePersonDetailQuery, useLibraryCollectionDetailQuery } from '@/queries/metadataQueries';
import { useTranslation } from '@/providers/LanguageContext';
import { resolveDetailsImageUrl } from '../../utils/detailUtils';
import { buildTmdbImageUrl, TMDB_IMAGE_SIZES } from '@/lib/imageUrls';
import { API_BASE } from '@/lib/backend';
import EmptyState from '@/ui/EmptyState';
import BackdropCard from '@/ui/BackdropCard';
import '../detail/panels/BackdropsPanel.css'; // Reuse existing backdrop panel grid styles

export default function TMDBImageGrid({
  itemId,
  tmdbId,
  mediaType,
  imageType = 'backdrop', // 'backdrop' | 'poster' | 'logo'
  customImages,
  currentPath,
  onSelect,
  isPending,
  pendingPath,
  initialVisibleCount,
  visibleStep,
  t,
  selectedSource,
}) {
  const { locale } = useTranslation();
  const isPerson = mediaType === 'person';
  const isCollection = mediaType === 'collection';
  const [visibleCount, setVisibleCount] = useState(() => initialVisibleCount ?? Number.POSITIVE_INFINITY);
  const loadMoreRef = useRef(null);
  const metadataLanguage = locale === 'en' ? 'en-US' : locale;
  const normalizedMediaType = mediaType === 'tv' ? 'tv' : mediaType;

  // Extract clean ID if it starts with collection_
  const cleanItemId = useMemo(() => {
    if (typeof itemId === 'string' && itemId.startsWith('collection_')) {
      return itemId.replace('collection_', '');
    }
    return itemId;
  }, [itemId]);

  const metadataQueryId = cleanItemId;

  const { data: fullMetadata, isLoading: isLoadingMetadata } = useFullMetadataQuery(metadataQueryId, normalizedMediaType, {
    enabled: !customImages && Boolean(metadataQueryId) && !isPerson && !isCollection,
    language: metadataLanguage,
  });

  const { data: personDetail, isLoading: isLoadingPerson } = usePersonDetailQuery(cleanItemId, {
    enabled: !customImages && Boolean(cleanItemId) && isPerson,
  });

  const { data: collectionDetail, isLoading: isLoadingCollection } = useLibraryCollectionDetailQuery(cleanItemId, {
    enabled: !customImages && Boolean(cleanItemId) && isCollection,
    language: metadataLanguage,
  });

  const isLoading = isLoadingMetadata || isLoadingPerson || isLoadingCollection;

  const images = useMemo(() => {
    if (customImages) return customImages;

    if (isPerson) {
      if (!personDetail?.images) return [];
      let list = personDetail.images;
      if (selectedSource && selectedSource !== 'all') {
        if (selectedSource === 'tmdb') {
          list = list.filter(img => img.startsWith('/') || img.includes('tmdb') || (!img.includes('stashdb') && !img.includes('fansdb') && !img.includes('theporndb') && !img.includes('metadataapi')));
        } else if (selectedSource === 'stashdb') {
          list = list.filter(img => img.includes('stashdb'));
        } else if (selectedSource === 'fansdb') {
          list = list.filter(img => img.includes('fansdb'));
        } else if (selectedSource === 'theporndb') {
          list = list.filter(img => img.includes('theporndb') || img.includes('metadataapi'));
        }
      }
      return list.map((img) => ({
        file_path: img,
        width: 0,
        height: 0,
        vote_average: 0,
      }));
    }

    if (isCollection) {
      const collectionPosterOptions = Array.isArray(collectionDetail?.collection_posters)
        ? collectionDetail.collection_posters
        : Array.isArray(collectionDetail?.posters)
          ? collectionDetail.posters
          : Array.isArray(collectionDetail?.images?.posters)
            ? collectionDetail.images.posters
            : [];

      const localeShort = String(metadataLanguage || '').split('-', 1)[0].toLowerCase();
      return collectionPosterOptions.map((img) => {
        const imgLang = String(img.iso_639_1 || '').toLowerCase();
        let score = 0;
        if (imgLang === String(metadataLanguage || '').toLowerCase()) {
          score = 4;
        } else if (localeShort && imgLang.split('-', 1)[0] === localeShort) {
          score = 3;
        } else if (imgLang === 'en' || imgLang === 'en-us') {
          score = 2;
        } else if (!imgLang || imgLang === 'null') {
          score = 1;
        }
        return {
          file_path: img.file_path || img.poster_path || img.path,
          width: img.width,
          height: img.height,
          vote_average: img.vote_average,
          score,
        };
      }).sort((a, b) => {
        if (b.score !== a.score) {
          return b.score - a.score;
        }
        return (b.vote_average || 0) - (a.vote_average || 0);
      });
    }

    const activeMatch = fullMetadata?.matches?.find((m) => m.is_active);
    const imageKey = imageType === 'backdrop'
      ? 'backdrops'
      : imageType === 'logo'
        ? 'logos'
        : 'posters';

    if (!activeMatch && fullMetadata?.raw_details?.images) {
      const rawImages = fullMetadata.raw_details.images[imageKey];
      if (Array.isArray(rawImages)) {
        const isTvBackdrop = normalizedMediaType === 'tv' && imageType === 'backdrop';
        const localeShort = String(metadataLanguage || '').split('-', 1)[0].toLowerCase();
        return rawImages
          .filter((img) => !isTvBackdrop || (img.width || 0) >= 720)
          .map((img) => {
          const imgLang = String(img.iso_639_1 || '').toLowerCase();
          let score = 0;
          if (isTvBackdrop) {
            // TV backdrops: language-independent, score only by resolution
            score = (img.width || 0) >= 1920 ? 2 : 1;
          } else if (imgLang === String(metadataLanguage || '').toLowerCase()) {
            score = 4;
          } else if (localeShort && imgLang.split('-', 1)[0] === localeShort) {
            score = 3;
          } else if (imgLang === 'en' || imgLang === 'en-us') {
            score = 2;
          } else if (!imgLang || imgLang === 'null') {
            score = 1;
          }
          return {
            file_path: img.file_path,
            width: img.width,
            height: img.height,
            vote_average: img.vote_average,
            score,
          };
        }).sort((a, b) => {
          if (b.score !== a.score) {
            return b.score - a.score;
          }
          return (b.vote_average || 0) - (a.vote_average || 0);
        });
      }
    }

    const responseMap = normalizedMediaType === 'tv'
      ? (activeMatch?.tv_api_responses || activeMatch?.api_responses || {})
      : (activeMatch?.api_responses || activeMatch?.tv_api_responses || {});

    const responseEntries = Object.entries(responseMap);
    const isTvBackdrop = normalizedMediaType === 'tv' && imageType === 'backdrop';
    const localeShort = String(metadataLanguage || '').split('-', 1)[0].toLowerCase();
    const allImagesMap = new Map();

    for (const [lang, response] of responseEntries) {
      const rawImages = response?.images?.[imageKey];
      if (!Array.isArray(rawImages)) continue;

      const normalizedLang = String(lang || '').toLowerCase();
      let langScore = 0;
      if (isTvBackdrop) {
        langScore = 1; // language-independent: all equal
      } else if (normalizedLang === String(metadataLanguage || '').toLowerCase()) {
        langScore = 4;
      } else if (localeShort && normalizedLang.split('-', 1)[0] === localeShort) {
        langScore = 3;
      } else if (normalizedLang === 'en' || normalizedLang === 'en-us') {
        langScore = 2;
      } else if (!normalizedLang || normalizedLang === 'null') {
        langScore = 1;
      }

      for (const img of rawImages) {
        if (!img.file_path) continue;
        if (isTvBackdrop && (img.width || 0) < 720) continue;
        const score = isTvBackdrop ? ((img.width || 0) >= 1920 ? 2 : 1) : langScore;
        const existing = allImagesMap.get(img.file_path);
        if (!existing || existing.score < score) {
          allImagesMap.set(img.file_path, {
            file_path: img.file_path,
            width: img.width,
            height: img.height,
            vote_average: img.vote_average,
            score,
          });
        }
      }
    }

    return Array.from(allImagesMap.values()).sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      return (b.vote_average || 0) - (a.vote_average || 0);
    });
  }, [collectionDetail, customImages, fullMetadata, imageType, isCollection, isPerson, metadataLanguage, normalizedMediaType, personDetail, selectedSource]);

  const normalizedCurrent = useMemo(() => {
    if (!currentPath) return '';
    const parts = currentPath.split('/');
    return parts[parts.length - 1].toLowerCase();
  }, [currentPath]);

  const selectedIndex = useMemo(
    () => images.findIndex((img) => {
      const path = img.file_path || img.backdrop_path || img.poster_path || img.logo_path;
      if (!path || !currentPath) return false;
      const isPathHttp = path.startsWith('http://') || path.startsWith('https://');
      const isCurrentHttp = currentPath.startsWith('http://') || currentPath.startsWith('https://');
      if (isPathHttp && isCurrentHttp) {
        return path.toLowerCase() === currentPath.toLowerCase();
      }
      return path.split('/').pop().toLowerCase() === normalizedCurrent;
    }),
    [images, currentPath, normalizedCurrent]
  );

  useEffect(() => {
    const baseVisibleCount = initialVisibleCount ?? Number.POSITIVE_INFINITY;
    const minimumVisibleCount = selectedIndex >= 0
      ? Math.max(baseVisibleCount, selectedIndex + 1)
      : baseVisibleCount;
    setVisibleCount(minimumVisibleCount);
  }, [images, initialVisibleCount, selectedIndex]);

  const displayedImages = useMemo(
    () => images.slice(0, visibleCount),
    [images, visibleCount]
  );

  const hasMore = displayedImages.length < images.length;

  const handleLoadMore = () => {
    const step = visibleStep ?? initialVisibleCount ?? 16;
    setVisibleCount((prev) => Math.min(images.length, prev + step));
  };

  useEffect(() => {
    if (!hasMore || !loadMoreRef.current || !Number.isFinite(visibleCount)) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          handleLoadMore();
        }
      },
      {
        root: null,
        rootMargin: '240px 0px',
        threshold: 0.01,
      }
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [hasMore, visibleCount, images.length]);

  const handleSelectImage = (path) => {
    if (onSelect) {
      onSelect(path);
    }
  };

  if (isLoading) {
    return (
      <div className="backdrops-grid">
        {Array.from({ length: 8 }).map((_, index) => (
          <BackdropCard key={`skeleton-${index}`} disabled={true} />
        ))}
      </div>
    );
  }

  return (
    <div className="backdrops-panel">
      <div className={`backdrops-grid ${imageType === 'logo' ? 'backdrops-grid--logo' : ''}`}>
        {displayedImages.map((img, idx) => {
          const path = img.file_path || img.backdrop_path || img.poster_path || img.logo_path;
          if (!path) return null;

          // Determine sizes and urls based on imageType
          let thumbUrl;
          if (imageType === 'backdrop') {
            thumbUrl = path.startsWith('/media/')
              ? resolveDetailsImageUrl(path, API_BASE, 'backdrop')
              : path.startsWith('/')
                ? buildTmdbImageUrl(path, TMDB_IMAGE_SIZES.backdropThumb)
                : resolveDetailsImageUrl(path, API_BASE, 'backdropThumb');
          } else if (imageType === 'poster') {
            thumbUrl = path.startsWith('/media/')
              ? resolveDetailsImageUrl(path, API_BASE, isPerson ? 'person' : 'poster')
              : path.startsWith('/')
                ? buildTmdbImageUrl(path, isPerson ? TMDB_IMAGE_SIZES.personThumb : TMDB_IMAGE_SIZES.posterThumb)
                : resolveDetailsImageUrl(path, API_BASE, isPerson ? 'person' : 'poster');
          } else {
            // Logo or generic
            thumbUrl = path.startsWith('/media/')
              ? resolveDetailsImageUrl(path, API_BASE, 'logo')
              : buildTmdbImageUrl(path, TMDB_IMAGE_SIZES.posterThumb);
          }

          const normalizedPath = path.split('/').pop().toLowerCase();
          const isImagePending = isPending && pendingPath === path;
          const isPathHttp = path.startsWith('http://') || path.startsWith('https://');
          const isCurrentHttp = currentPath && (currentPath.startsWith('http://') || currentPath.startsWith('https://'));
          const isSelected = (isPathHttp && isCurrentHttp)
            ? (path.toLowerCase() === currentPath.toLowerCase() || isImagePending)
            : ((normalizedCurrent !== '' && normalizedCurrent === normalizedPath) || isImagePending);

          const infoLeft = img.width && img.height ? `${img.width}×${img.height}` : '';
          const infoRight = img.vote_average ? `★ ${img.vote_average.toFixed(1)}` : '';

          return (
            <BackdropCard
              key={`${path}-${idx}`}
              imageUrl={thumbUrl}
              alt={`${imageType} ${idx + 1}`}
              isSelected={isSelected}
              isPending={isImagePending}
              infoLeft={infoLeft}
              infoRight={infoRight}
              onClick={() => handleSelectImage(path)}
              className={imageType === 'logo' ? 'ui-backdrop-card--logo' : (imageType === 'poster' ? 'ui-backdrop-card--poster' : '')}
            />
          );
        })}

        {images.length === 0 && (
          <EmptyState
            variant="detail-panel"
            icon={ImageOff}
            className="backdrops-panel__empty-state"
            title={t?.('library.details.noImagesAvailable') || `No ${imageType} options found.`}
          />
        )}

        {hasMore && (
          <div ref={loadMoreRef} className="backdrops-panel__load-more-trigger" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}

