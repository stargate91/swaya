from enum import Enum
from dataclasses import dataclass

class Casing(Enum):
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"
    DEFAULT = "default"

class Separator(Enum):
    SPACE = " "
    DOT = "."
    DASH = "-"
    UNDERSCORE = "_"

class ExtraOrg(Enum):
    SAME_FOLDER = "same_folder"
    SUBFOLDER = "subfolder"
    CATEGORY_FOLDERS = "category_folders"

@dataclass
class FormatterConfig:
    casing: Casing = Casing.DEFAULT
    separator: Separator = Separator.SPACE
    zero_pad: bool = True
    custom_text: str = ""

    # Naming Templates
    movie_file: str = "{title} ({year}) {resolution}"
    episode_file: str = "{tv_title} - S{season}E{episode} - {episode_title}"
    scene_file: str = "{studio} {performers} {date} {title} [{resolution}]"
    scene_date_format: str = "%Y-%m-%d"
    scene_prevent_title_performer: bool = True
    scene_tag_limit: int = 0
    scene_tag_separator: str = " "
    scene_tag_blacklist: str = ""
    
    # Part Naming
    part_keyword: str = "Part"
    part_numbering: str = "numeric"
    part_separator: Separator = Separator.SPACE

    # Performer Settings (Adult)
    naming_squeeze_studio_names: bool = True
    naming_performer_limit: int = 3
    naming_performer_limit_keep: bool = False
    naming_performer_splitchar: str = " & "
    naming_performer_gender_filter: str = "all"
    naming_performer_sort: str = "order"

    # Folder Organization
    org_enabled: bool = True
    move_to_library: bool = True
    library_path: str = ""
    sort_by_type: bool = True
    movies_dir_name: str = "Movies"
    tv_dir_name: str = "TV Shows"
    adult_dir_name: str = "Adult"
    adult_movies_dir_name: str = "Movies"
    adult_tv_dir_name: str = "TV Shows"
    adult_scenes_dir_name: str = "Scenes"
    adult_jav_dir_name: str = "JAV"
    scenes_dir_name: str = "Scenes"
    naming_adult_subfolders_enabled: bool = True
    scene_grouping_mode: str = "none"
    jav_grouping_mode: str = "parent_studio_studio"
    folder_scene_template: str = ""
    folder_jav_template: str = ""
    naming_jav_template: str = "{studio} - {date} - {performers} - {title} [{resolution}]"
    collision_strategy: str = "keep_both"
    collision_duration_tolerance_seconds: int = 10
    
    # Folder Templates
    create_movie_subdir: bool = True
    movie_folder: str = "{title} ({year})"
    create_collection_dir: bool = True
    collection_folder_mode: str = "threshold"
    collection_folder_threshold: int = 3
    collection_folder: str = "{collection}"
    create_tv_dir: bool = True
    tv_folder: str = "{tv_title} ({year_range})"
    create_season_dir: bool = True
    season_folder: str = "Season {season}"
    create_episode_dir: bool = False
    episode_folder: str = "{tv_title} - {season}{episode}"
    
    remove_empty: bool = True
    
    # Extras Naming & Actions
    extras_enabled: bool = True
    extra_video_action: str = "rename"
    extra_sub_action: str = "rename"
    extra_audio_action: str = "rename"
    extra_img_action: str = "rename"
    extra_meta_action: str = "rename"
    
    # Extras Templates
    extra_video_template: str = "{parent_name}-{sub_category}"
    extra_sub_template: str = "{parent_name}.{language}"
    extra_audio_template: str = "{parent_name}.{language}"
    extra_img_template: str = "{sub_category}"
    extra_meta_template: str = "{parent_name}"
    
    # Extras Folder Placement
    extras_folder_mode: str = "subfolder"
    extras_subfolder_name: str = "Extras"
    
    # Target Language / Naming language settings
    default_target_language: str = "en"
    follow_app_language_for_naming: bool = True
