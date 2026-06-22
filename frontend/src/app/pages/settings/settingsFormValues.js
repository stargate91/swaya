import {
  EXTRAS_FOLDER_MODES,
  FOLDER_COLLECTION_MODES,
  SETTINGS_PRESET_IDS,
} from './settingsConstants.js';

export const SETTINGS_BASE_DEFAULTS = {
  user_name: '',
  avatar_path: '',
  default_scan_dir: '',
  folder_library_path: '',
  collision_strategy: 'keep_both',
  collision_duration_tolerance_seconds: '10',
  extras_video_action: 'rename',
  extras_sub_action: 'rename',
  extras_audio_action: 'rename',
  extras_img_action: 'rename',
  extras_meta_action: 'rename',
  vlc_path: '',
  mpc_path: '',
  tmdb_api_key: '',
  tmdb_bearer_token: '',
  omdb_api_key: '',
  ui_language: 'en',
  follow_app_language_for_media_library: true,
  follow_app_language_for_naming: true,
  primary_metadata_language: 'en-US',
  fallback_metadata_language: 'en-US',
  default_target_language: 'en',
  close_button_behavior: 'ask',
  include_adult: false,
  adult_gender_preference: 'all',
  stashdb_api_key: '',
  fansdb_api_key: '',
  porndb_api_key: '',
  stashdb_endpoint: 'https://stashdb.org/graphql',
  fansdb_endpoint: 'https://fansdb.cc/graphql',
  porndb_endpoint: 'https://theporndb.net/graphql',
  custom_organization_enabled: false,
  organization_preset: SETTINGS_PRESET_IDS.PLEX,
  ui_theme: 'dark',
  min_video_size_mb: '50',
  min_video_duration_minutes: '12',
  adult_min_video_size_mb: '1',
  adult_min_video_duration_minutes: '0.1',
  folder_create_collection_dir: true,
  folder_collection_mode: FOLDER_COLLECTION_MODES.THRESHOLD,
  folder_collection_threshold: '3',
  naming_filename_casing: 'default',
  naming_word_separator: 'space',
  naming_movie_template: '{title} ({year}) {resolution}',
  naming_episode_template: '{tv_title} - S{season}E{episode} - {episode_title}',
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
  naming_custom_tag: 'default',
  naming_video_exts: '.mkv, .mp4, .avi, .m4v, .mov, .wmv, .mpg, .mpeg',
  folder_organization_enabled: true,
  folder_move_to_library: true,
  folder_sort_by_type: true,
  folder_movies_name: 'Movies',
  folder_tv_name: 'TV Shows',
  folder_adult_name: 'Adult',
  naming_adult_subfolders_enabled: true,
  folder_adult_movies_name: 'Movies',
  folder_adult_tv_name: 'TV Shows',
  folder_adult_scenes_name: 'Scenes',
  folder_create_movie_subdir: true,
  folder_movie_template: '{title} ({year})',
  folder_create_show_dir: true,
  folder_tv_template: '{tv_title} ({year_range})',
  folder_create_season_dir: true,
  folder_season_template: 'Season {season}',
  folder_create_episode_dir: false,
  folder_episode_template: '{tv_title} - {season}{episode}',
  folder_remove_empty: true,
  folder_collection_template: '{collection}',
  extras_enabled: true,
  extras_sub_exts: '.srt, .sub, .ass, .ssa, .vtt',
  extras_audio_exts: '.mka, .ac3, .dts, .mp3, .flac, .wav, .m4a',
  extras_img_exts: '.jpg, .jpeg, .png, .gif, .bmp, .webp',
  extras_meta_exts: '.nfo, .xml, .txt',
  extras_video_template: '{parent_name}-{sub_category}',
  extras_sub_template: '{parent_name}.{language}',
  extras_audio_template: '{parent_name}.{language}',
  extras_img_template: '{sub_category}',
  extras_meta_template: '{parent_name}',
  extras_folder_mode: EXTRAS_FOLDER_MODES.SUBFOLDER,
  extras_subfolder_name: 'Extras',
};

export function getLocalizedSettingsDefaults(t = null) {
  if (!t) {
    return {
      folder_movies_name: SETTINGS_BASE_DEFAULTS.folder_movies_name,
      folder_tv_name: SETTINGS_BASE_DEFAULTS.folder_tv_name,
      folder_adult_name: SETTINGS_BASE_DEFAULTS.folder_adult_name,
      folder_adult_movies_name: SETTINGS_BASE_DEFAULTS.folder_adult_movies_name,
      folder_adult_tv_name: SETTINGS_BASE_DEFAULTS.folder_adult_tv_name,
      folder_adult_scenes_name: SETTINGS_BASE_DEFAULTS.folder_adult_scenes_name,
      extras_subfolder_name: SETTINGS_BASE_DEFAULTS.extras_subfolder_name,
    };
  }

  return {
    folder_movies_name: t('settingsPage.sections.folderStructure.defaultMoviesName'),
    folder_tv_name: t('settingsPage.sections.folderStructure.defaultTvName'),
    folder_adult_name: t('settingsPage.sections.folderStructure.defaultAdultName'),
    folder_adult_movies_name: t('settingsPage.sections.folderStructure.defaultAdultMoviesName'),
    folder_adult_tv_name: t('settingsPage.sections.folderStructure.defaultAdultTvName'),
    folder_adult_scenes_name: t('settingsPage.sections.folderStructure.defaultAdultScenesName'),
    extras_subfolder_name: t('settingsPage.sections.extras.defaultSubfolderName'),
  };
}

function getSettingsDefaults(t = null) {
  return {
    ...SETTINGS_BASE_DEFAULTS,
    ...getLocalizedSettingsDefaults(t),
  };
}

function getStringValue(value, fallback) {
  return value === undefined || value === null || value === '' ? fallback : String(value);
}


function getBooleanValue(value, fallback) {
  return value === undefined ? fallback : value;
}

export function getInitialFormValues(settingsData = null, t = null) {
  const defaults = getSettingsDefaults(t);

  if (!settingsData) {
    return { ...defaults };
  }

  return {
    user_name: getStringValue(settingsData.user_name, defaults.user_name),
    avatar_path: getStringValue(settingsData.avatar_path, defaults.avatar_path),
    default_scan_dir: getStringValue(settingsData.default_scan_dir, defaults.default_scan_dir),
    folder_library_path: getStringValue(settingsData.folder_library_path, defaults.folder_library_path),
    collision_strategy: getStringValue(settingsData.collision_strategy, defaults.collision_strategy),
    collision_duration_tolerance_seconds: getStringValue(
      settingsData.collision_duration_tolerance_seconds,
      defaults.collision_duration_tolerance_seconds
    ),
    extras_video_action: getStringValue(settingsData.extras_video_action, defaults.extras_video_action),
    extras_sub_action: getStringValue(settingsData.extras_sub_action, defaults.extras_sub_action),
    extras_audio_action: getStringValue(settingsData.extras_audio_action, defaults.extras_audio_action),
    extras_img_action: getStringValue(settingsData.extras_img_action, defaults.extras_img_action),
    extras_meta_action: getStringValue(settingsData.extras_meta_action, defaults.extras_meta_action),
    vlc_path: getStringValue(settingsData.vlc_path, defaults.vlc_path),
    mpc_path: getStringValue(settingsData.mpc_path, defaults.mpc_path),
    tmdb_api_key: getStringValue(settingsData.tmdb_api_key, defaults.tmdb_api_key),
    tmdb_bearer_token: getStringValue(settingsData.tmdb_bearer_token, defaults.tmdb_bearer_token),
    omdb_api_key: getStringValue(settingsData.omdb_api_key, defaults.omdb_api_key),
    ui_language: getStringValue(settingsData.ui_language, defaults.ui_language),
    follow_app_language_for_media_library: getBooleanValue(
      settingsData.follow_app_language_for_media_library,
      defaults.follow_app_language_for_media_library
    ),
    follow_app_language_for_naming: getBooleanValue(
      settingsData.follow_app_language_for_naming,
      defaults.follow_app_language_for_naming
    ),
    primary_metadata_language: getStringValue(
      settingsData.primary_metadata_language,
      defaults.primary_metadata_language
    ),
    fallback_metadata_language: getStringValue(
      settingsData.fallback_metadata_language,
      defaults.fallback_metadata_language
    ),
    default_target_language: getStringValue(settingsData.default_target_language, defaults.default_target_language),
    close_button_behavior: getStringValue(settingsData.close_button_behavior, defaults.close_button_behavior),
    include_adult: getBooleanValue(settingsData.include_adult, defaults.include_adult),
    adult_gender_preference: getStringValue(settingsData.adult_gender_preference, defaults.adult_gender_preference),
    stashdb_api_key: getStringValue(settingsData.stashdb_api_key, defaults.stashdb_api_key),
    fansdb_api_key: getStringValue(settingsData.fansdb_api_key, defaults.fansdb_api_key),
    porndb_api_key: getStringValue(settingsData.porndb_api_key, defaults.porndb_api_key),
    stashdb_endpoint: getStringValue(settingsData.stashdb_endpoint, defaults.stashdb_endpoint),
    fansdb_endpoint: getStringValue(settingsData.fansdb_endpoint, defaults.fansdb_endpoint),
    porndb_endpoint: getStringValue(settingsData.porndb_endpoint, defaults.porndb_endpoint),
    custom_organization_enabled: getBooleanValue(
      settingsData.custom_organization_enabled,
      defaults.custom_organization_enabled
    ),
    organization_preset: getStringValue(settingsData.organization_preset, defaults.organization_preset),
    ui_theme: getStringValue(settingsData.ui_theme, defaults.ui_theme),
    min_video_size_mb: getStringValue(settingsData.min_video_size_mb, defaults.min_video_size_mb),
    adult_min_video_size_mb: getStringValue(settingsData.adult_min_video_size_mb, defaults.adult_min_video_size_mb),
    adult_min_video_duration_minutes: getStringValue(
      settingsData.adult_min_video_duration_minutes,
      defaults.adult_min_video_duration_minutes
    ),
    min_video_duration_minutes: getStringValue(
      settingsData.min_video_duration_minutes,
      defaults.min_video_duration_minutes
    ),
    folder_create_collection_dir: getBooleanValue(
      settingsData.folder_create_collection_dir,
      defaults.folder_create_collection_dir
    ),
    folder_collection_mode: settingsData.folder_create_collection_dir === false
      ? FOLDER_COLLECTION_MODES.NEVER
      : getStringValue(settingsData.folder_collection_mode, defaults.folder_collection_mode),
    folder_collection_threshold: getStringValue(
      settingsData.folder_collection_threshold,
      defaults.folder_collection_threshold
    ),
    naming_filename_casing: getStringValue(settingsData.naming_filename_casing, defaults.naming_filename_casing),
    naming_word_separator: getStringValue(settingsData.naming_word_separator, defaults.naming_word_separator),
    naming_movie_template: getStringValue(settingsData.naming_movie_template, defaults.naming_movie_template),
    naming_episode_template: getStringValue(settingsData.naming_episode_template, defaults.naming_episode_template),
    naming_scene_template: getStringValue(settingsData.naming_scene_template, defaults.naming_scene_template),
    naming_scene_date_format: getStringValue(settingsData.naming_scene_date_format, defaults.naming_scene_date_format),
    naming_scene_prevent_title_performer: getBooleanValue(settingsData.naming_scene_prevent_title_performer, defaults.naming_scene_prevent_title_performer),
    scene_tag_limit: getStringValue(settingsData.scene_tag_limit, defaults.scene_tag_limit),
    scene_tag_separator: getStringValue(settingsData.scene_tag_separator, defaults.scene_tag_separator),
    scene_tag_blacklist: getStringValue(settingsData.scene_tag_blacklist, defaults.scene_tag_blacklist),
    naming_squeeze_studio_names: getBooleanValue(settingsData.naming_squeeze_studio_names, defaults.naming_squeeze_studio_names),
    naming_performer_limit: getStringValue(settingsData.naming_performer_limit, defaults.naming_performer_limit),
    naming_performer_limit_keep: getBooleanValue(settingsData.naming_performer_limit_keep, defaults.naming_performer_limit_keep),
    naming_performer_splitchar: getStringValue(settingsData.naming_performer_splitchar, defaults.naming_performer_splitchar),
    naming_performer_gender_filter: getStringValue(settingsData.naming_performer_gender_filter, defaults.naming_performer_gender_filter),
    naming_performer_sort: getStringValue(settingsData.naming_performer_sort, defaults.naming_performer_sort),
    scene_grouping_mode: getStringValue(settingsData.scene_grouping_mode, defaults.scene_grouping_mode),
    folder_scene_template: getStringValue(settingsData.folder_scene_template, defaults.folder_scene_template),
    naming_custom_tag: getStringValue(settingsData.naming_custom_tag, defaults.naming_custom_tag),
    naming_video_exts: getStringValue(settingsData.naming_video_exts, defaults.naming_video_exts),
    folder_organization_enabled: getBooleanValue(
      settingsData.folder_organization_enabled,
      defaults.folder_organization_enabled
    ),
    folder_move_to_library: getBooleanValue(settingsData.folder_move_to_library, defaults.folder_move_to_library),
    folder_sort_by_type: getBooleanValue(settingsData.folder_sort_by_type, defaults.folder_sort_by_type),
    folder_movies_name: getStringValue(settingsData.folder_movies_name, defaults.folder_movies_name),
    folder_tv_name: getStringValue(settingsData.folder_tv_name, defaults.folder_tv_name),
    folder_adult_name: getStringValue(settingsData.folder_adult_name, defaults.folder_adult_name),
    naming_adult_subfolders_enabled: getBooleanValue(
      settingsData.naming_adult_subfolders_enabled,
      defaults.naming_adult_subfolders_enabled
    ),
    folder_adult_movies_name: getStringValue(
      settingsData.folder_adult_movies_name,
      defaults.folder_adult_movies_name
    ),
    folder_adult_tv_name: getStringValue(
      settingsData.folder_adult_tv_name,
      defaults.folder_adult_tv_name
    ),
    folder_adult_scenes_name: getStringValue(
      settingsData.folder_adult_scenes_name,
      defaults.folder_adult_scenes_name
    ),
    folder_create_movie_subdir: getBooleanValue(
      settingsData.folder_create_movie_subdir,
      defaults.folder_create_movie_subdir
    ),
    folder_movie_template: getStringValue(settingsData.folder_movie_template, defaults.folder_movie_template),
    folder_create_show_dir: getBooleanValue(settingsData.folder_create_show_dir, defaults.folder_create_show_dir),
    folder_tv_template: getStringValue(settingsData.folder_tv_template, defaults.folder_tv_template),
    folder_create_season_dir: getBooleanValue(
      settingsData.folder_create_season_dir,
      defaults.folder_create_season_dir
    ),
    folder_season_template: getStringValue(settingsData.folder_season_template, defaults.folder_season_template),
    folder_create_episode_dir: getBooleanValue(
      settingsData.folder_create_episode_dir,
      defaults.folder_create_episode_dir
    ),
    folder_episode_template: getStringValue(settingsData.folder_episode_template, defaults.folder_episode_template),
    folder_remove_empty: getBooleanValue(settingsData.folder_remove_empty, defaults.folder_remove_empty),
    folder_collection_template: getStringValue(
      settingsData.folder_collection_template,
      defaults.folder_collection_template
    ),
    extras_enabled: getBooleanValue(settingsData.extras_enabled, defaults.extras_enabled),
    extras_sub_exts: getStringValue(settingsData.extras_sub_exts, defaults.extras_sub_exts),
    extras_audio_exts: getStringValue(settingsData.extras_audio_exts, defaults.extras_audio_exts),
    extras_img_exts: getStringValue(settingsData.extras_img_exts, defaults.extras_img_exts),
    extras_meta_exts: getStringValue(settingsData.extras_meta_exts, defaults.extras_meta_exts),
    extras_video_template: getStringValue(settingsData.extras_video_template, defaults.extras_video_template),
    extras_sub_template: getStringValue(settingsData.extras_sub_template, defaults.extras_sub_template),
    extras_audio_template: getStringValue(settingsData.extras_audio_template, defaults.extras_audio_template),
    extras_img_template: getStringValue(settingsData.extras_img_template, defaults.extras_img_template),
    extras_meta_template: getStringValue(settingsData.extras_meta_template, defaults.extras_meta_template),
    extras_folder_mode: getStringValue(settingsData.extras_folder_mode, defaults.extras_folder_mode),
    extras_subfolder_name: getStringValue(settingsData.extras_subfolder_name, defaults.extras_subfolder_name),
  };
}


