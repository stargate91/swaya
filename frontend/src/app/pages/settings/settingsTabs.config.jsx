import { Settings2, FolderTree, KeyRound, Wrench, Palette, Cpu, Flame } from 'lucide-react';
import { ORGANIZATION_TAB_IDS, SETTINGS_TAB_GROUP_IDS, SETTINGS_TAB_IDS } from './settingsConstants.js';

import {
  GeneralTab,
  ThemeTab,
  AdultTab,
  PresetsTab,
  FileNamingTab,
  FolderStructureTab,
  CollisionRulesTab,
  CollectionsTab,
  ExtrasTab,
  ApiKeysTab,
  AdvancedTab,
  MaintenanceTab,
  ScenesTab,
} from './components';

const alwaysVisible = () => true;
const whenCustomOrganization = ({ form }) => form.custom_organization_enabled;
const whenAdultScenes = ({ form }) => form.custom_organization_enabled && form.include_adult;
const whenMoveToLibraryAndCustomOrganization = ({ form }) => form.folder_move_to_library && form.custom_organization_enabled;
const whenCollectionsEnabled = ({ form }) => form.folder_move_to_library && form.folder_organization_enabled;

export const settingsTabGroups = [
  {
    id: SETTINGS_TAB_GROUP_IDS.GENERAL,
    labelKey: 'settingsPage.sidebar.general',
    icon: Settings2,
  },
  {
    id: SETTINGS_TAB_GROUP_IDS.THEME,
    labelKey: 'settingsPage.sidebar.theme',
    icon: Palette,
  },
  {
    id: SETTINGS_TAB_GROUP_IDS.ADULT,
    labelKey: 'settingsPage.sidebar.adult',
    icon: Flame,
  },
  {
    id: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.organization',
    icon: FolderTree,
    children: ORGANIZATION_TAB_IDS,
  },
  {
    id: SETTINGS_TAB_GROUP_IDS.API_KEYS,
    labelKey: 'settingsPage.sidebar.apiKeys',
    icon: KeyRound,
  },
  {
    id: SETTINGS_TAB_GROUP_IDS.ADVANCED,
    labelKey: 'settingsPage.sidebar.advanced',
    icon: Cpu,
  },
  {
    id: SETTINGS_TAB_GROUP_IDS.MAINTENANCE,
    labelKey: 'settingsPage.sidebar.maintenance',
    icon: Wrench,
  },
];

export const settingsTabDefinitions = [
  {
    id: SETTINGS_TAB_IDS.GENERAL,
    group: SETTINGS_TAB_GROUP_IDS.GENERAL,
    component: GeneralTab,
  },
  {
    id: SETTINGS_TAB_IDS.THEME,
    group: SETTINGS_TAB_GROUP_IDS.THEME,
    component: ThemeTab,
  },
  {
    id: SETTINGS_TAB_IDS.ADULT,
    group: SETTINGS_TAB_GROUP_IDS.ADULT,
    component: AdultTab,
    getProps: (ctx) => ({
      form: ctx.form,
      setForm: ctx.setForm,
    }),
  },
  {
    id: SETTINGS_TAB_IDS.PRESETS,
    group: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.presets',
    component: PresetsTab,
    isVisible: alwaysVisible,
  },
  {
    id: SETTINGS_TAB_IDS.FILE_NAMING,
    group: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.fileNaming',
    component: FileNamingTab,
    isVisible: whenCustomOrganization,
    className: 'custom-only',
    getProps: (ctx) => ({
      form: ctx.form,
      t: ctx.t,
      handleChange: ctx.handleChange,
      insertTag: ctx.insertTag,
      casingOptions: ctx.casingOptions,
      separatorOptions: ctx.separatorOptions,
      formInputs: ctx.formInputs,
    }),
  },
  {
    id: SETTINGS_TAB_IDS.FOLDER_STRUCTURE,
    group: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.folderStructure',
    component: FolderStructureTab,
    isVisible: whenMoveToLibraryAndCustomOrganization,
    className: 'custom-only',
    getProps: (ctx) => ({
      form: ctx.form,
      t: ctx.t,
      handleChange: ctx.handleChange,
      handleCheckboxChange: ctx.handleCheckboxChange,
      insertTag: ctx.insertTag,
      formInputs: ctx.formInputs,
    }),
  },
  {
    id: SETTINGS_TAB_IDS.EXTRAS,
    group: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.extras',
    component: ExtrasTab,
    isVisible: whenCustomOrganization,
    className: 'custom-only',
  },
  {
    id: SETTINGS_TAB_IDS.SCENES,
    group: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.scenes',
    component: ScenesTab,
    isVisible: whenAdultScenes,
    className: 'custom-only',
    getProps: (ctx) => ({
      form: ctx.form,
      t: ctx.t,
      handleChange: ctx.handleChange,
      handleCheckboxChange: ctx.handleCheckboxChange,
      insertTag: ctx.insertTag,
      formInputs: ctx.formInputs,
    }),
  },

  {
    id: SETTINGS_TAB_IDS.RULES,
    group: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.rules',
    component: CollisionRulesTab,
    isVisible: alwaysVisible,
  },
  {
    id: SETTINGS_TAB_IDS.COLLECTIONS,
    group: SETTINGS_TAB_GROUP_IDS.ORGANIZATION,
    labelKey: 'settingsPage.sidebar.collections',
    component: CollectionsTab,
    isVisible: whenCollectionsEnabled,
    className: 'custom-only',
    getProps: (ctx) => ({
      form: ctx.form,
      setForm: ctx.setForm,
      t: ctx.t,
      handleChange: ctx.handleChange,
      insertTag: ctx.insertTag,
      collectionModeOptions: ctx.collectionModeOptions,
      formInputs: ctx.formInputs,
    }),
  },
  {
    id: SETTINGS_TAB_IDS.API_KEYS,
    group: SETTINGS_TAB_GROUP_IDS.API_KEYS,
    component: ApiKeysTab,
  },
  {
    id: SETTINGS_TAB_IDS.ADVANCED,
    group: SETTINGS_TAB_GROUP_IDS.ADVANCED,
    component: AdvancedTab,
  },
  {
    id: SETTINGS_TAB_IDS.MAINTENANCE,
    group: SETTINGS_TAB_GROUP_IDS.MAINTENANCE,
    component: MaintenanceTab,
    getProps: (ctx) => ({
      t: ctx.t,
      isSaving: ctx.isSaving,
      isWiping: ctx.isWiping,
      isScanActive: ctx.realBackgroundActive,
      handleExportSettings: ctx.handleExportSettings,
      handleImportClick: ctx.handleImportClick,
      handleImportSettings: ctx.handleImportSettings,
      handleWipeDatabase: ctx.handleWipeDatabase,
      formInputs: ctx.formInputs,
    }),
  },
];

export function getVisibleOrganizationTabs(ctx) {
  return settingsTabDefinitions
    .filter((tab) => tab.group === SETTINGS_TAB_GROUP_IDS.ORGANIZATION)
    .map((tab) => ({
      ...tab,
      isCurrentlyVisible: tab.isVisible ? tab.isVisible(ctx) : true,
    }));
}

export function getTabDefinition(tabId) {
  return settingsTabDefinitions.find((tab) => tab.id === tabId) || null;
}


