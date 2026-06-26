import { Image as ImageIcon, Link as LinkIcon, Sparkles } from 'lucide-react';
import PeopleTagPopover from './PeopleTagPopover';

export default function EntityDetailTopControls({
  isPeople,
  item,
  t,
  canChoosePeopleBackdrop,
  canChooseCollectionBackdrop,
  updatePersonStatusMutation,
  handleOpenPeopleBackdropModal,
  handleOpenCollectionBackdropModal,
  handleOpenLinkSourceModal,
  handleOpenDataMixerModal,
  extraLinks,
  socialLinks = [],
}) {
  if (isPeople) {
    return (
      <div className="entity-detail-page__top-controls">
        <PeopleTagPopover
          item={item}
          t={t}
          updatePersonStatusMutation={updatePersonStatusMutation}
        />
        {item?.is_adult ? (
          <>
            {item?.external_links && item.external_links.length > 0 ? (
              <button
                type="button"
                onClick={handleOpenDataMixerModal}
                className="media-detail-page__side-nav-toggle"
                title={t('library.details.dataMixer') || 'Performer Data Mixer'}
              >
                <Sparkles size={18} />
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleOpenLinkSourceModal}
              className="media-detail-page__side-nav-toggle"
              title={t('library.details.linkSource') || 'Link External Source'}
            >
              <LinkIcon size={18} />
            </button>
          </>
        ) : null}
        {canChoosePeopleBackdrop ? (
          <button
            type="button"
            onClick={handleOpenPeopleBackdropModal}
            className="media-detail-page__side-nav-toggle"
            title={t('library.details.backdrops') || 'Choose Backdrop'}
          >
            <ImageIcon size={18} />
          </button>
        ) : null}
      </div>
    );
  }

  if (!canChooseCollectionBackdrop) {
    return null;
  }

  return (
    <button
      type="button"
      onClick={handleOpenCollectionBackdropModal}
      className="media-detail-page__side-nav-toggle"
      title={t('library.details.backdrops') || 'Choose Backdrop'}
    >
      <ImageIcon size={18} />
    </button>
  );
}
