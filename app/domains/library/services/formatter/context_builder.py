import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.domains.library.services.formatter.tech_parser import TechParser
from app.domains.library.services.formatter.name_parser import NameParser
from app.domains.library.services.formatter.builders import (
    build_movie_context,
    build_scene_context,
    build_tv_context,
    build_extra_context,
)

logger = logging.getLogger(__name__)

class ContextBuilder:
    """
    Orchestrates the creation of naming contexts for different media types.
    Delegates to specific context builders.
    """

    def __init__(self, config: Any):
        self.config = config
        self.tech_parser = TechParser()
        self.name_parser = NameParser(config)

    @staticmethod
    def _resolve_user_tag_names(item: Any, match: Any, user_id: int = 1) -> List[str]:
        return NameParser.resolve_user_tag_names(item, match, user_id)

    def build_movie_context(self, item: Any, match: Any, loc: Any) -> Dict[str, Any]:
        """Builds context variables for a Movie."""
        return build_movie_context(
            item=item,
            match=match,
            loc=loc,
            tech_parser=self.tech_parser,
            name_parser=self.name_parser,
            config=self.config,
        )

    def build_scene_context(self, item: Any, match: Any, loc: Any, people_links: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Builds context variables for an adult Scene."""
        return build_scene_context(
            item=item,
            match=match,
            loc=loc,
            tech_parser=self.tech_parser,
            name_parser=self.name_parser,
            config=self.config,
            people_links=people_links,
        )

    def build_tv_context(self, item: Any, match: Any, loc: Any, children: List[Any] = None) -> Dict[str, Any]:
        """Builds context variables for TV Shows, Seasons, and Episodes."""
        return build_tv_context(
            item=item,
            match=match,
            loc=loc,
            tech_parser=self.tech_parser,
            name_parser=self.name_parser,
            config=self.config,
            children=children,
        )

    def build_extra_context(self, extra: Any, parent_formatted_name: str) -> Dict[str, Any]:
        """Builds context variables for Extra files."""
        return build_extra_context(
            extra=extra,
            parent_formatted_name=parent_formatted_name,
            config=self.config,
        )

    def _build_part_info(self, item: Any) -> (str, str, str):
        return self.name_parser.build_part_info(item)

    def _format_number(self, num: Any, prefix_multi: str = "") -> str:
        return self.name_parser.format_number(num, prefix_multi)

    def _resolve_collection_name(self, match: Any, loc: Any) -> str:
        return self.name_parser.resolve_collection_name(match, loc)

    def _resolve_air_dates(self, match: Any) -> tuple[Optional[datetime], Optional[datetime]]:
        return self.name_parser.resolve_air_dates(match)

    def _format_single_num(self, n: Any) -> str:
        return self.name_parser.format_single_num(n)
