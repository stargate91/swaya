import { useState, useEffect, useMemo } from 'react';
import { isEpisodeMediaType, isMovieOrEpisodeMediaType } from '@/lib/mediaTypes';

export function useOrganizerDetailsState({ sortedRows = [], paginatedRows = [] }) {
  const [activeRowId, setActiveRowId] = useState(null);
  const [activeImageIndex, setActiveImageIndex] = useState(0);
  const [isDetailsCollapsed, setIsDetailsCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('organizer_details_collapsed');
      return saved !== null ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  // Sync activeRowId with paginatedRows
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveRowId((current) => (paginatedRows.some((row) => row.id === current) ? current : null));
  }, [paginatedRows]);

  const activeRow = useMemo(
    () => sortedRows.find((row) => row.id === activeRowId) || null,
    [activeRowId, sortedRows]
  );

  // Reset image index when active row changes
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveImageIndex(0);
  }, [activeRow?.id]);

  const activeImages = activeRow?.images || [];
  const activeImage = activeImages[activeImageIndex] || activeImages[0] || null;

  const isScene = activeRow?.rawType === 'scene';
  const shouldShowDetailsPoster = (activeRow?.rawStatus === 'matched' || activeRow?.rawStatus === 'uncertain' || activeRow?.rawStatus === 'multiple') &&
    (isMovieOrEpisodeMediaType(activeRow?.rawType) || isScene) &&
    activeImages.length > 0;

  const shouldShowDetailsCarousel = isEpisodeMediaType(activeRow?.rawType) && activeImages.length > 1;

  const handleToggleDetails = () => {
    setIsDetailsCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem('organizer_details_collapsed', JSON.stringify(next));
      } catch {
        // Ignore storage access errors.
      }
      return next;
    });
  };

  const handleAdvanceDetailsImage = () => {
    if (activeImages.length <= 1) {
      return;
    }
    setActiveImageIndex((current) => (current + 1) % activeImages.length);
  };

  return {
    activeRowId,
    setActiveRowId,
    activeImageIndex,
    setActiveImageIndex,
    isDetailsCollapsed,
    setIsDetailsCollapsed,
    activeRow,
    activeImages,
    activeImage,
    shouldShowDetailsPoster,
    shouldShowDetailsCarousel,
    handleToggleDetails,
    handleAdvanceDetailsImage,
  };
}
