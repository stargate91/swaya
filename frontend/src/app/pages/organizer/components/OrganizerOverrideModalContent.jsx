import { useState, useMemo } from 'react';
import Dropdown from '../../../ui/Dropdown';
import SelectableCard from '../../../ui/SelectableCard';
import { useTranslation } from '../../../providers/LanguageContext';
import { useQueryClient } from '@tanstack/react-query';
import { useUpdateMediaMutation } from '../../../queries';
import { isEpisodeMediaType } from '@/lib/mediaTypes';
import OverrideMovieFields from './OverrideMovieFields';
import OverrideEpisodeFields from './OverrideEpisodeFields';
import OverrideExtraFields from './OverrideExtraFields';

import { useLibraryModeStore } from '@/stores/useLibraryModeStore';

import {
  SUBCATEGORIES_BY_CATEGORY,
  LANGUAGE_OPTIONS,
  SOURCE_OPTIONS,
  EDITION_OPTIONS,
  AUDIO_TYPE_OPTIONS,
  MAIN_TYPE_OPTIONS,
} from './overrideConstants';

export default function OrganizerOverrideModalContent({ row, onClose, toast }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const sessionMode = useLibraryModeStore((state) => state.sessionMode);

  const translatedLanguageOptions = useMemo(() =>
    LANGUAGE_OPTIONS.map((opt) => ({
      ...opt,
      label: t(`languages.${opt.value}`) || opt.label,
    })),
    [t]
  );
  const isExtra = row.rawType === 'extra';
  const category = isExtra ? (row.rawPayload?.category || 'video') : 'video';

  const translatedSubcategoriesByCategory = useMemo(() => {
    const result = {};
    Object.keys(SUBCATEGORIES_BY_CATEGORY).forEach((catKey) => {
      result[catKey] = SUBCATEGORIES_BY_CATEGORY[catKey].map((opt) => ({
        ...opt,
        label: t(`organizer.overrideModal.options.subcategories.${opt.value}`) || opt.label,
      }));
    });
    return result;
  }, [t]);

  const translatedSourceOptions = useMemo(() =>
    SOURCE_OPTIONS.map((opt) => ({
      ...opt,
      label: t(`organizer.overrideModal.options.sources.${opt.value}`) || opt.label,
    })),
    [t]
  );

  const translatedEditionOptions = useMemo(() =>
    EDITION_OPTIONS.map((opt) => ({
      ...opt,
      label: t(`organizer.overrideModal.options.editions.${opt.value}`) || opt.label,
    })),
    [t]
  );

  const translatedAudioTypeOptions = useMemo(() =>
    AUDIO_TYPE_OPTIONS.map((opt) => ({
      ...opt,
      label: t(`organizer.overrideModal.options.audioTypes.${opt.value}`) || opt.label,
    })),
    [t]
  );

  const translatedMainTypeOptions = useMemo(() => {
    const isScenesMode = row.rawPayload?.scan_mode === 'scenes' || row.rawPayload?.parent_scan_mode === 'scenes';
    if (isScenesMode) {
      return [
        { value: 'scene', label: t('organizer.overrideModal.options.mainTypes.scene') || 'Scene' },
        { value: 'bonus', label: t('organizer.overrideModal.options.mainTypes.bonus') || 'Bonus Video' },
      ];
    }
    return MAIN_TYPE_OPTIONS.map((opt) => ({
      ...opt,
      label: t(`organizer.overrideModal.options.mainTypes.${opt.value}`) || opt.label,
    }));
  }, [t, row.rawPayload]);

  // Get parent candidates (movies + tv) from cache
  const organizer = queryClient.getQueryData(['organizer']) || {};
  const movies = organizer.movies || [];
  const tv = organizer.tv || [];

  const isParentCandidateAdult = (item) => {
    const itemScanMode = item.scan_mode || '';
    return item.matches?.some((m) => m.is_adult)
      || String(item.type).toLowerCase() === 'scene'
      || itemScanMode === 'porndb_movie'
      || itemScanMode === 'scenes';
  };

  const isExtraAdult = sessionMode === 'nsfw';

  const isExtraScene = row.rawType === 'extra'
    ? (row.parentType === 'scene' || (row.rawPayload?.parent_scan_mode === 'scenes'))
    : (String(row.type || row.rawType).toLowerCase() === 'scene' || row.scan_mode === 'scenes' || row.rawPayload?.scan_mode === 'scenes');

  const filteredMoviesAndTv = [...movies, ...tv].filter((item) => {
    // 0. Cannot select itself as parent
    if (item.id === row.itemId) return false;

    const isParentAdult = isParentCandidateAdult(item);
    // 1. Must match SFW/NSFW
    if (isExtraAdult !== isParentAdult) return false;

    // 2. Within NSFW, scenes must go to scenes, and adult movies/tv to adult movies/tv
    if (isExtraAdult) {
      const isParentScene = String(item.type).toLowerCase() === 'scene' || item.scan_mode === 'scenes';
      if (isExtraScene !== isParentScene) return false;
    }

    return true;
  });

  const parentCandidates = filteredMoviesAndTv.map((item) => ({
    value: item.id,
    label: item.filename || item.current_path || `ID: ${item.id}`,
  }));

  // Initial values setup
  const initialMainType = isExtra
    ? (category === 'video' ? 'bonus' : 'extra')
    : row.rawType;

  const initialSeason = useMemo(() => row.rawPayload?.season ?? '', [row.rawPayload]);
  const initialEpisode = useMemo(() => row.rawPayload?.episode ?? '', [row.rawPayload]);

  const [mainType, setMainType] = useState(initialMainType);

  const subcategoryList = translatedSubcategoriesByCategory[mainType === 'bonus' ? 'video' : category] || [];

  const [targetLanguage, setTargetLanguage] = useState(row.rawPayload?.target_language || 'en');
  const [source, setSource] = useState(row.rawPayload?.custom_source || 'none');
  const [edition, setEdition] = useState(row.rawPayload?.custom_edition || 'none');
  const [audioType, setAudioType] = useState(row.rawPayload?.custom_audio_type || 'none');
  const [seasonNum, setSeasonNum] = useState(initialSeason);
  const [episodeNum, setEpisodeNum] = useState(initialEpisode);
  const [subcategory, setSubcategory] = useState(row.rawPayload?.subtype || 'other');
  const [language, setLanguage] = useState((row.rawPayload?.language || 'en').toLowerCase());
  const [parentId, setParentId] = useState(row.parent_id || (parentCandidates[0]?.value || ''));
  const [matchAction, setMatchAction] = useState('keep');
  const updateMediaMutation = useUpdateMediaMutation();

  const isMatchedEpisode = isEpisodeMediaType(row.rawType) && row.rawStatus === 'matched';
  const isSeasonModified = String(seasonNum) !== String(initialSeason);
  const isEpisodeModified = String(episodeNum) !== String(initialEpisode);
  const showSelector = isMatchedEpisode && (isSeasonModified || isEpisodeModified);

  const activeMatch = useMemo(() =>
    row.rawPayload?.matches?.find((m) => m.is_active) || row.rawPayload?.matches?.[0],
    [row.rawPayload]
  );
  const hideLanguage = useMemo(() => {
    const isScenesMode = row.rawPayload?.scan_mode === 'scenes' || row.rawPayload?.parent_scan_mode === 'scenes';
    const hasAdultProviderMatch = activeMatch && ['porndb', 'stashdb', 'fansdb'].includes(activeMatch.provider);
    return isScenesMode || hasAdultProviderMatch;
  }, [row.rawPayload, activeMatch]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (mainType === 'episode') {
      const isSeasonEmpty = !String(seasonNum ?? '').trim();
      const isEpisodeEmpty = !String(episodeNum ?? '').trim();
      if (isSeasonEmpty || isEpisodeEmpty) {
        toast(t('organizer.toasts.overrideSeasonEpisodeRequired'), 'danger');
        return;
      }
    }

    if ((mainType === 'bonus' || (isExtra && mainType !== 'movie' && mainType !== 'episode')) && String(parentId) === String(row.itemId)) {
      toast(t('organizer.toasts.selfParentError') || 'An item cannot be its own parent.', 'danger');
      return;
    }

    const payload = {
      id: row.itemId,
      type: isExtra ? 'extra' : 'media',
    };

    if (showSelector && matchAction === 'reset') {
      payload.reset_match = true;
    }

    if (!isExtra) {
      // Media updates
      payload.main_type = mainType;
      if (mainType === 'bonus') {
        payload.parent_id = parentId;
      } else {
        payload.custom_language = targetLanguage;
        payload.custom_audio_type = audioType;
        if (mainType === 'movie') {
          payload.custom_source = source;
          payload.custom_edition = edition;
        } else if (mainType === 'episode') {
          payload.season = seasonNum;
          payload.episode = episodeNum;
        }
      }
    } else {
      // Extra updates
      payload.main_type = mainType; // could trigger convert to movie/episode
      if (mainType === 'movie' || mainType === 'episode') {
        payload.parent_id = parentId; // not strictly needed for media but useful
        if (mainType === 'episode') {
          payload.season = seasonNum;
          payload.episode = episodeNum;
        }
      } else {
        payload.parent_id = parentId;
        if (category !== 'metadata') {
          payload.subtype = subcategory;
        }
        if (category === 'subtitle' || category === 'audio') {
          payload.language = language;
        }
      }
    }

    updateMediaMutation.mutate(payload, {
      onSuccess: () => {
        toast(t('organizer.toasts.overrideSuccess'), 'success');
      },
      onError: (err) => {
        toast(err.message || t('organizer.toasts.overrideSaveFailed'), 'danger');
      },
    });
    onClose();
  };

  const renderFormFields = () => (
    <>
      {/* 1. Main Category Choice */}
      {(!isExtra || category === 'video') && (
        <Dropdown
          label={t('organizer.overrideModal.labels.mainCategory')}
          value={mainType}
          onChange={(e) => setMainType(e.target.value)}
          options={translatedMainTypeOptions}
          hint={t('organizer.overrideModal.hints.mainType')}
        />
      )}

      {/* 2. Extra/Bonus Selection */}
      {(mainType === 'bonus' || (isExtra && mainType !== 'movie' && mainType !== 'episode')) && (
        <OverrideExtraFields
          parentId={parentId}
          setParentId={setParentId}
          subcategory={subcategory}
          setSubcategory={setSubcategory}
          language={language}
          setLanguage={setLanguage}
          parentCandidates={parentCandidates}
          category={category}
          subcategoryList={subcategoryList}
          isExtra={isExtra}
          LANGUAGE_OPTIONS={translatedLanguageOptions}
          t={t}
          isScenesMode={hideLanguage}
        />
      )}

      {/* 3. Movie settings */}
      {mainType === 'movie' && (
        <OverrideMovieFields
          targetLanguage={targetLanguage}
          setTargetLanguage={setTargetLanguage}
          source={source}
          setSource={setSource}
          edition={edition}
          setEdition={setEdition}
          audioType={audioType}
          setAudioType={setAudioType}
          LANGUAGE_OPTIONS={translatedLanguageOptions}
          SOURCE_OPTIONS={translatedSourceOptions}
          EDITION_OPTIONS={translatedEditionOptions}
          AUDIO_TYPE_OPTIONS={translatedAudioTypeOptions}
          t={t}
          hideLanguage={hideLanguage}
        />
      )}

      {/* 4. Episode settings */}
      {mainType === 'episode' && (
        <OverrideEpisodeFields
          targetLanguage={targetLanguage}
          setTargetLanguage={setTargetLanguage}
          audioType={audioType}
          setAudioType={setAudioType}
          seasonNum={seasonNum}
          setSeasonNum={setSeasonNum}
          episodeNum={episodeNum}
          setEpisodeNum={setEpisodeNum}
          LANGUAGE_OPTIONS={translatedLanguageOptions}
          AUDIO_TYPE_OPTIONS={translatedAudioTypeOptions}
          t={t}
          hideLanguage={hideLanguage}
        />
      )}
    </>
  );

  return (
    <form id="organizer-override-form" className="organizer-override-modal organizer-override-modal--clip-x" onSubmit={handleSubmit}>
      {showSelector ? (
        <div className="single-override-layout">
          <div className="single-override-layout__side-panel">
            <h4 className="organizer-override-modal__section-title">
              {t('organizer.overrideModal.matchAction.title') || 'Match Action'}
            </h4>
            <p className="organizer-override-field__label-text organizer-override-field__label-text--support organizer-override-field__label-text--spaced">
              {t('organizer.overrideModal.matchAction.description') || 'Choose what to do with the current tv match since season or episode changed:'}
            </p>

            <SelectableCard
              as="div"
              className="match-action-option"
              selected={matchAction === 'keep'}
              onClick={() => setMatchAction('keep')}
            >
              <label className="match-action-option__radio-label">
                <input
                  type="radio"
                  name="matchAction"
                  checked={matchAction === 'keep'}
                  onChange={() => setMatchAction('keep')}
                  className="match-action-option__radio-input"
                />
                {t('organizer.overrideModal.matchAction.keep') || 'Keep current tv match'}
              </label>
              <span className="match-action-option__description">
                {t('organizer.overrideModal.matchAction.keepDesc') || 'Update season/episode under the tv.'}
              </span>
            </SelectableCard>

            <SelectableCard
              as="div"
              className="match-action-option"
              selected={matchAction === 'reset'}
              onClick={() => setMatchAction('reset')}
            >
              <label className="match-action-option__radio-label">
                <input
                  type="radio"
                  name="matchAction"
                  checked={matchAction === 'reset'}
                  onChange={() => setMatchAction('reset')}
                  className="match-action-option__radio-input"
                />
                {t('organizer.overrideModal.matchAction.reset') || 'Reset match (Pending)'}
              </label>
              <span className="match-action-option__description">
                {t('organizer.overrideModal.matchAction.resetDesc') || 'Remove match and return to Review Needed.'}
              </span>
            </SelectableCard>
          </div>
          <div className="single-override-layout__form">
            {renderFormFields()}
          </div>
        </div>
      ) : (
        renderFormFields()
      )}
    </form>
  );
}
