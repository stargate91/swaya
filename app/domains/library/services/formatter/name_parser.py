import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import object_session
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService

logger = logging.getLogger(__name__)

class NameParser:
    def __init__(self, config: Any):
        self.config = config

    @staticmethod
    def resolve_user_tag_names(item: Any, match: Any, user_id: int = 1) -> List[str]:
        tag_names: Dict[str, str] = {}

        for entity in (item, match):
            overrides = getattr(entity, "overrides", None)
            if overrides is None:
                continue
            if not isinstance(overrides, (list, tuple, set)):
                overrides = [overrides]

            for override in overrides:
                if getattr(override, "user_id", None) != user_id:
                    continue
                for tag in getattr(override, "tags", None) or []:
                    name = str(getattr(tag, "name", "") or "").strip()
                    if name:
                        tag_names.setdefault(name.casefold(), name)

        return list(tag_names.values())

    def resolve_collection_name(self, match: Any, loc: Any) -> str:
        collection = getattr(match, "collection", None)
        localizations = getattr(collection, "localizations", None) if collection and hasattr(collection, "localizations") else None
        if localizations:
            locale = getattr(loc, "locale", DEFAULT_FALLBACK_LANGUAGE) or DEFAULT_FALLBACK_LANGUAGE
            localized = LanguageService.get_best_localization(localizations, locale)
            if localized and getattr(localized, "title", None):
                return localized.title
            if localized and getattr(localized, "name", None):
                return localized.name
        return getattr(collection, "name", None) or getattr(match, "collection_name", None) or ""

    def build_part_info(self, item: Any) -> tuple[str, str, str]:
        label = "cd"
        val = ""
        sep = " "
        
        part_num = getattr(item, "part_number", None)
        if part_num is None:
            part_num = getattr(item, "part", None)

        if part_num is not None:
            val = str(part_num)
                
        return label, val, sep

    def resolve_air_dates(self, match: Any) -> tuple[Optional[datetime], Optional[datetime]]:
        first_air_date = getattr(match, "first_air_date", None) or getattr(match, "release_date", None)
        last_air_date = getattr(match, "last_air_date", None)
        if first_air_date and last_air_date:
            return first_air_date, last_air_date

        parent = getattr(match, "parent", None)
        if parent:
            if not first_air_date:
                first_air_date = getattr(parent, "first_air_date", None) or getattr(parent, "release_date", None)
            if not last_air_date:
                last_air_date = getattr(parent, "last_air_date", None)

        return first_air_date, last_air_date

    def format_single_num(self, n: Any) -> str:
        if self.config.zero_pad:
            return f"{int(n):02d}"
        return str(n)

    def format_number(self, num: Any, prefix_multi: str = "") -> str:
        if num is None or str(num).strip() == "": return ""
        import json
        
        if isinstance(num, str):
            num = num.strip()
            if num.startswith("[") and num.endswith("]"):
                try:
                    num = json.loads(num)
                except:
                    pass
            elif "," in num:
                num = [n.strip() for n in num.split(",")]

        try:
            if isinstance(num, list) and len(num) > 0:
                parts = []
                for i, n in enumerate(num):
                    formatted_n = self.format_single_num(n)
                    if prefix_multi:
                        parts.append(f"{prefix_multi}{formatted_n}")
                    elif i > 0:
                        parts.append(f"{prefix_multi}{formatted_n}")
                    else:
                        parts.append(formatted_n)
                return "-".join(parts)
            return self.format_single_num(num)
        except:
            return str(num)

    def resolve_studios(self, match: Any) -> tuple[str, str, str]:
        studio_name = ""
        parent_studio_name = ""
        studio_family_name = ""
        
        studios = getattr(match, "studios", []) or []
        if studios:
            primary_studio = studios[0]
            studio_name = primary_studio.name
            parent_studio = getattr(primary_studio, "parent_studio", None)
            if parent_studio:
                parent_studio_name = parent_studio.name
                studio_family_name = parent_studio.name
            else:
                studio_family_name = primary_studio.name
                
            if self.config.naming_squeeze_studio_names:
                studio_name = studio_name.replace(" ", "")
                parent_studio_name = parent_studio_name.replace(" ", "")
                studio_family_name = studio_family_name.replace(" ", "")
        return studio_name, parent_studio_name, studio_family_name

    def resolve_performers(self, match: Any, people_links: Optional[List[Any]] = None) -> str:
        performer_names = []
        from app.shared_kernel.enums import RoleType
        
        if people_links is None and match:
            if hasattr(match, "people_links") and match.people_links is not None:
                people_links = match.people_links
            else:
                from sqlalchemy import inspect
                insp = inspect(match)
                if insp.session:
                    from app.domains.people.models import MediaPersonLink
                    from sqlalchemy.orm import joinedload
                    people_links = insp.session.query(MediaPersonLink).options(
                        joinedload(MediaPersonLink.person)
                    ).filter(MediaPersonLink.match_id == match.id).all()
        
        people_links = people_links or []
        actor_links = [l for l in people_links if getattr(l, "role", None) == RoleType.ACTOR]
        
        sort_mode = self.config.naming_performer_sort
        if sort_mode == "popularity":
            actor_links.sort(
                key=lambda l: (
                    l.person.rating_porndb
                    if getattr(l.person, "rating_porndb", None) is not None
                    else getattr(l.person, "popularity", 0) or 0
                ),
                reverse=True,
            )
        elif sort_mode == "name":
            actor_links.sort(key=lambda l: getattr(l.person, "name", "").lower())
        else:
            actor_links.sort(key=lambda l: getattr(l, "order", 0) or 0)
            
        for link in actor_links:
            person = getattr(link, "person", None)
            if not person:
                continue
                
            gender_filter = self.config.naming_performer_gender_filter
            if gender_filter == "female" and getattr(person, "gender", None) == 2:
                continue
            if gender_filter == "male" and getattr(person, "gender", None) == 1:
                continue
                
            performer_names.append(person.name)
            
        limit = self.config.naming_performer_limit
        if len(performer_names) > limit:
            if self.config.naming_performer_limit_keep:
                performer_names = performer_names[:limit]
            else:
                performer_names = []
                
        performers_str = self.config.naming_performer_splitchar.join(performer_names)
        return performers_str, performer_names

    def resolve_tags(self, item: Any, match: Any) -> str:
        tags_list = self.resolve_user_tag_names(item, match)
        blacklist = {
            tag.strip().casefold()
            for tag in str(self.config.scene_tag_blacklist or "").split(",")
            if tag.strip()
        }
        if blacklist:
            tags_list = [tag for tag in tags_list if tag.casefold() not in blacklist]
        tags_list = sorted(dict.fromkeys(tags_list), key=str.casefold)
        tags_list = tags_list[:self.config.scene_tag_limit] if self.config.scene_tag_limit > 0 else []
        tags_str = (self.config.scene_tag_separator or " ").join(tags_list)
        return tags_str
