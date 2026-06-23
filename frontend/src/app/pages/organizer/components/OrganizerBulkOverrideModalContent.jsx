import { useState, useMemo, useEffect } from 'react';
import { ArrowUp, ArrowDown, GripVertical } from 'lucide-react';
import Dropdown from '../../../ui/Dropdown';
import Input from '../../../ui/Input';
import SelectableCard from '../../../ui/SelectableCard';
import { useTranslation } from '../../../providers/LanguageContext';
import { useQueryClient } from '@tanstack/react-query';
import { useBulkUpdateMediaMutation } from '../../../queries';

const DOT = '.';

import { useLibraryModeStore } from '@/stores/useLibraryModeStore';

import {
  SUBCATEGORIES_BY_CATEGORY,
  LANGUAGE_OPTIONS,
  SOURCE_OPTIONS,
  EDITION_OPTIONS,
  AUDIO_TYPE_OPTIONS,
  MAIN_TYPE_OPTIONS,
} from './overrideConstants';

export default function OrganizerBulkOverrideModalContent({ rows, onClose, toast }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const sessionMode = useLibraryModeStore((state) => state.sessionMode);

  const isExtra = rows[0]?.rawType === 'extra';
  const category = isExtra ? (rows[0]?.rawPayload?.category || 'video') : 'video';
  const initialMainType = isExtra
    ? (category === 'video' ? 'bonus' : 'extra')
    : rows[0]?.rawType;

  const [mainType, setMainType] = useState(initialMainType);
  const [applyMainType, setApplyMainType] = useState(false);

  // Options Translations
  const translatedLanguageOptions = useMemo(() =>
    LANGUAGE_OPTIONS.map((opt) => {
      const key = `languages.${opt.value}`;
      const val = t(key);
      return {
        ...opt,
        label: val === key ? opt.label : val,
      };
    }),
    [t]
  );

  const translatedSubcategoriesByCategory = useMemo(() => {
    const result = {};
    Object.keys(SUBCATEGORIES_BY_CATEGORY).forEach((catKey) => {
      result[catKey] = SUBCATEGORIES_BY_CATEGORY[catKey].map((opt) => {
        const key = `organizer.overrideModal.options.subcategories.${opt.value}`;
        const val = t(key);
        return {
          ...opt,
          label: val === key ? opt.label : val,
        };
      });
    });
    return result;
  }, [t]);

  const translatedSourceOptions = useMemo(() =>
    SOURCE_OPTIONS.map((opt) => {
      const key = `organizer.overrideModal.options.sources.${opt.value}`;
      const val = t(key);
      return {
        ...opt,
        label: val === key ? opt.label : val,
      };
    }),
    [t]
  );

  const translatedEditionOptions = useMemo(() =>
    EDITION_OPTIONS.map((opt) => {
      const key = `organizer.overrideModal.options.editions.${opt.value}`;
      const val = t(key);
      return {
        ...opt,
        label: val === key ? opt.label : val,
      };
    }),
    [t]
  );

  const translatedAudioTypeOptions = useMemo(() =>
    AUDIO_TYPE_OPTIONS.map((opt) => {
      const key = `organizer.overrideModal.options.audioTypes.${opt.value}`;
      const val = t(key);
      return {
        ...opt,
        label: val === key ? opt.label : val,
      };
    }),
    [t]
  );

  const isScenesMode = useMemo(() =>
    rows.some((r) => r.rawPayload?.scan_mode === 'scenes' || r.rawPayload?.parent_scan_mode === 'scenes'),
    [rows]
  );

  const hideLanguage = useMemo(() => {
    const hasAdultMatch = rows.some((r) => {
      const activeMatch = r.rawPayload?.matches?.find((m) => m.is_active) || r.rawPayload?.matches?.[0];
      return activeMatch && ['porndb', 'stashdb', 'fansdb'].includes(activeMatch.provider);
    });
    return isScenesMode || hasAdultMatch;
  }, [rows, isScenesMode]);

  const translatedMainTypeOptions = useMemo(() => {
    if (isScenesMode) {
      return [
        { value: 'scene', label: t('organizer.overrideModal.options.mainTypes.scene') || 'Scene' },
        { value: 'bonus', label: t('organizer.overrideModal.options.mainTypes.bonus') || 'Bonus Video' },
      ];
    }
    return MAIN_TYPE_OPTIONS.map((opt) => {
      const key = `organizer.overrideModal.options.mainTypes.${opt.value}`;
      const val = t(key);
      return {
        ...opt,
        label: val === key ? opt.label : val,
      };
    });
  }, [t, isScenesMode]);

  const subcategoryList = translatedSubcategoriesByCategory[mainType === 'bonus' ? 'video' : category] || [];

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

  const firstRow = rows[0] || {};
  const isExtraAdult = sessionMode === 'nsfw';

  const isExtraScene = isExtra
    ? (firstRow.parentType === 'scene' || (firstRow.rawPayload?.parent_scan_mode === 'scenes'))
    : (String(firstRow.type || firstRow.rawType).toLowerCase() === 'scene' || firstRow.scan_mode === 'scenes' || firstRow.rawPayload?.scan_mode === 'scenes');

  const filteredMoviesAndTv = [...movies, ...tv].filter((item) => {
    // 0. Cannot select any of the edited items as parent
    if (rows.some((r) => r.itemId === item.id)) return false;

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

  // State for properties to apply
  const [applyTargetLanguage, setApplyTargetLanguage] = useState(false);
  const [targetLanguage, setTargetLanguage] = useState('en');

  const [applySource, setApplySource] = useState(false);
  const [source, setSource] = useState('none');

  const [applyEdition, setApplyEdition] = useState(false);
  const [edition, setEdition] = useState('none');

  const [applyAudioType, setApplyAudioType] = useState(false);
  const [audioType, setAudioType] = useState('none');

  const [applySeasonNum, setApplySeasonNum] = useState(false);
  const [seasonNum, setSeasonNum] = useState('');

  const [applyParentId, setApplyParentId] = useState(false);
  const [parentId, setParentId] = useState(parentCandidates[0]?.value || '');

  const [applySubcategory, setApplySubcategory] = useState(false);
  const [subcategory, setSubcategory] = useState('other');

  const [applyLanguage, setApplyLanguage] = useState(false);
  const [language, setLanguage] = useState('en');

  // Auto-numbering and ordering states (for episodes)
  const [orderedItems, setOrderedItems] = useState(() => [...rows]);
  const [applyAutoNumbering, setApplyAutoNumbering] = useState(false);
  const [startEpisodeNum, setStartEpisodeNum] = useState('1');
  const [matchAction, setMatchAction] = useState('keep');

  const hasMatched = useMemo(() => rows.some((row) => row.rawStatus === 'matched'), [rows]);
  const isEpisode = mainType === 'episode';
  const isModifyingSeasonOrEpisode = applySeasonNum || applyAutoNumbering;
  const showMatchActionSelector = hasMatched && initialMainType === 'episode' && isEpisode && isModifyingSeasonOrEpisode;

  const bulkUpdateMutation = useBulkUpdateMediaMutation();

  useEffect(() => {
    const modalElement = document.querySelector('.ui-modal');
    if (modalElement) {
      if (mainType === 'episode' && applyAutoNumbering) {
        modalElement.classList.add('has-side-panel');
      } else {
        modalElement.classList.remove('has-side-panel');
      }
    }
  }, [mainType, applyAutoNumbering]);

  // HTML5 Drag and Drop handlers
  const [draggedIndex, setDraggedIndex] = useState(null);

  const handleDragStart = (e, index) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;
    const newList = [...orderedItems];
    const draggedItem = newList[draggedIndex];
    newList.splice(draggedIndex, 1);
    newList.splice(index, 0, draggedItem);
    setDraggedIndex(index);
    setOrderedItems(newList);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleMoveUp = (index) => {
    if (index === 0) return;
    const newList = [...orderedItems];
    const item = newList[index];
    newList.splice(index, 1);
    newList.splice(index - 1, 0, item);
    setOrderedItems(newList);
  };

  const handleMoveDown = (index) => {
    if (index === orderedItems.length - 1) return;
    const newList = [...orderedItems];
    const item = newList[index];
    newList.splice(index, 1);
    newList.splice(index + 1, 0, item);
    setOrderedItems(newList);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (initialMainType !== 'episode' && mainType === 'episode') {
      if (!applySeasonNum || !String(seasonNum ?? '').trim()) {
        toast(t('organizer.toasts.bulkOverrideSeasonRequired'), 'danger');
        return;
      }
      if (!applyAutoNumbering || !String(startEpisodeNum ?? '').trim()) {
        toast(t('organizer.toasts.bulkOverrideAutoNumberRequired'), 'danger');
        return;
      }
    }

    if (applyParentId && (mainType === 'bonus' || mainType === 'extra') && rows.some((r) => String(r.itemId) === String(parentId))) {
      toast(t('organizer.toasts.selfParentError') || 'An item cannot be its own parent.', 'danger');
      return;
    }

    const payload = {
      ids: rows.map((r) => r.itemId),
      type: isExtra ? 'extra' : 'media',
    };

    if (showMatchActionSelector && matchAction === 'reset') {
      payload.reset_match = true;
    }

    if (applyMainType) {
      payload.main_type = mainType;
    }

    if (mainType === 'bonus' || mainType === 'extra') {
      if (applyParentId) payload.parent_id = parentId;
      if (category !== 'metadata') {
        if (applySubcategory) payload.subtype = subcategory;
      }
      if (mainType === 'extra') {
        if (category === 'subtitle' || category === 'audio') {
          if (applyLanguage) payload.language = language;
        }
      }
    } else {
      // movie or episode
      if (applyTargetLanguage) payload.custom_language = targetLanguage;
      if (applyAudioType) payload.custom_audio_type = audioType;
      if (mainType === 'movie') {
        if (applySource) payload.custom_source = source;
        if (applyEdition) payload.custom_edition = edition;
      } else if (mainType === 'episode') {
        if (applySeasonNum) payload.season = seasonNum;
      }
    }

    // Prepare item-specific updates (e.g. calculated episode numbers)
    const itemUpdates = [];
    if (mainType === 'episode' && applyAutoNumbering) {
      const startNum = parseInt(startEpisodeNum, 10);
      if (Number.isNaN(startNum)) {
        toast(t('organizer.toasts.bulkOverrideStartEpisodeInvalid'), 'danger');
        return;
      }
      orderedItems.forEach((item, index) => {
        itemUpdates.push({
          id: item.itemId,
          updates: {
            episode: String(startNum + index),
          },
        });
      });
    }

    if (itemUpdates.length > 0) {
      payload.item_updates = itemUpdates;
    }

    bulkUpdateMutation.mutate(payload, {
      onSuccess: () => {
        toast(t('organizer.toasts.bulkOverrideSuccess'), 'success');
      },
      onError: (err) => {
        toast(err.message || t('organizer.toasts.bulkOverrideSaveFailed'), 'danger');
      },
    });
    onClose();
  };

  const renderFieldWithCheckbox = (label, checked, setChecked, content) => (
    <div className="organizer-override-field">
      <label className="organizer-override-field__checkbox-label">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => setChecked(e.target.checked)}
          className="ui-checkbox"
        />
        <span className="organizer-override-field__label-text">{label}</span>
      </label>
      <div className={`organizer-override-field__input ${!checked ? 'is-disabled' : ''}`}>
        {content}
      </div>
    </div>
  );

  const isSidebarActive = mainType === 'episode' && applyAutoNumbering;

  return (
    <form id="organizer-bulk-override-form" className={`organizer-override-modal ${isSidebarActive ? 'bulk-override-layout' : ''}`} onSubmit={handleSubmit}>
      <div className={isSidebarActive ? 'bulk-override-layout__form' : ''}>
        {/* Main Category override (only for movie, episode, bonus) */}
        {(initialMainType === 'movie' || initialMainType === 'episode' || initialMainType === 'bonus') && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.mainCategory'),
          applyMainType,
          setApplyMainType,
          <Dropdown
            value={mainType}
            onChange={(e) => setMainType(e.target.value)}
            options={translatedMainTypeOptions}
            disabled={!applyMainType}
          />
        )}

        {/* Target Language override (for Movies & Episodes) */}
        {!hideLanguage && mainType !== 'extra' && mainType !== 'bonus' && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.targetLanguage'),
          applyTargetLanguage,
          setApplyTargetLanguage,
          <Dropdown
            value={targetLanguage}
            onChange={(e) => setTargetLanguage(e.target.value)}
            options={translatedLanguageOptions}
            disabled={!applyTargetLanguage}
          />
        )}

        {/* Source override (for Movies) */}
        {mainType === 'movie' && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.source'),
          applySource,
          setApplySource,
          <Dropdown
            value={source}
            onChange={(e) => setSource(e.target.value)}
            options={translatedSourceOptions}
            disabled={!applySource}
          />
        )}

        {/* Edition override (for Movies) */}
        {mainType === 'movie' && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.edition'),
          applyEdition,
          setApplyEdition,
          <Dropdown
            value={edition}
            onChange={(e) => setEdition(e.target.value)}
            options={translatedEditionOptions}
            disabled={!applyEdition}
          />
        )}

        {/* Audio Type override (for Movies & Episodes) */}
        {mainType !== 'extra' && mainType !== 'bonus' && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.audioType'),
          applyAudioType,
          setApplyAudioType,
          <Dropdown
            value={audioType}
            onChange={(e) => setAudioType(e.target.value)}
            options={translatedAudioTypeOptions}
            disabled={!applyAudioType}
          />
        )}

        {/* Season Number override (for Episodes) */}
        {mainType === 'episode' && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.seasonNumber'),
          applySeasonNum,
          setApplySeasonNum,
          <Input
            type="text"
            value={seasonNum}
            onChange={(e) => setSeasonNum(e.target.value)}
            placeholder={t('organizer.overrideModal.placeholders.seasonNumber')}
            disabled={!applySeasonNum}
          />
        )}

        {/* Subcategory override (for Extras & Bonus videos) */}
        {(mainType === 'extra' || mainType === 'bonus') && category !== 'metadata' && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.extraSubcategory'),
          applySubcategory,
          setApplySubcategory,
          <Dropdown
            value={subcategory}
            onChange={(e) => setSubcategory(e.target.value)}
            options={subcategoryList}
            disabled={!applySubcategory}
          />
        )}

        {/* Parent ID override (for Extras & Bonus videos) */}
        {(mainType === 'bonus' || mainType === 'extra') && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.parentMovieOrEpisode'),
          applyParentId,
          setApplyParentId,
          <Dropdown
            value={parentId}
            onChange={(e) => setParentId(e.target.value)}
            options={parentCandidates}
            disabled={!applyParentId}
            searchable={true}
          />
        )}

        {/* Language override (for Subtitle & Audio extras) */}
        {mainType === 'extra' && (category === 'subtitle' || category === 'audio') && renderFieldWithCheckbox(
          t('organizer.overrideModal.labels.language'),
          applyLanguage,
          setApplyLanguage,
          <Dropdown
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            options={translatedLanguageOptions}
            disabled={!applyLanguage}
          />
        )}

        {/* Auto-numbering and sorting panel checkbox (Only for Episodes) */}
        {mainType === 'episode' && (
          <div className={`organizer-override-bulk-episodes${isSidebarActive ? ' organizer-override-bulk-episodes--sidebar-active' : ''}`}>
            <label className="organizer-override-field__checkbox-label organizer-override-bulk-episodes__header-check">
              <input
                type="checkbox"
                checked={applyAutoNumbering}
                onChange={(e) => setApplyAutoNumbering(e.target.checked)}
                className="ui-checkbox"
              />
              <span className="organizer-override-field__label-text font-semibold">{t('organizer.overrideModal.labels.autoNumberCheck')}</span>
            </label>
          </div>
        )}

        {showMatchActionSelector && (
          <div className="organizer-override-modal__section organizer-override-modal__section--match-actions">
            <h4 className="organizer-override-modal__section-title organizer-override-modal__section-title--compact">
              {t('organizer.overrideModal.matchAction.title') || 'Match Action'}
            </h4>
            <p className="organizer-override-field__label-text organizer-override-field__label-text--support">
              {t('organizer.overrideModal.matchAction.description') || 'Choose what to do with the current tv match since season or episode changed:'}
            </p>

            <div className="organizer-match-action-grid">
              <SelectableCard
                as="div"
                className="match-action-option"
                selected={matchAction === 'keep'}
                onClick={() => setMatchAction('keep')}
              >
                <label className="match-action-option__radio-label">
                  <input
                    type="radio"
                    name="bulkMatchAction"
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
                    name="bulkMatchAction"
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
          </div>
        )}
      </div>

      {isSidebarActive && (
        <div className="bulk-override-layout__side-panel">
          <div className="organizer-override-bulk-episodes__panel organizer-override-bulk-episodes__panel--sidebar">
            <div className="organizer-override-field">
              <span className="organizer-override-field__label-text">{t('organizer.overrideModal.labels.startNumbering')}</span>
              <Input
                type="number"
                min="1"
                value={startEpisodeNum}
                onChange={(e) => setStartEpisodeNum(e.target.value)}
                className="w-24"
              />
            </div>

            <span className="organizer-override-bulk-episodes__hint">
              {t('organizer.overrideModal.labels.dragAndDropHint')}
            </span>

            <div className="organizer-override-bulk-episodes__list organizer-override-bulk-episodes__list--sidebar">
              {orderedItems.map((item, index) => {
                return (
                  // eslint-disable-next-line jsx-a11y/no-static-element-interactions
                  <div
                    key={item.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, index)}
                    onDragOver={(e) => handleDragOver(e, index)}
                    onDragEnd={handleDragEnd}
                    className={`organizer-override-bulk-episodes__item ${draggedIndex === index ? 'is-dragging' : ''}`}
                  >
                    <div className="organizer-override-bulk-episodes__item-left">
                      <GripVertical className="organizer-override-bulk-episodes__grip" size={14} />
                      <span className="organizer-override-bulk-episodes__index">{index + parseInt(startEpisodeNum, 10) || (index + 1)}{DOT}</span>
                      <span className="organizer-override-bulk-episodes__filename" title={item.source}>
                        {item.source}
                      </span>
                    </div>
                    <div className="organizer-override-bulk-episodes__item-actions">
                      <IconButton
                        type="button"
                        onClick={() => handleMoveUp(index)}
                        disabled={index === 0}
                      >
                        <ArrowUp size={12} />
                      </IconButton>
                      <IconButton
                        type="button"
                        onClick={() => handleMoveDown(index)}
                        disabled={index === orderedItems.length - 1}
                      >
                        <ArrowDown size={12} />
                      </IconButton>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </form>
  );
}

function IconButton({ children, disabled, onClick, type = 'button' }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`ui-icon-button organizer-override-icon-button${disabled ? ' is-disabled' : ''}`.trim()}
    >
      {children}
    </button>
  );
}
