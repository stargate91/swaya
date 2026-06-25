import { Image as ImageIcon, Link as LinkIcon } from 'lucide-react';
import PeopleTagPopover from './PeopleTagPopover';
import PeopleLinksPopover from './PeopleLinksPopover';

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
  extraLinks,
}) {
  if (isPeople) {
    return (
      <div className="entity-detail-page__top-controls">
        <PeopleLinksPopover extraLinks={extraLinks} t={t} />
        <PeopleTagPopover
          item={item}
          t={t}
          updatePersonStatusMutation={updatePersonStatusMutation}
        />
        {item?.is_adult ? (
          <button
            type="button"
            onClick={handleOpenLinkSourceModal}
            className="media-detail-page__side-nav-toggle"
            title={t('library.details.linkSource') || 'Link External Source'}
          >
            <LinkIcon size={18} />
          </button>
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
