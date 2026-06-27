import { useState } from 'react';
import { useMediaDetailContext } from '../MediaDetailContext';
import TMDBImageGrid from '../../entityDetail/TMDBImageGrid';
import ImageUploadPanel from '../../../modals/ImageUploadPanel';
import { useUploadBackdropMutation } from '@/queries/mediaQueries';
import { resolveMediaImageUrl } from '@/lib/imageUrls';
import './BackdropsPanel.css';

export default function BackdropsPanel({ showTitle = true }) {
  const { state, mutations, id, type, t, toast } = useMediaDetailContext();
  const {
    item
  } = state;

  const {
    overrideBackdropMutation
  } = mutations;

  const uploadBackdropMutation = useUploadBackdropMutation();
  const [prevBackdropPath, setPrevBackdropPath] = useState(item?.backdrop_path || '');
  const [selectedBackdropPath, setSelectedBackdropPath] = useState(item?.backdrop_path || '');

  if (item?.backdrop_path && item.backdrop_path !== prevBackdropPath) {
    setPrevBackdropPath(item.backdrop_path);
    setSelectedBackdropPath(item.backdrop_path);
  }

  const handleUploadBackdrop = async (file) => {
    if (!file || uploadBackdropMutation.isPending) return;
    try {
      const data = await uploadBackdropMutation.mutateAsync({ itemId: id, file, mediaType: type });
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
        itemId: id,
        backdropPath: backdropPath,
        mediaType: type,
      });
      toast(t('library.details.backdropUpdated') || 'Backdrop updated successfully!', 'success');
    } catch (err) {
      toast(err.message || t('library.details.backdropUpdateFailed') || 'Failed to update backdrop', 'danger');
    }
  };

  const isScene = type === 'scene' || item?.type === 'scene' || (typeof id === 'string' && id.startsWith('stash_'));

  return (
    <div className="backdrops-panel">
      {showTitle && (
        <h4 className="details-panel__section-title">
          {t('library.details.chooseBackdrop') || 'Choose Backdrop'}
        </h4>
      )}

      <ImageUploadPanel
        imageType="backdrop"
        isPending={overrideBackdropMutation.isPending || uploadBackdropMutation.isPending}
        t={t}
        onSaveUrl={handleSelectBackdrop}
        onUploadFile={handleUploadBackdrop}
      />

      {isScene && item?.original_backdrop_path && (
        <div className="scene-image-picker-options">
          <h4 className="scene-image-picker-title">{t('library.details.availableBackdrops') || 'Available Backdrops'}</h4>
          <div className="scene-image-picker-grid">
            <div 
              className={`scene-image-picker-card ${selectedBackdropPath === item.original_backdrop_path ? 'active' : ''}`}
              role="button"
              tabIndex={0}
              onClick={() => handleSelectBackdrop(item.original_backdrop_path)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  handleSelectBackdrop(item.original_backdrop_path);
                }
              }}
            >
              <div className="scene-image-picker-img-wrapper backdrop-variant">
                <img src={resolveMediaImageUrl(item.original_backdrop_path, 'backdrop')} alt="Original Scene Backdrop" />
              </div>
              <span className="scene-image-picker-label">{t('library.details.originalSceneBackdrop') || 'Original Scene Still'}</span>
            </div>
          </div>
        </div>
      )}

      {!isScene && (
        <TMDBImageGrid
          itemId={id}
          tmdbId={item?.tmdb_id || item?.tv_tmdb_id}
          mediaType={type}
          imageType="backdrop"
          currentPath={selectedBackdropPath}
          onSelect={handleSelectBackdrop}
          isPending={overrideBackdropMutation.isPending || uploadBackdropMutation.isPending}
          pendingPath={overrideBackdropMutation.variables?.backdropPath}
          initialVisibleCount={12}
          visibleStep={12}
          t={t}
        />
      )}
    </div>
  );
}
