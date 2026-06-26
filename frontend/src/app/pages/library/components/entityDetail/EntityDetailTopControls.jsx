import { Image as ImageIcon, Settings } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
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
  extraLinks,
  socialLinks = [],
}) {
  const navigate = useNavigate();

  if (isPeople) {
    return (
      <div className="entity-detail-page__top-controls">
        <PeopleTagPopover
          item={item}
          t={t}
          updatePersonStatusMutation={updatePersonStatusMutation}
        />
        {item?.is_adult ? (
          <button
            type="button"
            onClick={() => navigate(`/library/people/${item.id}/edit`)}
            className="media-detail-page__side-nav-toggle"
            title="Edit Performer"
          >
            <Settings size={18} />
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
