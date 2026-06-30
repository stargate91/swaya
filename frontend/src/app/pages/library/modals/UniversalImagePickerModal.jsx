import { useState } from 'react';
import TMDBImageGrid from '../components/entityDetail/TMDBImageGrid';
import SegmentedControl from '@/ui/SegmentedControl';
import {
  useOverrideBackdropMutation,
  useUploadBackdropMutation,
  useOverridePosterMutation,
  useUploadPosterMutation,
  useOverrideLogoMutation,
  useUploadLogoMutation,
} from '@/queries/mediaQueries';
import {
  useOverridePersonProfileMutation,
  useUploadPersonProfileMutation,
} from '@/queries/libraryQueries';
import ImageUploadPanel from './ImageUploadPanel';
import { resolveMediaImageUrl } from '@/lib/imageUrls';
import './UniversalImagePickerModal.css';

const COLON_CHAR = ':';

const pathsMatch = (pathA, pathB) => {
  if (!pathA || !pathB) return false;
  const cleanA = String(pathA).split(/[/\\]/).pop().toLowerCase();
  const cleanB = String(pathB).split(/[/\\]/).pop().toLowerCase();
  return cleanA === cleanB;
};

export default function UniversalImagePickerModal({
  entityId,
  tmdbId,
  imageType = 'backdrop',
  entityType = 'movie',
  currentPath,
  t,
  toast,
  onClose,
  externalIds,
  item,
}) {
  const overrideBackdropMutation = useOverrideBackdropMutation();
  const uploadBackdropMutation = useUploadBackdropMutation();
  const overridePosterMutation = useOverridePosterMutation();
  const uploadPosterMutation = useUploadPosterMutation();
  const overrideLogoMutation = useOverrideLogoMutation();
  const uploadLogoMutation = useUploadLogoMutation();
  const overridePersonProfileMutation = useOverridePersonProfileMutation();
  const uploadPersonProfileMutation = useUploadPersonProfileMutation();

  // Compute available sources
  const sources = [];
  if (entityType === 'person') {
    const hasStash = !!externalIds?.stashdb_id || !!item?.stashdb_id || !!item?.external_ids?.stashdb_id;
    const hasFans = !!externalIds?.fansdb_id || !!item?.fansdb_id || !!item?.external_ids?.fansdb_id;
    const hasPornDb = !!externalIds?.theporndb_id || !!item?.theporndb_id || !!item?.external_ids?.theporndb_id || !!externalIds?.porndb_id || !!item?.porndb_id || !!item?.external_ids?.porndb_id;
    const hasTMDb = !!externalIds?.tmdb_id || !!item?.tmdb_id || !!item?.external_ids?.tmdb_id || (!hasStash && !hasFans && !hasPornDb);

    if (hasTMDb) sources.push({ value: 'tmdb', label: 'TMDb' });
    if (hasStash) sources.push({ value: 'stashdb', label: 'StashDB' });
    if (hasFans) sources.push({ value: 'fansdb', label: 'FansDB' });
    if (hasPornDb) sources.push({ value: 'theporndb', label: 'THEPornDB' });

    console.log('UniversalImagePickerModal: Performer sources computed:', {
      externalIds,
      tmdbId,
      hasStash,
      hasFans,
      hasPornDb,
      hasTMDb,
      sources
    });
  }

  const [prevCurrentPath, setPrevCurrentPath] = useState(currentPath);
  const [selectedPath, setSelectedPath] = useState(currentPath);

  if (prevCurrentPath !== currentPath) {
    setPrevCurrentPath(currentPath);
    setSelectedPath(currentPath);
  }

  const [imageSource, setImageSource] = useState(() => {
    return sources.length > 0 ? sources[0].value : 'tmdb';
  });

  const handleSelectTmdbImage = async (path) => {
    setSelectedPath(path);
    try {
      if (imageType === 'backdrop') {
        await overrideBackdropMutation.mutateAsync({
          itemId: entityId,
          backdropPath: path,
          mediaType: entityType,
        });
      } else if (imageType === 'poster') {
        await overridePosterMutation.mutateAsync({
          itemId: entityId,
          posterPath: path,
          mediaType: entityType,
        });
      } else if (imageType === 'logo') {
        await overrideLogoMutation.mutateAsync({
          itemId: entityId,
          logoPath: path,
          mediaType: entityType,
        });
      } else if (imageType === 'profile' && entityType === 'person') {
        await overridePersonProfileMutation.mutateAsync({
          personId: entityId,
          profilePath: path,
        });
      }
      toast(t?.('library.details.imageUpdated') || 'Image updated successfully!', 'success');
      onClose?.();
    } catch (err) {
      toast(err.message || t?.('library.details.imageUpdateFailed') || 'Failed to update image', 'danger');
    }
  };

  const handleUploadFile = async (file) => {
    if (!file) return;

    try {
      if (imageType === 'backdrop') {
        await uploadBackdropMutation.mutateAsync({
          itemId: entityId,
          file,
          mediaType: entityType,
        });
      } else if (imageType === 'poster') {
        await uploadPosterMutation.mutateAsync({
          itemId: entityId,
          file,
          mediaType: entityType,
        });
      } else if (imageType === 'logo') {
        await uploadLogoMutation.mutateAsync({
          itemId: entityId,
          file,
          mediaType: entityType,
        });
      } else if (imageType === 'profile' && entityType === 'person') {
        await uploadPersonProfileMutation.mutateAsync({
          personId: entityId,
          file,
        });
      }
      toast(t?.('library.details.imageUploaded') || 'Image uploaded and updated successfully!', 'success');
      onClose?.();
    } catch (err) {
      toast(err.message || t?.('library.details.imageUploadFailed') || 'Failed to upload image', 'danger');
    }
  };

  const isPending =
    overrideBackdropMutation.isPending ||
    uploadBackdropMutation.isPending ||
    overridePosterMutation.isPending ||
    uploadPosterMutation.isPending ||
    overrideLogoMutation.isPending ||
    uploadLogoMutation.isPending ||
    overridePersonProfileMutation.isPending ||
    uploadPersonProfileMutation.isPending;

  const isScene = entityType === 'scene' || item?.type === 'scene' || (typeof entityId === 'string' && entityId.startsWith('stash_'));

  return (
    <div className="universal-image-picker">
      <ImageUploadPanel
        imageType={imageType}
        isPending={isPending}
        t={t}
        onSaveUrl={handleSelectTmdbImage}
        onUploadFile={handleUploadFile}
      />

      {isScene && imageType === 'logo' && (
        <div className="scene-image-picker-options scene-image-picker-options--logo">
          <h4 className="scene-image-picker-title">{t('library.details.availableLogos') || 'Available Logos'}</h4>
          <div className="scene-image-picker-grid">
            {(() => {
              const logoOptions = [];
              const seenLogos = new Set();

              if (item?.original_logo_path) {
                logoOptions.push({
                  path: item.original_logo_path,
                  label: t('library.details.originalSceneLogo') || 'Original Scene Logo',
                  alt: 'Original Logo',
                });
                seenLogos.add(item.original_logo_path);
              }

              if (item?.companies?.[0]?.logo_path && !seenLogos.has(item.companies[0].logo_path)) {
                logoOptions.push({
                  path: item.companies[0].logo_path,
                  label: item.companies[0].name || 'Studio Logo',
                  alt: item.companies[0].name || 'Studio',
                });
                seenLogos.add(item.companies[0].logo_path);
              }

              if (item?.networks?.[0]?.logo_path && !seenLogos.has(item.networks[0].logo_path)) {
                logoOptions.push({
                  path: item.networks[0].logo_path,
                  label: item.networks[0].name || 'Network Logo',
                  alt: item.networks[0].name || 'Network',
                });
                seenLogos.add(item.networks[0].logo_path);
              }

              return logoOptions.map((opt, idx) => (
                <div
                  key={idx}
                  className={`scene-image-picker-card ${pathsMatch(selectedPath || currentPath, opt.path) ? 'active' : ''}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectTmdbImage(opt.path)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      handleSelectTmdbImage(opt.path);
                    }
                  }}
                >
                  <div className="scene-image-picker-img-wrapper">
                    <img src={resolveMediaImageUrl(opt.path, 'logo')} alt={opt.alt} />
                  </div>
                  <span className="scene-image-picker-label">{opt.label}</span>
                </div>
              ));
            })()}
          </div>
        </div>
      )}

      {isScene && (imageType === 'poster' || imageType === 'backdrop') && (
        <div className="scene-image-picker-options">
          <h4 className="scene-image-picker-title">
            {imageType === 'poster'
              ? (t('library.details.availablePosters') || 'Available Posters')
              : (t('library.details.availableBackdrops') || 'Available Backdrops')}
          </h4>
          <div className="scene-image-picker-grid">
            {(() => {
              const options = [];
              if (item?.original_backdrop_path) {
                options.push({
                  path: item.original_backdrop_path,
                  label: t('library.details.originalSceneStill') || 'Original Scene Still',
                  alt: 'Original Still',
                });
              }

              return options.map((opt, idx) => (
                <div
                  key={idx}
                  className={`scene-image-picker-card ${pathsMatch(selectedPath || currentPath, opt.path) ? 'active' : ''}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectTmdbImage(opt.path)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      handleSelectTmdbImage(opt.path);
                    }
                  }}
                >
                  <div className="scene-image-picker-img-wrapper backdrop-variant">
                    <img src={resolveMediaImageUrl(opt.path, imageType)} alt={opt.alt} />
                  </div>
                  <span className="scene-image-picker-label">{opt.label}</span>
                </div>
              ));
            })()}
          </div>
        </div>
      )}

      {sources.length > 1 && (
        <div className="universal-image-picker__source-filter">
          <SegmentedControl
            value={imageSource}
            onChange={(val) => setImageSource(val)}
            options={sources}
          />
        </div>
      )}

      {!isScene && (
        <div className="universal-image-picker__grid">
          <TMDBImageGrid
            itemId={entityId}
            tmdbId={tmdbId}
            mediaType={entityType}
            imageType={imageType === 'profile' ? 'poster' : imageType}
            currentPath={selectedPath || currentPath}
            onSelect={handleSelectTmdbImage}
            isPending={isPending}
            t={t}
            selectedSource={imageSource}
          />
        </div>
      )}
    </div>
  );
}
