import os
from typing import Callable, Optional, Dict, Any, List
from pathlib import Path

from app.shared_kernel.enums import MediaType, ItemStatus
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService
from .config import Casing, Separator, ExtraOrg, FormatterConfig
from .models import RenamePreview
from .context_builder import ContextBuilder
from .template_renderer import TemplateRenderer
from .path_resolver import PathResolver

from app.domains.library.services.formatter.directory_formatter import DirectoryFormatter
from app.domains.library.services.formatter.plan_generator import PlanGenerator

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

        # Subcomponent delegation
        self.directory_formatter = DirectoryFormatter(self)
        self.plan_generator = PlanGenerator(self)

    def _get_absolute_path(self, item_or_extra: Any) -> str:
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

        if not preferred_locale:
            preferred_locale = self.config.default_target_language

        preferred_locale = preferred_locale or DEFAULT_FALLBACK_LANGUAGE
        return LanguageService.get_best_localization(localizations, preferred_locale)

    def _get_target_name_and_subpath(self, item: Any, match: Any, loc: Any, people_links: Optional[List[Any]] = None) -> tuple[str, str]:
        return self.plan_generator._get_target_name_and_subpath(item, match, loc, people_links=people_links)

    def format_item(self, item: Any, match: Any, loc: Any, people_links: Optional[List[Any]] = None) -> RenamePreview:
        return self.plan_generator.format_item(item, match, loc, people_links=people_links)

    def plan_rename(self, match: Any, destination_root: str) -> RenamePreview:
        return self.plan_generator.plan_rename(match, destination_root)

    def _check_path_lengths(self, preview: RenamePreview):
        self.path_resolver.check_path_lengths(preview)

    def resolve_collisions(self, previews: List[RenamePreview]) -> List[RenamePreview]:
        return self.path_resolver.resolve_collisions(previews)

    # =========================================================================
    # Delegated Directory Formatting API
    # =========================================================================

    def format_movie_filename(self, context: Dict[str, Any]) -> str:
        return self._render(self.config.movie_file, context, is_file=True)

    def format_scene_filename(self, context: Dict[str, Any]) -> str:
        return self._render(self.config.scene_file, context, is_file=True)

    def format_movie_foldername(self, context: Dict[str, Any], match: Optional[Any] = None) -> str:
        return self.directory_formatter.format_movie_foldername(context, match)

    def format_collection_foldername(self, context: Dict[str, Any]) -> str:
        return self.directory_formatter.format_collection_foldername(context)

    def _should_use_collection_folder(self, match: Optional[Any], collection_value: Any) -> bool:
        return self.directory_formatter._should_use_collection_folder(match, collection_value)

    def _count_owned_collection_movies(self, match: Optional[Any]) -> int:
        return self.directory_formatter._count_owned_collection_movies(match)

    def _get_collection_total_parts(self, match: Optional[Any]) -> int:
        return self.directory_formatter._get_collection_total_parts(match)

    def format_tv_foldername(self, context: Dict[str, Any]) -> str:
        return self.directory_formatter.format_tv_foldername(context)

    def format_season_foldername(self, context: Dict[str, Any]) -> str:
        return self.directory_formatter.format_season_foldername(context)

    def format_episode_filename(self, context: Dict[str, Any]) -> str:
        return self.directory_formatter.format_episode_filename(context)

    def format_extra_filename(self, context: Dict[str, Any]) -> str:
        return self.directory_formatter.format_extra_filename(context)

    def get_extra_subpath(self, extra) -> str:
        return self.directory_formatter.get_extra_subpath(extra)

    def get_category_folder(self, item_type_value: str, match: Optional[Any] = None) -> str:
        return self.directory_formatter.get_category_folder(item_type_value, match)

    # =========================================================================
    # Context Builders (Delegated to ContextBuilder)
    # =========================================================================

    def build_movie_context(self, item, match, loc) -> Dict[str, Any]:
        return self.context_builder.build_movie_context(item, match, loc)

    def build_scene_context(self, item, match, loc, people_links: Optional[List[Any]] = None) -> Dict[str, Any]:
        return self.context_builder.build_scene_context(item, match, loc, people_links=people_links)

    def build_tv_context(self, item, match, loc, children: List[Any] = None) -> Dict[str, Any]:
        return self.context_builder.build_tv_context(item, match, loc, children)

    def build_extra_context(self, extra, parent_formatted_name: str) -> Dict[str, Any]:
        return self.context_builder.build_extra_context(extra, parent_formatted_name)

    # =========================================================================
    # Helper Functions (Delegated to TemplateRenderer)
    # =========================================================================

    def _render(self, template: str, context: Dict[str, Any], is_file: bool = True) -> str:
        return self.renderer.render(template, context, is_file)

    def apply_casing(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.renderer.apply_casing(text, context)

    def apply_separator(self, text: str) -> str:
        return self.renderer.apply_separator(text)

    def format_number(self, num, width: int = 2) -> str:
        return self.renderer.format_number(num, width)

    def sanitize(self, text: str) -> str:
        return self.renderer.sanitize(text)
