import { FolderOpen, Video, Check, Eye, Play, BellPlus, Flame, Info } from 'lucide-react';
import Button from '@/ui/Button';
import { formatEpisodeNumber } from '../../utils/detailUtils';
import { useMediaDetailContext } from './MediaDetailContext';

export default function MediaActions() {
  const { state, actions, mutations, t, navigate, setIsDrawerOpen } = useMediaDetailContext();
  const {
    isOwned,
    isMovie,
    isScene,
    item,
    isTracked,
    canToggleTracked,
    isWatched,
    canToggleWatched,
    nextEpisodeInfo,
    cleanId,
    effectiveId
  } = state;

  const {
    handleTrailerClick,
    handleToggleWatched,
    handleToggleTracked,
    handlePlayClick
  } = actions;

  const {
    updateStatusMutation,
    bulkUpdateWatchedMutation,
    toggleTrackedMutation,
    playMutation,
    addPeakMutation
  } = mutations;

  const hasCollection = isMovie && item?.collection_data;
  const hasTrailer = item?.trailer_key;

  if (!isOwned && !canToggleTracked && !canToggleWatched && !hasCollection && !hasTrailer) return null;

  return (
    <div className="media-detail-page__actions-row">
      {hasCollection && (
        <Button
          variant="ghost"
          onClick={() => navigate(`/library/collection/${item?.collection_data.tmdb_id}`)}
        >
          <FolderOpen size={16} />
          {t('library.details.collection') || 'Collection'}
        </Button>
      )}

      {hasTrailer && (
        <Button
          variant="ghost"
          onClick={handleTrailerClick}
        >
          <Video size={16} />
          {t('library.details.trailer') || 'Trailer'}
        </Button>
      )}

      {canToggleWatched && (
        <Button
          variant="ghost"
          onClick={handleToggleWatched}
          disabled={updateStatusMutation.isPending || bulkUpdateWatchedMutation.isPending}
        >
          {isWatched ? <Check size={16} /> : <Eye size={16} />}
          {isWatched ? (t('library.details.watched') || 'Watched') : (t('library.details.markWatched') || 'Mark as Watched')}
        </Button>
      )}

      {canToggleTracked && (
        <Button
          variant="ghost"
          onClick={handleToggleTracked}
          disabled={toggleTrackedMutation.isPending}
        >
          {isTracked ? <Check size={16} /> : <BellPlus size={16} />}
          {isTracked ? 'Tracked' : 'Track'}
        </Button>
      )}

      {!isScene && (
        <Button
          variant="ghost"
          onClick={() => setIsDrawerOpen(true)}
        >
          <Info size={16} />
          {t('library.details.details') || 'Details'}
        </Button>
      )}

      {isOwned && (
        <>
          {(item?.is_adult && (isMovie || isScene)) && (
            <Button
              variant="ghost"
              onClick={() => addPeakMutation.mutate({ itemId: effectiveId, tvId: cleanId })}
              disabled={addPeakMutation.isPending}
            >
              <Flame size={16} />
              {t('library.details.addPeak') || 'Add Peak'}
            </Button>
          )}

          {isMovie || isScene ? (
            <Button
              variant="secondary"
              onClick={handlePlayClick}
              disabled={playMutation.isPending}
            >
              <Play size={16} fill="currentColor" />
              {item?.resume_position > 0 ? (t('library.details.resume') || 'Resume') : (t('library.details.play') || 'Play')}
            </Button>
          ) : (
            nextEpisodeInfo && (
              <Button
                variant="secondary"
                onClick={handlePlayClick}
                disabled={playMutation.isPending}
              >
                <Play size={16} fill="currentColor" />
                {t('library.details.continueEpisode', { defaultValue: 'Continue S{{season}} E{{episode}}', season: nextEpisodeInfo.seasonNumber, episode: formatEpisodeNumber(nextEpisodeInfo.episode.episode_number) })}
              </Button>
            )
          )}
        </>
      )}
    </div>
  );
}
