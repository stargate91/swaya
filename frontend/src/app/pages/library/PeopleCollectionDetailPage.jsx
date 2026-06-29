import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from '@/providers/LanguageContext';
import { useUi } from '@/providers/UiProvider';
import { Plus, Minus, ChevronDown, ChevronUp } from 'lucide-react';
import DetailPageShell from './components/detail/DetailPageShell';
import EntityDetailTopControls from './components/entityDetail/EntityDetailTopControls';
import EntityDetailStatusSection from './components/entityDetail/EntityDetailStatusSection';
import EntityDetailHeroSection from './components/entityDetail/EntityDetailHeroSection';
import PersonCreditsSections from './components/entityDetail/PersonCreditsSections';
import CollectionDetailSections from './components/entityDetail/CollectionDetailSections';
import usePeopleCollectionDetailController from './usePeopleCollectionDetailController.jsx';
import UniversalImagePickerModal from './modals/UniversalImagePickerModal';
import UtilityBarBottomPortal from '../../../components/UtilityBarBottomPortal';
import './PeopleCollectionDetailPage.css';
import './components/detail/UserRatingSection.css';
import './components/detail/panels/BackdropsPanel.css';
export default function PeopleCollectionDetailPage({ type = 'people' }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { openModal, closeModal, toast } = useUi();
  const isPeople = type === 'people';
  const {
    item,
    isLoading,
    queryError,
    hasError,
    overviewTitle,
    overviewText,
    overviewEmptyText,
    profileLinks,
    extraLinks,
    socialLinks,
    backdropUrl,
    mediaUrl,
    metaPills,
    extraMetaPills,
    displayRating,
    isActivateHovered,
    starsStyleSheetText,
    canChoosePeopleBackdrop,
    canChooseCollectionBackdrop,
    updatePersonStatusMutation,
    setIsActivateHovered,
    handlePeopleRatingMouseMove,
    handlePeopleRatingMouseLeave,
    handlePeopleRatingClick,
    handleToggleFavorite,
    handleToggleActive,
    handleOpenReviewModal,
    handleOpenCollectionBackdropModal,
    handleOpenPeopleBackdropModal,
  } = usePeopleCollectionDetailController({
    id,
    isPeople,
    t,
    openModal,
    closeModal,
    toast,
  });

  const [isSocialExpanded, setIsSocialExpanded] = useState(false);
  const [isScrolled, setIsScrolled] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsScrolled(false);
  }, [id]);

  useEffect(() => {
    const handleWheel = (e) => {
      if (Math.abs(e.deltaY) > 5) {
        if (e.deltaY > 0 && !isScrolled) {
          setIsScrolled(true);
        } else if (e.deltaY < 0 && isScrolled) {
          const isInsideSection = e.target.closest('.person-credits-section-container');
          if (isInsideSection) {
            const scrollable = isInsideSection.querySelector('.person-credits-discover-grid-wrapper, .person-credits-discover-grid');
            if (scrollable && scrollable.scrollTop > 0) {
              return;
            }
          }
          setIsScrolled(false);
        }
      }
    };

    window.addEventListener('wheel', handleWheel, { passive: true });
    return () => window.removeEventListener('wheel', handleWheel);
  }, [isScrolled]);

  const handleScrollArrowClick = useCallback(() => {
    setIsScrolled(true);
  }, []);

  const hasExtraSocials = socialLinks.length > 4;
  const mainSocialLinks = hasExtraSocials ? socialLinks.slice(0, 4) : socialLinks;
  const extraSocialLinks = hasExtraSocials ? socialLinks.slice(4) : [];

  const handleOpenImagePickerModal = () => {
    const idToUse = isPeople ? item?.id : `collection_${item?.tmdb_id}`;
    if (!idToUse) return;
    openModal({
      title: isPeople ? (t('library.details.changeProfile') || 'Change Profile Picture') : (t('library.details.changePoster') || 'Change Poster'),
      variant: 'wide',
      content: (
        <UniversalImagePickerModal
          entityId={idToUse}
          entityType={isPeople ? 'person' : 'collection'}
          imageType={isPeople ? 'profile' : 'poster'}
          externalIds={item?.external_ids}
          item={item}
          t={t}
          toast={toast}
          onClose={closeModal}
          onImageSelected={() => {
            closeModal();
            toast.success(t('library.details.imageUpdatedSuccessfully') || 'Image updated successfully');
          }}
        />
      ),
    });
  };



  return (
    <DetailPageShell
      containerRef={containerRef}
      backdropUrl={backdropUrl}
      fallbackUrl={mediaUrl}
      backLabel={t('common.back') || 'Back'}
      isLoading={isLoading}
      pageClassName={`entity-detail-page ${isPeople ? 'entity-detail-page--people' : 'entity-detail-page--collection'} ${isScrolled ? 'is-scrolled' : ''}`}
      topRightControls={
        <EntityDetailTopControls
          isPeople={isPeople}
          item={item}
          t={t}
          canChoosePeopleBackdrop={canChoosePeopleBackdrop}
          canChooseCollectionBackdrop={canChooseCollectionBackdrop}
          updatePersonStatusMutation={updatePersonStatusMutation}
          handleOpenPeopleBackdropModal={handleOpenPeopleBackdropModal}
          handleOpenCollectionBackdropModal={handleOpenCollectionBackdropModal}
          extraLinks={extraLinks}
          socialLinks={socialLinks}
        />
      }
    >
      {hasError && (
        <EntityDetailStatusSection
          title={isPeople ? 'Unable to load person' : 'Unable to load collection'}
          message={queryError?.message || 'The detail request failed.'}
        />
      )}

      {!hasError && !item && !isLoading && (
        <EntityDetailStatusSection
          title={isPeople ? 'Person not found' : 'Collection not found'}
          message={isPeople ? 'No person detail was returned for this route.' : 'No collection detail was returned for this route.'}
        />
      )}

      {!hasError && (
        <div className="entity-detail-page__transition-wrapper">
          <EntityDetailHeroSection
            isPeople={isPeople}
            item={item}
            isScrolled={isScrolled}
            onScrollArrowClick={handleScrollArrowClick}
            mediaUrl={mediaUrl}
            profileLinks={profileLinks}
            extraLinks={extraLinks}
            socialLinks={socialLinks}
            metaPills={metaPills}
            extraMetaPills={extraMetaPills}
            overviewText={overviewText}
            overviewTitle={overviewTitle}
            overviewEmptyText={overviewEmptyText}
            displayRating={displayRating}
            isActivateHovered={isActivateHovered}
            starsStyleSheetText={starsStyleSheetText}
            t={t}
            openModal={openModal}
            setIsActivateHovered={setIsActivateHovered}
            handleToggleFavorite={handleToggleFavorite}
            handleToggleActive={handleToggleActive}
            handleOpenReviewModal={handleOpenReviewModal}
            handlePeopleRatingMouseMove={handlePeopleRatingMouseMove}
            handlePeopleRatingMouseLeave={handlePeopleRatingMouseLeave}
            handlePeopleRatingClick={handlePeopleRatingClick}
            onMediaCardClick={handleOpenImagePickerModal}
          />

          {isPeople && (
            <PersonCreditsSections
              id={id}
              item={item}
              isScrolled={isScrolled}
              navigate={navigate}
              t={t}
            />
          )}

          {!isPeople && (
            <CollectionDetailSections
              item={item}
              navigate={navigate}
              t={t}
            />
          )}
        </div>
      )}
      {!hasError && isPeople && socialLinks.length > 0 && (
        <UtilityBarBottomPortal side="right">
          <div className={`entity-detail-page__bottom-socials ${isSocialExpanded ? 'entity-detail-page__bottom-socials--expanded' : ''}`}>
            <div className="entity-detail-page__bottom-socials-wrapper">
              {hasExtraSocials && (
                <div className="entity-detail-page__bottom-socials-extra">
                  {extraSocialLinks.map((link) => (
                    <a
                      key={link.key}
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="entity-detail-page__bottom-social-btn"
                      title={link.label}
                    >
                      <img src={link.iconSrc || '/links/website.svg'} alt={link.label} />
                    </a>
                  ))}
                </div>
              )}

              <div className="entity-detail-page__bottom-socials-main">
                {mainSocialLinks.map((link) => (
                  <a
                    key={link.key}
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="entity-detail-page__bottom-social-btn"
                    title={link.label}
                  >
                    <img src={link.iconSrc || '/links/website.svg'} alt={link.label} />
                  </a>
                ))}
              </div>

              {hasExtraSocials && (
                <button
                  type="button"
                  className="entity-detail-page__bottom-social-toggle"
                  onClick={() => setIsSocialExpanded(!isSocialExpanded)}
                  title={isSocialExpanded ? (t('common.less') || 'Show Less') : (t('common.more') || 'Show More')}
                >
                  {isSocialExpanded ? <Minus size={14} /> : <Plus size={14} />}
                </button>
              )}
            </div>
          </div>
        </UtilityBarBottomPortal>
      )}

      {!hasError && isPeople && (
        <div className={`entity-detail-page__scroll-toggle-container ${isScrolled ? 'is-scrolled' : ''}`}>
          <button
            type="button"
            className="entity-detail-page__scroll-toggle-btn"
            onClick={() => setIsScrolled(!isScrolled)}
            title={isScrolled ? (t('library.details.backToProfile') || 'Back to Profile') : (t('library.details.scrollToCredits') || 'Scroll to Credits')}
          >
            {isScrolled ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
        </div>
      )}
    </DetailPageShell>
  );
}
