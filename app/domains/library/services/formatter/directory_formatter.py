import logging
from typing import Dict, Any, Optional
from app.shared_kernel.enums import MediaType, ItemStatus

logger = logging.getLogger(__name__)

class DirectoryFormatter:
    """
    Submodule to format folder names for movies, collections, seasons, TV shows, and subpaths.
    """
    def __init__(self, formatter):
        self.formatter = formatter

    @property
    def config(self):
        return self.formatter.config

    def format_movie_foldername(self, context: Dict[str, Any], match: Optional[Any] = None) -> str:
        if not self.config.create_movie_subdir:
            return ""
            
        coll_val = context.get("Collection") or context.get("collection")
        if self._should_use_collection_folder(match, coll_val):
            coll_name = self.format_collection_foldername(context)
            movie_name = self.formatter._render(self.config.movie_folder, context, is_file=False)
            if coll_name and movie_name:
                return f"{coll_name}/{movie_name}"
            return movie_name or coll_name
            
        return self.formatter._render(self.config.movie_folder, context, is_file=False)

    def format_collection_foldername(self, context: Dict[str, Any]) -> str:
        tmpl = self.config.collection_folder or "{Collection}"
        return self.formatter._render(tmpl, context, is_file=False)

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

    def format_tv_foldername(self, context: Dict[str, Any]) -> str:
        if not self.config.create_tv_dir:
            return ""
        return self.formatter._render(self.config.tv_folder, context, is_file=False)

    def format_season_foldername(self, context: Dict[str, Any]) -> str:
        if not self.config.create_season_dir:
            return ""
        return self.formatter._render(self.config.season_folder, context, is_file=False)

    def format_episode_filename(self, context: Dict[str, Any]) -> str:
        return self.formatter._render(self.config.episode_file, context, is_file=True)

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
            
        name = self.formatter._render(tmpl, context, is_file=True)
        name = " ".join(name.split())
        return name

    def get_extra_subpath(self, extra) -> str:
        if self.config.extras_folder_mode == "flat":
            return ""
        return self.config.extras_subfolder_name

    def get_category_folder(self, item_type_value: str, match: Optional[Any] = None) -> str:
        if not self.config.sort_by_type:
            return ""
        if match and getattr(match, "is_adult", False):
            return self.config.adult_dir_name
        if item_type_value == "movie":
            return self.config.movies_dir_name
        if item_type_value in ["tv", "episode"]:
            return self.config.tv_dir_name
        return ""
