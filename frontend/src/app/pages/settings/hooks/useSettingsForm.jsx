/* eslint-disable react-hooks/refs */
import { useRef } from 'react';
import { useUi } from '@/providers/UiProvider';
import { useTranslation } from '@/providers/LanguageContext';
import { useScanStatusQuery, useImageStatusQuery, useHydrateStatusQuery } from '@/queries';
import useSettingsNavigation from './useSettingsNavigation.jsx';
import useTemplateTagInsertion from './useTemplateTagInsertion.jsx';
import useFolderValidation from './useFolderValidation.jsx';
import useSettingsBackup from './useSettingsBackup.jsx';
import useSettingsPersistence from './useSettingsPersistence.jsx';
import useSettingsPickers from './useSettingsPickers.jsx';
import useSettingsDangerZone from './useSettingsDangerZone.jsx';
import { SETTINGS_TAB_IDS } from '../settingsConstants.js';

export default function useSettingsForm() {
  const { t } = useTranslation();
  const { toast, openModal, closeModal } = useUi();
  const scanStatusQuery = useScanStatusQuery();
  const imageStatusQuery = useImageStatusQuery();
  const hydrateStatusQuery = useHydrateStatusQuery();

  const isSyncActive = Boolean(scanStatusQuery.data?.active && scanStatusQuery.data?.phase === 'sync_language');
  const isScanActive = Boolean(scanStatusQuery.data?.active) && scanStatusQuery.data?.phase !== 'sync_language';
  const isBackgroundActive = Boolean(
    isScanActive ||
    isSyncActive ||
    imageStatusQuery.data?.active ||
    hydrateStatusQuery.data?.active
  );

  const formInputs = {
    scanFolder: useRef(null),
    targetFolder: useRef(null),
    namingMovie: useRef(null),
    namingEpisode: useRef(null),
    namingScene: useRef(null),
    folderScene: useRef(null),
    folderMovie: useRef(null),
    folderTv: useRef(null),
    folderSeason: useRef(null),
    folderEpisode: useRef(null),
    extrasVideo: useRef(null),
    extrasSub: useRef(null),
    extrasAudio: useRef(null),
    extrasImage: useRef(null),
    extrasMeta: useRef(null),
    folderCollection: useRef(null),
    backupFile: useRef(null),
  };

  const {
    validationErrors,
    clearFolderValidation,
    validateFormFolders,
  } = useFolderValidation({
    t,
    onInvalid: ({ firstField }) => {
      navigation.setActiveTab(SETTINGS_TAB_IDS.GENERAL);
      if (!firstField) {
        return;
      }
      setTimeout(() => {
        formInputs[firstField]?.current?.focus();
      }, 0);
    },
  });
  const persistence = useSettingsPersistence({
    t,
    toast,
    openModal,
    closeModal,
    validateFormFolders,
    onValidationInvalid: () => navigation.setActiveTab(SETTINGS_TAB_IDS.GENERAL),
  });
  const navigation = useSettingsNavigation(persistence.form, persistence.isDirty);
  const insertTag = useTemplateTagInsertion(persistence.form, persistence.setForm);
  const pickers = useSettingsPickers({
    form: persistence.form,
    setForm: persistence.setForm,
    clearFolderValidation,
  });
  const {
    handleExportSettings,
    handleImportClick,
    handleImportSettings,
  } = useSettingsBackup({
    form: persistence.form,
    setForm: persistence.setForm,
    fileInputRef: formInputs.backupFile,
    toast,
    t,
  });
  const dangerZone = useSettingsDangerZone({
    t,
    toast,
    openModal,
    closeModal,
    onBeforeWipe: persistence.resetInitialization,
  });

  return {
    t,
    settingsQuery: persistence.settingsQuery,
    settings: persistence.settings,
    form: persistence.form,
    setForm: persistence.setForm,
    activeTab: navigation.activeTab,
    setActiveTab: navigation.setActiveTab,
    isOrgExpanded: navigation.isOrgExpanded,
    setIsOrgExpanded: navigation.setIsOrgExpanded,
    isOrganizationTabActive: navigation.isOrganizationTabActive,
    isSaving: persistence.isSaving,
    isWiping: dangerZone.isWiping,
    isScanActive,
    isBackgroundActive,
    isSyncActive,
    validationErrors,
    isDirty: persistence.isDirty,
    formInputs,
    insertTag,
    handleClose: navigation.handleClose,
    handleChange: pickers.handleChange,
    handleCheckboxChange: pickers.handleCheckboxChange,
    handlePickFolder: pickers.handlePickFolder,
    handlePickFile: pickers.handlePickFile,
    handleExportSettings,
    handleImportClick,
    handleImportSettings,
    handleSave: persistence.handleSave,
    handleWipeDatabase: dangerZone.handleWipeDatabase,
    handleReset: persistence.handleReset,
    isShaking: navigation.isShaking,
    openModal,
    closeModal,
  };
}
