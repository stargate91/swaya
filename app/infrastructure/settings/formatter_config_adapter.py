from pathlib import Path
from typing import Any, Dict, Optional

from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.library.models import Library, MediaItem
from app.domains.library.services.formatter.config import Casing, FormatterConfig, Separator
from app.domains.settings.models import SystemSetting, UserSetting


def _settings_dict(db_session, user_id: int = 1) -> Dict[str, Any]:
    settings = {}
    for setting in db_session.query(SystemSetting).all():
        settings[setting.key] = setting.value
    for setting in db_session.query(UserSetting).filter(UserSetting.user_id == user_id).all():
        settings[setting.key] = setting.value
    return settings


def _normalize_template(value: str) -> str:
    return value.replace("{{", "{").replace("}}", "}")


def _localized_builtin_folder_name(settings: Dict[str, Any], setting_key: str, current_value: str):
    if not settings.get("follow_app_language_for_naming", True):
        return current_value

    ui_lang = str(settings.get("ui_language", DEFAULT_FALLBACK_LANGUAGE) or DEFAULT_FALLBACK_LANGUAGE).lower()
    localized_aliases = {
        "folder_movies_name": {"en": {"Movies"}, "hu": {"Movies", "Filmek"}},
        "folder_tv_name": {"en": {"TV Shows", "Shows", "TV"}, "hu": {"TV Shows", "Shows", "TV", "Sorozatok"}},
        "folder_adult_name": {"en": {"Adult"}, "hu": {"Adult", "Felnott", "Feln\u0151tt"}},
        "folder_adult_movies_name": {"en": {"Movies"}, "hu": {"Movies", "Filmek"}},
        "folder_adult_tv_name": {"en": {"TV Shows", "Shows", "TV"}, "hu": {"TV Shows", "Shows", "TV", "Sorozatok"}},
        "folder_adult_scenes_name": {"en": {"Scenes"}, "hu": {"Scenes", "Jelenetek"}},
        "folder_adult_jav_name": {"en": {"JAV"}, "hu": {"JAV", "JAW"}},
        "folder_scenes_name": {"en": {"Scenes"}, "hu": {"Scenes", "Jelenetek"}},
        "extras_subfolder_name": {"en": {"Extras", "extras"}, "hu": {"Extras", "extras", "Extrak", "Extr\u00e1k"}},
    }
    localized_targets = {
        "en": {
            "folder_movies_name": "Movies",
            "folder_tv_name": "TV Shows",
            "folder_adult_name": "Adult",
            "folder_adult_movies_name": "Movies",
            "folder_adult_tv_name": "TV Shows",
            "folder_adult_scenes_name": "Scenes",
            "folder_adult_jav_name": "JAV",
            "folder_scenes_name": "Scenes",
            "extras_subfolder_name": "Extras",
        },
        "hu": {
            "folder_movies_name": "Filmek",
            "folder_tv_name": "Sorozatok",
            "folder_adult_name": "Feln\u0151tt",
            "folder_adult_movies_name": "Filmek",
            "folder_adult_tv_name": "Sorozatok",
            "folder_adult_scenes_name": "Jelenetek",
            "folder_adult_jav_name": "JAW",
            "folder_scenes_name": "Jelenetek",
            "extras_subfolder_name": "Extr\u00e1k",
        },
    }

    target_lang = "hu" if ui_lang == "hu" else "en"
    if current_value in localized_aliases.get(setting_key, {}).get(target_lang, set()):
        return localized_targets[target_lang][setting_key]
    return current_value


def load_formatter_config_from_db(db_session, user_id: int = 1) -> FormatterConfig:
    config = FormatterConfig()
    try:
        settings = _settings_dict(db_session, user_id)

        config.follow_app_language_for_naming = settings.get("follow_app_language_for_naming", True)
        if config.follow_app_language_for_naming:
            config.default_target_language = settings.get("ui_language", "en")
        else:
            config.default_target_language = settings.get("default_target_language", "en")

        c_val = settings.get("naming_filename_casing", "default")
        if c_val == "lower":
            config.casing = Casing.LOWER
        elif c_val == "upper":
            config.casing = Casing.UPPER
        elif c_val == "title":
            config.casing = Casing.TITLE
        else:
            config.casing = Casing.DEFAULT

        s_val = settings.get("naming_word_separator", "space")
        if s_val == "dot":
            config.separator = Separator.DOT
        elif s_val == "dash":
            config.separator = Separator.DASH
        elif s_val == "underscore":
            config.separator = Separator.UNDERSCORE
        else:
            config.separator = Separator.SPACE

        config.movie_file = _normalize_template(settings.get("naming_movie_template", config.movie_file))
        config.episode_file = _normalize_template(settings.get("naming_episode_template", config.episode_file))
        config.scene_file = _normalize_template(settings.get("naming_scene_template", config.scene_file))
        config.scene_date_format = settings.get("naming_scene_date_format", config.scene_date_format)
        config.scene_prevent_title_performer = settings.get("naming_scene_prevent_title_performer", config.scene_prevent_title_performer)
        try:
            config.scene_tag_limit = max(0, int(settings.get("scene_tag_limit", config.scene_tag_limit)))
        except (TypeError, ValueError):
            pass
        config.scene_tag_separator = settings.get("scene_tag_separator", config.scene_tag_separator)
        config.scene_tag_blacklist = settings.get("scene_tag_blacklist", config.scene_tag_blacklist)

        config.naming_squeeze_studio_names = settings.get("naming_squeeze_studio_names", config.naming_squeeze_studio_names)
        try:
            config.naming_performer_limit = int(settings.get("naming_performer_limit", config.naming_performer_limit))
        except (TypeError, ValueError):
            pass
        config.naming_performer_limit_keep = settings.get("naming_performer_limit_keep", config.naming_performer_limit_keep)
        config.naming_performer_splitchar = settings.get("naming_performer_splitchar", config.naming_performer_splitchar)
        config.naming_performer_gender_filter = settings.get("naming_performer_gender_filter", config.naming_performer_gender_filter)
        config.naming_performer_sort = settings.get("naming_performer_sort", config.naming_performer_sort)

        config.movie_folder = _normalize_template(settings.get("folder_movie_template", config.movie_folder))
        config.collection_folder = _normalize_template(settings.get("folder_collection_template", config.collection_folder))
        config.tv_folder = _normalize_template(settings.get("folder_tv_template", config.tv_folder))
        config.season_folder = _normalize_template(settings.get("folder_season_template", config.season_folder))
        config.episode_folder = _normalize_template(settings.get("folder_episode_template", config.episode_folder))

        config.extra_video_template = _normalize_template(settings.get("extras_video_template", config.extra_video_template))
        config.extra_sub_template = _normalize_template(settings.get("extras_sub_template", config.extra_sub_template))
        config.extra_audio_template = _normalize_template(settings.get("extras_audio_template", config.extra_audio_template))
        config.extra_img_template = _normalize_template(settings.get("extras_img_template", config.extra_img_template))
        config.extra_meta_template = _normalize_template(settings.get("extras_meta_template", config.extra_meta_template))

        config.org_enabled = settings.get("folder_organization_enabled", True)
        config.move_to_library = settings.get("folder_move_to_library", True)
        config.library_path = settings.get("folder_library_path", "")
        config.sort_by_type = settings.get("folder_sort_by_type", True)
        config.movies_dir_name = _localized_builtin_folder_name(settings, "folder_movies_name", settings.get("folder_movies_name", "Movies"))
        config.tv_dir_name = _localized_builtin_folder_name(settings, "folder_tv_name", settings.get("folder_tv_name", "TV Shows"))
        config.adult_dir_name = _localized_builtin_folder_name(settings, "folder_adult_name", settings.get("folder_adult_name", "Adult"))
        config.adult_movies_dir_name = _localized_builtin_folder_name(settings, "folder_adult_movies_name", settings.get("folder_adult_movies_name", "Movies"))
        config.adult_tv_dir_name = _localized_builtin_folder_name(settings, "folder_adult_tv_name", settings.get("folder_adult_tv_name", "TV Shows"))
        config.adult_scenes_dir_name = _localized_builtin_folder_name(settings, "folder_adult_scenes_name", settings.get("folder_adult_scenes_name", "Scenes"))
        config.adult_jav_dir_name = _localized_builtin_folder_name(settings, "folder_adult_jav_name", settings.get("folder_adult_jav_name", "JAV"))
        config.scenes_dir_name = _localized_builtin_folder_name(settings, "folder_scenes_name", settings.get("folder_scenes_name", "Scenes"))
        config.naming_adult_subfolders_enabled = settings.get("naming_adult_subfolders_enabled", config.naming_adult_subfolders_enabled)
        grouping_mode = settings.get("scene_grouping_mode", config.scene_grouping_mode)
        config.scene_grouping_mode = grouping_mode if grouping_mode in {"none", "studio", "parent_studio", "parent_studio_studio"} else "none"
        jav_group_mode = settings.get("jav_grouping_mode", config.jav_grouping_mode)
        config.jav_grouping_mode = jav_group_mode if jav_group_mode in {"none", "studio", "parent_studio", "parent_studio_studio"} else "none"
        config.folder_scene_template = _normalize_template(settings.get("folder_scene_template", config.folder_scene_template))
        config.folder_jav_template = _normalize_template(settings.get("folder_jav_template", config.folder_jav_template))
        config.naming_jav_template = _normalize_template(settings.get("naming_jav_template", config.naming_jav_template))
        config.collision_strategy = settings.get("collision_strategy", "keep_both")
        config.collision_duration_tolerance_seconds = int(settings.get("collision_duration_tolerance_seconds", 10) or 10)

        config.create_movie_subdir = settings.get("folder_create_movie_subdir", True)
        config.create_collection_dir = settings.get("folder_create_collection_dir", True)
        raw_collection_mode = settings.get("folder_collection_mode")
        if isinstance(raw_collection_mode, str) and raw_collection_mode in {"never", "always", "threshold", "complete_only"}:
            config.collection_folder_mode = raw_collection_mode
        else:
            config.collection_folder_mode = "threshold" if config.create_collection_dir else "never"
        try:
            config.collection_folder_threshold = max(1, int(settings.get("folder_collection_threshold", 3) or 3))
        except (TypeError, ValueError):
            config.collection_folder_threshold = 3
        config.create_tv_dir = settings.get("folder_create_show_dir", True)
        config.create_season_dir = settings.get("folder_create_season_dir", True)
        config.create_episode_dir = settings.get("folder_create_episode_dir", False)
        config.remove_empty = settings.get("folder_remove_empty", True)

        config.extras_enabled = settings.get("extras_enabled", True)
        config.extra_video_action = settings.get("extras_video_action", "rename")
        config.extra_sub_action = settings.get("extras_sub_action", "rename")
        config.extra_audio_action = settings.get("extras_audio_action", "rename")
        config.extra_img_action = settings.get("extras_img_action", "rename")
        config.extra_meta_action = settings.get("extras_meta_action", "rename")
        config.extras_folder_mode = settings.get("extras_folder_mode", "subfolder")
        config.extras_subfolder_name = _localized_builtin_folder_name(
            settings,
            "extras_subfolder_name",
            settings.get("extras_subfolder_name", config.extras_subfolder_name),
        )
        config.custom_text = settings.get("naming_custom_tag", "default")
    except Exception as e:
        print(f"Error loading FormatterConfig from DB: {e}")
    return config




def build_formatter_from_db(db_session, user_id: int = 1):
    from app.domains.library.services.formatter.formatter import Formatter

    config = load_formatter_config_from_db(db_session, user_id)
    replacement_decider = ExistingMediaReplacementDecider(db_session, config.collision_duration_tolerance_seconds)
    return Formatter(config, replacement_decider=replacement_decider)


class ExistingMediaReplacementDecider:
    def __init__(self, db_session, tolerance_seconds: int):
        self.db = db_session
        self.tolerance_seconds = tolerance_seconds

    def __call__(self, preview) -> Optional[bool]:
        try:
            target_path = Path(preview.target_path)
            target_path_lower = str(target_path).replace("\\", "/").lower()

            target_item = None
            libraries = self.db.query(Library).all()
            for library in libraries:
                root_lower = str(library.root_path).replace("\\", "/").lower().rstrip("/")
                if target_path_lower.startswith(root_lower):
                    rel = str(target_path)[len(root_lower):].strip("/\\").replace("\\", "/")
                    target_item = self.db.query(MediaItem).filter(
                        MediaItem.library_id == library.id,
                        MediaItem.relative_path == rel,
                    ).first()
                    if target_item:
                        break

            if not target_item:
                return None

            if preview.source_duration and target_item.duration:
                if abs(float(preview.source_duration) - float(target_item.duration)) > self.tolerance_seconds:
                    return False

            source_score = (
                _resolution_height(preview.source_resolution),
                preview.source_video_bitrate or 0,
                preview.source_size or 0,
            )
            target_score = (
                _resolution_height(target_item.resolution),
                target_item.video_bitrate or 0,
                target_item.size or 0,
            )
            return source_score > target_score
        except Exception:
            return None


def _resolution_height(resolution: str) -> int:
    if not resolution:
        return 0
    import re

    match = re.search(r"(\d{3,4})p", str(resolution).lower())
    if match:
        return int(match.group(1))
    if "4k" in str(resolution).lower():
        return 2160
    if "8k" in str(resolution).lower():
        return 4320
    return 0
