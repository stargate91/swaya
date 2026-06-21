import os
from typing import Callable, Optional, Dict, Any, List
from pathlib import Path

from app.core.enums import MediaType, ItemStatus
from app.core.constants import DEFAULT_FALLBACK_LANGUAGE
from app.core.language import LanguageService
from .config import Casing, Separator, ExtraOrg, FormatterConfig
from .models import RenamePreview
from .context_builder import ContextBuilder
from .template_renderer import TemplateRenderer
from .path_resolver import PathResolver

class Formatter:
    """
    Generator for standardized file and directory names.
    Handles template rendering, illegal character stripping, and collision resolution.
    """

    ILLEGAL_CHARS = TemplateRenderer.ILLEGAL_CHARS
    MULTI_SPACE = TemplateRenderer.MULTI_SPACE
    TEMPLATE_VAR = TemplateRenderer.TEMPLATE_VAR

    def __init__(self, config: Optional[FormatterConfig] = None, replacement_decider: Optional[Callable[[RenamePreview], Optional[bool]]] = None):
        self.config = config or FormatterConfig()
        self.context_builder = ContextBuilder(self.config)
        self.renderer = TemplateRenderer(self.config)
        self.path_resolver = PathResolver(self.config, replacement_decider)

    def _get_absolute_path(self, item_or_extra: Any) -> str:
        # Reconstruct path using library root path + relative path
        library = getattr(item_or_extra, "library", None)
        if not library and hasattr(item_or_extra, "media_item") and item_or_extra.media_item:
            library = getattr(item_or_extra.media_item, "library", None)

        root = getattr(library, "root_path", "") if library else ""
        rel = getattr(item_or_extra, "relative_path", "")
        if root and rel:
            return f"{root.rstrip('/')}/{rel.lstrip('/')}".replace("\\", "/")
        return getattr(item_or_extra, "current_path", "") or rel or ""

    def _match_language_code(self, lang_a: Optional[str], lang_b: Optional[str]) -> bool:
        if not lang_a or not lang_b:
            return False
        return lang_a.split("-", 1)[0].strip().lower() == lang_b.split("-", 1)[0].strip().lower()

    def _pick_localization(self, match: Any, item: Any = None):
        localizations = getattr(match, "localizations", None) or []
        if not localizations:
            return None

        # 1. Check item-level custom language override (UserOverride)
        overrides = None
        if item:
            if hasattr(item, "overrides"):
                overrides = item.overrides
            elif isinstance(item, dict):
                overrides = item.get("overrides")
        
        if not overrides and match:
            media_item = getattr(match, "media_item", None)
            if media_item and hasattr(media_item, "overrides"):
                overrides = media_item.overrides
                
        preferred_locale = None
        if overrides:
            if hasattr(overrides, "custom_language"):
                preferred_locale = overrides.custom_language
            elif isinstance(overrides, dict):
                preferred_locale = overrides.get("custom_language")

        # 2. Fall back to config-level target language settings
        if not preferred_locale:
            preferred_locale = self.config.default_target_language

        preferred_locale = preferred_locale or DEFAULT_FALLBACK_LANGUAGE
        return LanguageService.get_best_localization(localizations, preferred_locale)

    def _get_target_name_and_subpath(self, item: Any, match: Any, loc: Any) -> tuple[str, str]:
        """Calculates target name and subpath for a media item."""
        is_inplace = not self.config.org_enabled or not self.config.move_to_library or not self.config.library_path
        media_type = getattr(match, "media_type", MediaType.MOVIE) if match else MediaType.MOVIE

        if is_inplace:
             if media_type == MediaType.SCENE:
                 target_name = self.format_scene_filename(self.build_scene_context(item, match, loc))
             elif media_type == MediaType.JAV:
                 target_name = self.format_jav_filename(self.build_scene_context(item, match, loc))
             elif media_type == MediaType.MOVIE:
                 target_name = self.format_movie_filename(self.build_movie_context(item, match, loc))
             else:
                 target_name = self.format_episode_filename(self.build_tv_context(item, match, loc))
             return target_name, ""

        if media_type in (MediaType.SCENE, MediaType.JAV):
            context = self.build_scene_context(item, match, loc)
            if media_type == MediaType.JAV:
                target_name = self.format_jav_filename(context)
            else:
                target_name = self.format_scene_filename(context)
            
            sub_path_parts = []
            if match and getattr(match, "is_adult", False):
                sub_path_parts.append(self.config.adult_dir_name)
                if self.config.naming_adult_subfolders_enabled:
                    if media_type == MediaType.JAV:
                        sub_path_parts.append(self.config.adult_jav_dir_name)
                    else:
                        sub_path_parts.append(self.config.adult_scenes_dir_name)
                
                grouping_mode = self.config.jav_grouping_mode if media_type == MediaType.JAV else self.config.scene_grouping_mode
                if grouping_mode == "studio" and context.get("studio"):
                    sub_path_parts.append(context["studio"])
                elif grouping_mode == "parent_studio" and context.get("parent_studio"):
                    sub_path_parts.append(context["parent_studio"])
                elif grouping_mode == "parent_studio_studio":
                    parent_studio = context.get("parent_studio")
                    studio = context.get("studio")
                    if parent_studio:
                        sub_path_parts.append(parent_studio)
                    if studio and studio != parent_studio:
                        sub_path_parts.append(studio)
            else:
                if media_type == MediaType.JAV:
                    sub_path_parts.append(getattr(self.config, "adult_jav_dir_name", "JAV"))
                else:
                    scenes_dir = getattr(self.config, "scenes_dir_name", "Scenes")
                    sub_path_parts.append(scenes_dir)
                
            folder_tmpl = self.config.folder_jav_template if media_type == MediaType.JAV else self.config.folder_scene_template
            if folder_tmpl:
                scene_folder = self._render(folder_tmpl, context, is_file=False)
                sub_path_parts.append(scene_folder)
                
            sub_path_obj = Path()
            for p in sub_path_parts:
                if p and str(p).strip() and str(p) != ".":
                    sub_path_obj = sub_path_obj / p
            target_subpath = str(sub_path_obj).replace("\\", "/")
            
        elif media_type == MediaType.MOVIE:
            context = self.build_movie_context(item, match, loc)
            target_name = self.format_movie_filename(context)
            
            sub_path_parts = []
            if match and getattr(match, "is_adult", False):
                sub_path_parts.append(self.config.adult_dir_name)
                if self.config.naming_adult_subfolders_enabled:
                    sub_path_parts.append(self.config.adult_movies_dir_name)
            else:
                if self.config.sort_by_type:
                    sub_path_parts.append(self.config.movies_dir_name)
                    
            if self.config.create_movie_subdir:
                folder_name = self.format_movie_foldername(context, match)
                sub_path_parts.append(folder_name)
                
            sub_path_obj = Path()
            for p in sub_path_parts:
                if p and str(p).strip() and str(p) != ".":
                    sub_path_obj = sub_path_obj / p
            target_subpath = str(sub_path_obj).replace("\\", "/")
            
        elif media_type in [MediaType.TV, MediaType.SEASON, MediaType.EPISODE]:
            context = self.build_tv_context(item, match, loc)
            target_name = self.format_episode_filename(context)
                
            sub_path_parts = []
            if match and getattr(match, "is_adult", False):
                sub_path_parts.append(self.config.adult_dir_name)
                if self.config.naming_adult_subfolders_enabled:
                    sub_path_parts.append(self.config.adult_tv_dir_name)
            else:
                if self.config.sort_by_type:
                    sub_path_parts.append(self.config.tv_dir_name)
                    
            if self.config.create_tv_dir:
                tv_folder = self.format_tv_foldername(context)
                sub_path_parts.append(tv_folder)
            if self.config.create_season_dir:
                season_folder = self.format_season_foldername(context)
                sub_path_parts.append(season_folder)
                
            sub_path_obj = Path()
            for p in sub_path_parts:
                if p and str(p).strip() and str(p) != ".":
                    sub_path_obj = sub_path_obj / p
            target_subpath = str(sub_path_obj).replace("\\", "/")
        else:
            target_name = getattr(item, "filename", "")
            target_subpath = ""

        # Normalize slashes
        target_subpath = target_subpath.replace("\\", "/")
        target_name = target_name.replace("\\", "/")
        return target_name, target_subpath

    def format_item(self, item: Any, match: Any, loc: Any) -> RenamePreview:
        """
        Generates a preview for a single item using official metadata.
        Used for updating planned_path after enrichment.
        """
        orig_path = self._get_absolute_path(item)
        target_name, target_subpath = self._get_target_name_and_subpath(item, match, loc)
        dest_root = self.config.library_path if self.config.move_to_library and self.config.library_path else os.path.dirname(orig_path)
        media_type = getattr(match, "media_type", MediaType.MOVIE) if match else MediaType.MOVIE

        preview = RenamePreview(
            item_id=item.id,
            original_path=orig_path,
            target_name=target_name,
            target_subpath=target_subpath,
            item_type=media_type.value,
            destination_root=dest_root,
            source_size=getattr(item, "size", 0),
            source_duration=getattr(item, "duration", None),
            source_resolution=getattr(item, "resolution", None),
            source_video_bitrate=getattr(item, "video_bitrate", None)
        )
        self.resolve_collisions([preview])
        self._check_path_lengths(preview)
        return preview

    def plan_rename(self, match: Any, destination_root: str) -> RenamePreview:
        """
        Generates a comprehensive renaming plan for a media item and all its extras.
        Validates path lengths and resolves potential filename collisions.
        """
        item = getattr(match, "media_item", None)
        if not item:
            raise ValueError("No media_item attached to match")
            
        loc = self._pick_localization(match, item)
        if not loc:
            raise ValueError("No localization available for rename planning")
        
        orig_path = self._get_absolute_path(item)
        media_type = getattr(match, "media_type", MediaType.MOVIE)

        # 1. Context Building & Route Generation
        is_inplace = not self.config.org_enabled or not self.config.move_to_library or not self.config.library_path
        target_name, target_subpath = self._get_target_name_and_subpath(item, match, loc)

        # Defining a Destination Folder (Global Library vs In-place)
        effective_root = destination_root
        if self.config.move_to_library and self.config.library_path:
            effective_root = self.config.library_path
        elif not destination_root:
            effective_root = os.path.dirname(orig_path)

        # 2. Create a main preview
        main_preview = RenamePreview(
            item_id=item.id,
            original_path=orig_path,
            target_name=target_name,
            target_subpath=target_subpath,
            item_type=media_type.value,
            destination_root=effective_root,
            source_size=getattr(item, "size", 0),
            source_duration=getattr(item, "duration", None),
            source_resolution=getattr(item, "resolution", None),
            source_video_bitrate=getattr(item, "video_bitrate", None)
        )

        # 3. Planning extras
        if self.config.extras_enabled:
            parent_name_no_ext = target_name.rsplit(".", 1)[0]
            for extra in getattr(item, "extras", []):
                cat = extra.category.value if hasattr(extra.category, 'value') else str(extra.category)
                
                short_cat = cat.lower()
                if short_cat == "subtitle": short_cat = "sub"
                elif short_cat == "image": short_cat = "img"
                elif short_cat == "metadata": short_cat = "meta"
                
                action = getattr(self.config, f"extra_{short_cat}_action", "rename")
                
                if action == "ignore":
                    continue
                
                extra_orig_path = self._get_absolute_path(extra)
                if action == "delete":
                    main_preview.extra_previews.append(RenamePreview(
                        item_id=extra.id,
                        original_path=extra_orig_path,
                        target_name="", # Empty name indicates deletion
                        target_subpath="",
                        item_type="extra",
                        destination_root="",
                        action="delete",
                        extra_id=extra.id,
                        warnings=["File will be deleted according to extras settings."]
                    ))
                    continue

                extra_ctx = self.build_extra_context(extra, parent_name_no_ext)
                extra_name = self.format_extra_filename(extra_ctx)
                extra_sub = self.get_extra_subpath(extra)
                
                final_extra_sub = "" if is_inplace else str(Path(target_subpath) / extra_sub)
                
                main_preview.extra_previews.append(RenamePreview(
                    item_id=extra.id,
                    original_path=extra_orig_path,
                    target_name=extra_name,
                    target_subpath=final_extra_sub,
                    item_type="extra",
                    destination_root=effective_root,
                    extra_id=extra.id
                ))

        # 4. Resolve collisions
        self.resolve_collisions([main_preview])

        # 5. Path length check
        self._check_path_lengths(main_preview)

        return main_preview

    def _check_path_lengths(self, preview: RenamePreview):
        """Recursively checks path lengths and issues a warning."""
        self.path_resolver.check_path_lengths(preview)

    def resolve_collisions(self, previews: List[RenamePreview]) -> List[RenamePreview]:
        """
        Detects collisions and automatically numbers the extras.
        Modifies the 'previews' list in-place.
        """
        return self.path_resolver.resolve_collisions(previews)

    # =========================================================================
    # Public API - Films
    # =========================================================================

    def format_movie_filename(self, context: Dict[str, Any]) -> str:
        return self._render(self.config.movie_file, context, is_file=True)

    def format_scene_filename(self, context: Dict[str, Any]) -> str:
        return self._render(self.config.scene_file, context, is_file=True)

    def format_jav_filename(self, context: Dict[str, Any]) -> str:
        return self._render(self.config.naming_jav_template, context, is_file=True)

    def format_movie_foldername(self, context: Dict[str, Any], match: Optional[Any] = None) -> str:
        if not self.config.create_movie_subdir:
            return ""
            
        coll_val = context.get("Collection") or context.get("collection")
        if self._should_use_collection_folder(match, coll_val):
            coll_name = self.format_collection_foldername(context)
            movie_name = self._render(self.config.movie_folder, context, is_file=False)
            if coll_name and movie_name:
                return f"{coll_name}/{movie_name}"
            return movie_name or coll_name
            
        return self._render(self.config.movie_folder, context, is_file=False)

    def format_collection_foldername(self, context: Dict[str, Any]) -> str:
        tmpl = self.config.collection_folder or "{Collection}"
        return self._render(tmpl, context, is_file=False)

    def _should_use_collection_folder(self, match: Optional[Any], collection_value: Any) -> bool:
        if not self.config.create_collection_dir:
            return False
        if not collection_value or not str(collection_value).strip():
            return False

        mode = getattr(self.config, "collection_folder_mode", "threshold")
        if mode == "never":
            return False
        if mode == "always":
            return True
        if mode == "complete_only":
            owned_count = self._count_owned_collection_movies(match)
            total_parts = self._get_collection_total_parts(match)
            return total_parts > 0 and owned_count >= total_parts
        if mode != "threshold":
            return True

        owned_count = self._count_owned_collection_movies(match)
        threshold = max(1, int(getattr(self.config, "collection_folder_threshold", 3) or 3))
        return owned_count >= threshold

    def _count_owned_collection_movies(self, match: Optional[Any]) -> int:
        collection_entity = getattr(match, "collection", None)
        if not match or not collection_entity:
            return 0

        owned_statuses = {ItemStatus.MATCHED, ItemStatus.ORGANIZED, ItemStatus.RENAMED}
        seen_item_ids = set()
        for related_match in getattr(collection_entity, "matches", []) or []:
            related_item = getattr(related_match, "media_item", None)
            if not related_item or getattr(related_match, "media_type", None) != MediaType.MOVIE or not getattr(related_match, "is_active", True):
                continue
            if getattr(related_item, "status", None) not in owned_statuses:
                continue
            seen_item_ids.add(related_item.id)

        current_item = getattr(match, "media_item", None)
        if current_item and getattr(current_item, "item_type", None) == MediaType.MOVIE and current_item.id not in seen_item_ids:
            seen_item_ids.add(current_item.id)

        return len(seen_item_ids)

    def _get_collection_total_parts(self, match: Optional[Any]) -> int:
        collection_entity = getattr(match, "collection", None)
        if not match or not collection_entity:
            return 0
        try:
            return max(0, int(getattr(collection_entity, "total_parts", 0) or 0))
        except (TypeError, ValueError):
            return 0

    # =========================================================================
    # Public API - TV
    # =========================================================================

    def format_tv_foldername(self, context: Dict[str, Any]) -> str:
        if not self.config.create_tv_dir:
            return ""
        return self._render(self.config.tv_folder, context, is_file=False)

    def format_season_foldername(self, context: Dict[str, Any]) -> str:
        if not self.config.create_season_dir:
            return ""
        return self._render(self.config.season_folder, context, is_file=False)

    def format_episode_filename(self, context: Dict[str, Any]) -> str:
        return self._render(self.config.episode_file, context, is_file=True)

    def format_extra_filename(self, context: Dict[str, Any]) -> str:
        cat = context.get("category", "").lower()
        if cat == "video":
            tmpl = self.config.extra_video_template
        elif cat == "subtitle":
            tmpl = self.config.extra_sub_template
        elif cat == "audio":
            tmpl = self.config.extra_audio_template
        elif cat == "image":
            tmpl = self.config.extra_img_template
        elif cat == "metadata":
            tmpl = self.config.extra_meta_template
        else:
            tmpl = "{parent_name} {sub_category}"
            
        name = self._render(tmpl, context, is_file=True)
        name = " ".join(name.split())
        return name

    def get_extra_subpath(self, extra) -> str:
        """It returns the subdirectory of the extra file based on the strategy."""
        if self.config.extras_folder_mode == "flat":
            return ""
        return self.config.extras_subfolder_name

    def get_category_folder(self, item_type_value: str, match: Optional[Any] = None) -> str:
        """It returns the category folder name (Movies/TV), if enabled."""
        if not self.config.sort_by_type:
            return ""
        if match and getattr(match, "is_adult", False):
            return self.config.adult_dir_name
        if item_type_value == "movie":
            return self.config.movies_dir_name
        if item_type_value in ["tv", "episode"]:
            return self.config.tv_dir_name
        return ""

    # =========================================================================
    # Context Builders
    # =========================================================================

    def build_movie_context(self, item, match, loc) -> Dict[str, Any]:
        """Collects variables for a movie."""
        return self.context_builder.build_movie_context(item, match, loc)

    def build_scene_context(self, item, match, loc) -> Dict[str, Any]:
        """Collects variables for an adult scene."""
        return self.context_builder.build_scene_context(item, match, loc)

    def build_tv_context(self, item, match, loc, children: List[Any] = None) -> Dict[str, Any]:
        """Collects variables for a TV show/season/episode."""
        return self.context_builder.build_tv_context(item, match, loc, children)

    def build_extra_context(self, extra, parent_formatted_name: str) -> Dict[str, Any]:
        """Collects variables for an extra file."""
        return self.context_builder.build_extra_context(extra, parent_formatted_name)

    # =========================================================================
    # Helper Functions
    # =========================================================================

    def _render(self, template: str, context: Dict[str, Any], is_file: bool = True) -> str:
        """Renders the template and automatically adds the extension if it's a file."""
        return self.renderer.render(template, context, is_file)

    def apply_casing(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.renderer.apply_casing(text, context)

    def apply_separator(self, text: str) -> str:
        return self.renderer.apply_separator(text)

    def format_number(self, num, width: int = 2) -> str:
        return self.renderer.format_number(num, width)

    def sanitize(self, text: str) -> str:
        return self.renderer.sanitize(text)
