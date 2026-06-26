import os
import logging
from pathlib import Path
from typing import Any, List, Optional, Tuple

from app.shared_kernel.enums import MediaType
from app.domains.library.services.formatter.models import RenamePreview

logger = logging.getLogger(__name__)

class PlanGenerator:
    """
    Submodule to orchestrate renaming previews for media items and all of their extra files.
    """
    def __init__(self, formatter):
        self.formatter = formatter

    @property
    def config(self):
        return self.formatter.config

    def _get_target_name_and_subpath(
        self,
        item: Any,
        match: Any,
        loc: Any,
        people_links: Optional[List[Any]] = None
    ) -> Tuple[str, str]:
        is_inplace = not self.config.org_enabled or not self.config.move_to_library or not self.config.library_path
        media_type = getattr(match, "media_type", None) if match else None
        if not media_type:
            inferred = str((item.parsed_info or {}).get("type") or "").lower()
            scan_mode = str((item.parsed_info or {}).get("scan_mode") or "").lower()
            if inferred == "episode":
                media_type = MediaType.EPISODE
            elif inferred == "scene" or scan_mode == "scenes":
                media_type = MediaType.SCENE
            else:
                media_type = MediaType.MOVIE

        if is_inplace:
            if media_type == MediaType.SCENE:
                target_name = self.formatter.format_scene_filename(self.formatter.build_scene_context(item, match, loc, people_links=people_links))
            elif media_type == MediaType.MOVIE:
                target_name = self.formatter.format_movie_filename(self.formatter.build_movie_context(item, match, loc))
            else:
                target_name = self.formatter.format_episode_filename(self.formatter.build_tv_context(item, match, loc))
            return target_name, ""

        if media_type == MediaType.SCENE:
            context = self.formatter.build_scene_context(item, match, loc, people_links=people_links)
            target_name = self.formatter.format_scene_filename(context)
            
            sub_path_parts = []
            if match and getattr(match, "is_adult", False):
                sub_path_parts.append(self.config.adult_dir_name)
                if self.config.naming_adult_subfolders_enabled:
                    sub_path_parts.append(self.config.adult_scenes_dir_name)
                
                grouping_mode = self.config.scene_grouping_mode
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
                scenes_dir = getattr(self.config, "scenes_dir_name", "Scenes")
                sub_path_parts.append(scenes_dir)
                
            if self.config.folder_create_scene_subdir:
                folder_tmpl = self.config.folder_scene_template
                if folder_tmpl:
                    scene_folder = self.formatter._render(folder_tmpl, context, is_file=False)
                    sub_path_parts.append(scene_folder)
                
            sub_path_obj = Path()
            for p in sub_path_parts:
                if p and str(p).strip() and str(p) != ".":
                    sub_path_obj = sub_path_obj / p
            target_subpath = str(sub_path_obj).replace("\\", "/")
            
        elif media_type == MediaType.MOVIE:
            context = self.formatter.build_movie_context(item, match, loc)
            target_name = self.formatter.format_movie_filename(context)
            
            sub_path_parts = []
            if match and getattr(match, "is_adult", False):
                sub_path_parts.append(self.config.adult_dir_name)
                if self.config.naming_adult_subfolders_enabled:
                    sub_path_parts.append(self.config.adult_movies_dir_name)
            else:
                if self.config.sort_by_type:
                    sub_path_parts.append(self.config.movies_dir_name)
                    
            if self.config.create_movie_subdir:
                folder_name = self.formatter.format_movie_foldername(context, match)
                sub_path_parts.append(folder_name)
                
            sub_path_obj = Path()
            for p in sub_path_parts:
                if p and str(p).strip() and str(p) != ".":
                    sub_path_obj = sub_path_obj / p
            target_subpath = str(sub_path_obj).replace("\\", "/")
            
        elif media_type in [MediaType.TV, MediaType.SEASON, MediaType.EPISODE]:
            context = self.formatter.build_tv_context(item, match, loc)
            target_name = self.formatter.format_episode_filename(context)
                
            sub_path_parts = []
            if match and getattr(match, "is_adult", False):
                sub_path_parts.append(self.config.adult_dir_name)
                if self.config.naming_adult_subfolders_enabled:
                    sub_path_parts.append(self.config.adult_tv_dir_name)
            else:
                if self.config.sort_by_type:
                    sub_path_parts.append(self.config.tv_dir_name)
                    
            if self.config.create_tv_dir:
                tv_folder = self.formatter.format_tv_foldername(context)
                sub_path_parts.append(tv_folder)
            if self.config.create_season_dir:
                season_folder = self.formatter.format_season_foldername(context)
                sub_path_parts.append(season_folder)
                
            sub_path_obj = Path()
            for p in sub_path_parts:
                if p and str(p).strip() and str(p) != ".":
                    sub_path_obj = sub_path_obj / p
            target_subpath = str(sub_path_obj).replace("\\", "/")
        else:
            target_name = getattr(item, "filename", "")
            target_subpath = ""

        target_subpath = target_subpath.replace("\\", "/")
        target_name = target_name.replace("\\", "/")
        return target_name, target_subpath

    def format_item(self, item: Any, match: Any, loc: Any, people_links: Optional[List[Any]] = None) -> RenamePreview:
        orig_path = self.formatter._get_absolute_path(item)
        target_name, target_subpath = self._get_target_name_and_subpath(item, match, loc, people_links=people_links)
        dest_root = self.config.library_path if self.config.move_to_library and self.config.library_path else os.path.dirname(orig_path)
        media_type = getattr(match, "media_type", None) if match else None
        if not media_type:
            inferred = str((item.parsed_info or {}).get("type") or "").lower()
            scan_mode = str((item.parsed_info or {}).get("scan_mode") or "").lower()
            if inferred == "episode":
                media_type = MediaType.EPISODE
            elif inferred == "scene" or scan_mode == "scenes":
                media_type = MediaType.SCENE
            else:
                media_type = MediaType.MOVIE

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
        self.formatter.resolve_collisions([preview])
        self.formatter._check_path_lengths(preview)
        return preview

    def plan_rename(self, match: Any, destination_root: str) -> RenamePreview:
        item = getattr(match, "media_item", None)
        if not item:
            raise ValueError("No media_item attached to match")
            
        loc = self.formatter._pick_localization(match, item)
        if not loc:
            raise ValueError("No localization available for rename planning")
        
        orig_path = self.formatter._get_absolute_path(item)
        media_type = getattr(match, "media_type", MediaType.MOVIE)

        is_inplace = not self.config.org_enabled or not self.config.move_to_library or not self.config.library_path
        target_name, target_subpath = self._get_target_name_and_subpath(item, match, loc)

        effective_root = destination_root
        if self.config.move_to_library and self.config.library_path:
            effective_root = self.config.library_path
        elif not destination_root:
            effective_root = os.path.dirname(orig_path)

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
                
                extra_orig_path = self.formatter._get_absolute_path(extra)
                if action == "delete":
                    main_preview.extra_previews.append(RenamePreview(
                        item_id=extra.id,
                        original_path=extra_orig_path,
                        target_name="", 
                        target_subpath="",
                        item_type="extra",
                        destination_root="",
                        action="delete",
                        extra_id=extra.id,
                        warnings=["File will be deleted according to extras settings."]
                    ))
                    continue

                extra_ctx = self.formatter.build_extra_context(extra, parent_name_no_ext)
                extra_name = self.formatter.format_extra_filename(extra_ctx)
                extra_sub = self.formatter.get_extra_subpath(extra)
                
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

        self.formatter.resolve_collisions([main_preview])
        self.formatter._check_path_lengths(main_preview)

        return main_preview
