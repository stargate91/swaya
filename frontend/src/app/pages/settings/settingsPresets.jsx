import { Minimize2 } from 'lucide-react';
import {
  EXTRAS_FOLDER_MODES,
  FOLDER_COLLECTION_MODES,
  SETTINGS_PRESET_IDS,
} from './settingsConstants.js';

const ADULT_SUBFOLDER_PRESET = {
  naming_adult_subfolders_enabled: true,
  folder_adult_movies_name: 'Movies',
  folder_adult_tv_name: 'TV Shows',
  folder_adult_scenes_name: 'Scenes',
  folder_adult_jav_name: 'JAV',
};

const ADULT_STANDARD_PRESET = {
  ...ADULT_SUBFOLDER_PRESET,
  naming_scene_template: '{studio} - {date} - {performers} - {title} [{resolution}]',
  naming_scene_date_format: '%Y-%m-%d',
  naming_scene_prevent_title_performer: true,
  scene_tag_limit: '0',
  scene_tag_separator: ' ',
  scene_tag_blacklist: '',
  naming_squeeze_studio_names: false,
  naming_performer_limit: '3',
  naming_performer_limit_keep: true,
  naming_performer_splitchar: ' & ',
  naming_performer_gender_filter: 'all',
  naming_performer_sort: 'popularity',
  scene_grouping_mode: 'parent_studio_studio',
  folder_scene_template: '{date} - {title}',
  naming_jav_template: '{studio} - {date} - {performers} - {title} [{resolution}]',
  jav_grouping_mode: 'parent_studio_studio',
  folder_jav_template: '{date} - {title}',
};

const ADULT_MINIMAL_PRESET = {
  ...ADULT_SUBFOLDER_PRESET,
  naming_scene_template: '{date} - {performers} - {title}',
  naming_scene_date_format: '%Y-%m-%d',
  naming_scene_prevent_title_performer: true,
  scene_tag_limit: '0',
  scene_tag_separator: ' ',
  scene_tag_blacklist: '',
  naming_squeeze_studio_names: false,
  naming_performer_limit: '3',
  naming_performer_limit_keep: true,
  naming_performer_splitchar: ' & ',
  naming_performer_gender_filter: 'all',
  naming_performer_sort: 'popularity',
  scene_grouping_mode: 'none',
  folder_scene_template: '',
  naming_jav_template: '{date} - {performers} - {title}',
  jav_grouping_mode: 'none',
  folder_jav_template: '',
};

export const PRESETS_CONFIG = {
  [SETTINGS_PRESET_IDS.PLEX]: {
    ...ADULT_STANDARD_PRESET,
    naming_filename_casing: 'default',
    naming_word_separator: 'space',
    naming_movie_template: '{title} ({year}) {resolution}',
    naming_episode_template: '{tv_title} - S{season}E{episode} - {episode_title}',
    folder_create_movie_subdir: true,
    folder_movie_template: '{title} ({year})',
    folder_create_show_dir: true,
    folder_tv_template: '{tv_title} ({year_range})',
    folder_create_season_dir: true,
    folder_season_template: 'Season {season}',
    folder_create_episode_dir: false,
    folder_episode_template: '{tv_title} - {season}{episode}',
    folder_create_collection_dir: true,
    folder_collection_mode: FOLDER_COLLECTION_MODES.THRESHOLD,
    extras_folder_mode: EXTRAS_FOLDER_MODES.SUBFOLDER,
    extras_subfolder_name: 'Extras',
  },
  [SETTINGS_PRESET_IDS.JELLYFIN]: {
    ...ADULT_STANDARD_PRESET,
    naming_filename_casing: 'default',
    naming_word_separator: 'space',
    naming_movie_template: '{title} ({year}) {resolution}',
    naming_episode_template: '{tv_title} - S{season}E{episode} - {episode_title}',
    folder_create_movie_subdir: true,
    folder_movie_template: '{title} ({year})',
    folder_create_show_dir: true,
    folder_tv_template: '{tv_title} ({year_range})',
    folder_create_season_dir: true,
    folder_season_template: 'Season {season}',
    folder_create_episode_dir: false,
    folder_episode_template: '{tv_title} - {season}{episode}',
    folder_create_collection_dir: true,
    folder_collection_mode: FOLDER_COLLECTION_MODES.THRESHOLD,
    extras_folder_mode: EXTRAS_FOLDER_MODES.FLAT,
    extras_subfolder_name: 'Extras',
  },
  [SETTINGS_PRESET_IDS.KODI]: {
    ...ADULT_STANDARD_PRESET,
    naming_filename_casing: 'default',
    naming_word_separator: 'dot',
    naming_movie_template: '{title} ({year}) {resolution}',
    naming_episode_template: '{tv_title} - S{season}E{episode} - {episode_title}',
    folder_create_movie_subdir: true,
    folder_movie_template: '{title} ({year})',
    folder_create_show_dir: true,
    folder_tv_template: '{tv_title} ({year_range})',
    folder_create_season_dir: true,
    folder_season_template: 'Season {season}',
    folder_create_episode_dir: false,
    folder_episode_template: '{tv_title} - {season}{episode}',
    folder_create_collection_dir: true,
    folder_collection_mode: FOLDER_COLLECTION_MODES.THRESHOLD,
    extras_folder_mode: EXTRAS_FOLDER_MODES.FLAT,
    extras_subfolder_name: 'Extras',
  },
  [SETTINGS_PRESET_IDS.MINIMAL]: {
    ...ADULT_MINIMAL_PRESET,
    naming_filename_casing: 'default',
    naming_word_separator: 'space',
    naming_movie_template: '{title} ({year})',
    naming_episode_template: '{tv_title} S{season}E{episode}',
    folder_create_movie_subdir: false,
    folder_movie_template: '{title} ({year})',
    folder_create_show_dir: true,
    folder_tv_template: '{tv_title}',
    folder_create_season_dir: false,
    folder_season_template: 'Season {season}',
    folder_create_episode_dir: false,
    folder_episode_template: '{tv_title} - {season}{episode}',
    folder_create_collection_dir: false,
    folder_collection_mode: FOLDER_COLLECTION_MODES.NEVER,
    extras_folder_mode: EXTRAS_FOLDER_MODES.FLAT,
    extras_subfolder_name: 'Extras',
  }
};

export function getPresetCards(t) {
  return [
    {
      value: SETTINGS_PRESET_IDS.PLEX,
      label: t('settingsPage.sections.organization.presets.plex') || 'Plex Standard',
      desc: t('settingsPage.sections.organization.presets.plexDesc') || 'Plex-style naming with Adult/Movies, Adult/TV Shows, and studio-grouped Adult/Scenes.',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="settings-preset-svg-icon">
          <path d="M5.25 2H10.75L18.75 12L10.75 22H5.25L13.25 12L5.25 2Z" fill="var(--settings-preset-plex-color)" />
        </svg>
      )
    },
    {
      value: SETTINGS_PRESET_IDS.JELLYFIN,
      label: t('settingsPage.sections.organization.presets.jellyfin') || 'Jellyfin Standard',
      desc: t('settingsPage.sections.organization.presets.jellyfinDesc') || 'Jellyfin-friendly naming with Adult/Movies, Adult/TV Shows, and studio-grouped Adult/Scenes.',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="settings-preset-svg-icon">
          <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 4C14.76 4 17.14 5.37 18.57 7.43L12 11.5L5.43 7.43C6.86 5.37 9.24 4 12 4ZM5.07 9.47L11 13.18V20C7.38 19.54 4.54 16.7 4.08 13.08C3.93 11.83 4.29 10.57 5.07 9.47ZM13 20V13.18L18.93 9.47C19.71 10.57 20.07 11.83 19.92 13.08C19.46 16.7 16.62 19.54 13 20Z" fill="url(#jellyfin-gradient)" />
          <defs>
            <linearGradient id="jellyfin-gradient" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
              <stop stopColor="var(--settings-preset-jellyfin-start)" />
              <stop offset="1" stopColor="var(--settings-preset-jellyfin-end)" />
            </linearGradient>
          </defs>
        </svg>
      )
    },
    {
      value: SETTINGS_PRESET_IDS.KODI,
      label: t('settingsPage.sections.organization.presets.kodi') || 'Kodi Standard',
      desc: t('settingsPage.sections.organization.presets.kodiDesc') || 'Kodi-friendly dot naming with Adult/Movies, Adult/TV Shows, and studio-grouped Adult/Scenes.',
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="settings-preset-svg-icon">
          <path d="M12 2L2 12L12 22L22 12L12 2Z" fill="var(--settings-preset-kodi-primary)" />
          <path d="M12 6L6 12L12 18L18 12L12 6Z" fill="var(--settings-preset-kodi-secondary)" />
          <rect x="11.25" y="11.25" width="1.5" height="1.5" fill="var(--settings-preset-kodi-accent)" />
        </svg>
      )
    },
    {
      value: SETTINGS_PRESET_IDS.MINIMAL,
      label: t('settingsPage.sections.organization.presets.minimal') || 'Minimalist Layout',
      desc: t('settingsPage.sections.organization.presets.minimalDesc') || 'A shallow layout that still separates Adult/Movies, Adult/TV Shows, and Adult/Scenes.',
      icon: <Minimize2 size={20} color="var(--settings-preset-minimal-color)" className="settings-preset-svg-icon" />
    }
  ];
}
