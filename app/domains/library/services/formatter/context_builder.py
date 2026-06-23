import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import object_session
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService
from app.domains.library.services.formatter.tech_parser import TechParser

logger = logging.getLogger(__name__)



class ContextBuilder:
    """
    Orchestrates the creation of naming contexts for different media types.
    Combines technical metadata with descriptive metadata.
    """

    def __init__(self, config: Any):
        self.config = config
        self.tech_parser = TechParser()

    @staticmethod
    def _resolve_user_tag_names(item: Any, match: Any, user_id: int = 1) -> List[str]:
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

    def build_movie_context(self, item: Any, match: Any, loc: Any) -> Dict[str, Any]:
        """Builds context variables for a Movie."""
        ctx = self.tech_parser.get_tech_context(item)
        collection_name = self._resolve_collection_name(match, loc)
        
        from app.shared_kernel.enums import Provider, MovieEdition, MediaSource, MediaAudioType
        tmdb_id = ""
        if match and getattr(match, "provider", None) == Provider.TMDB:
            tmdb_id = str(match.external_id)
        
        edition_val = getattr(item, "edition", None)
        source_val = getattr(item, "source", None)
        audio_type_val = getattr(item, "audio_type", None)
        
        overrides = getattr(item, "overrides", None)
        if overrides:
            if getattr(overrides, "custom_edition", None) and overrides.custom_edition != MovieEdition.NONE:
                edition_val = overrides.custom_edition
            if getattr(overrides, "custom_source", None) and overrides.custom_source != MediaSource.NONE:
                source_val = overrides.custom_source
            if getattr(overrides, "custom_audio_type", None) and overrides.custom_audio_type != MediaAudioType.NONE:
                audio_type_val = overrides.custom_audio_type

        ctx.update({
            "Title": loc.title if loc and loc.title else "",
            "OriginalTitle": getattr(match, "original_title", "") or "",
            "Year": str(match.release_date.year) if match and match.release_date else "",
            "ReleaseDate": match.release_date.strftime("%Y-%m-%d") if match and match.release_date else "",
            "Edition": self.tech_parser.format_enum_val(edition_val),
            "Source": self.tech_parser.format_source(source_val),
            "AudioType": self.tech_parser.format_enum_val(audio_type_val),
            "Custom": self.config.custom_text,
            "ImdbId": getattr(match, "imdb_id", "") or "",
            "TmdbId": tmdb_id,
            "RatingImdb": str(match.rating_imdb) if match and getattr(match, "rating_imdb", None) else "",
            "Collection": collection_name,
            "ext": getattr(item, "extension", "") or "",
        })

        part_label, part_val, part_sep = self._build_part_info(item)
        ctx.update({"PartType": part_label, "Part": part_val, "PartSep": part_sep})
        return ctx

    def build_scene_context(self, item: Any, match: Any, loc: Any) -> Dict[str, Any]:
        """Builds context variables for an adult Scene."""
        ctx = self.tech_parser.get_tech_context(item)
        
        # 1. Resolve Studio names
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
                
        # 2. Resolve Performers (people with role ACTOR)
        performer_names = []
        from app.shared_kernel.enums import RoleType
        
        people_links = getattr(match, "people", []) or []
        actor_links = [l for l in people_links if getattr(l, "role", None) == RoleType.ACTOR]
        
        # Sort actor links
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
        else: # default: order
            actor_links.sort(key=lambda l: getattr(l, "order", 0) or 0)
            
        for link in actor_links:
            person = getattr(link, "person", None)
            if not person:
                continue
                
            # Gender filter: female=1, male=2
            gender_filter = self.config.naming_performer_gender_filter
            if gender_filter == "female" and getattr(person, "gender", None) != 1:
                continue
            if gender_filter == "male" and getattr(person, "gender", None) != 2:
                continue
                
            performer_names.append(person.name)
            
        # Performer limits check
        limit = self.config.naming_performer_limit
        if len(performer_names) > limit:
            if self.config.naming_performer_limit_keep:
                performer_names = performer_names[:limit]
            else:
                performer_names = []
                
        performers_str = self.config.naming_performer_splitchar.join(performer_names)
        
        # 3. Date formatting
        date_str = ""
        year_str = ""
        if match and match.release_date:
            date_format = self.config.scene_date_format or "%Y-%m-%d"
            try:
                date_str = match.release_date.strftime(date_format)
            except Exception:
                date_str = match.release_date.strftime("%Y-%m-%d")
            year_str = str(match.release_date.year)
            
        title_value = loc.title if loc and loc.title else (getattr(match, "original_title", "") or "")
        if self.config.scene_prevent_title_performer and performers_str and title_value:
            normalized_title = title_value.strip()
            for performer_name in performer_names:
                normalized_title = re.sub(
                    rf"^\s*{re.escape(performer_name)}\s*[-:|]?\s*",
                    "",
                    normalized_title,
                    flags=re.IGNORECASE,
                )
            title_value = normalized_title or title_value

        # 4. Tags
        tags_list = self._resolve_user_tag_names(item, match)
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
        
        ctx.update({
            "Title": title_value,
            "title": title_value,
            "OriginalTitle": getattr(match, "original_title", "") or "",
            "Date": date_str,
            "date": date_str,
            "Year": year_str,
            "year": year_str,
            "Studio": studio_name,
            "studio": studio_name,
            "ParentStudio": parent_studio_name,
            "parent_studio": parent_studio_name,
            "StudioFamily": studio_family_name,
            "studio_family": studio_family_name,
            "Performers": performers_str,
            "performers": performers_str,
            "Performer": performers_str,
            "performer": performers_str,
            "RatingPorndb": str(match.rating_porndb) if match and getattr(match, "rating_porndb", None) is not None else "",
            "rating_porndb": str(match.rating_porndb) if match and getattr(match, "rating_porndb", None) is not None else "",
            "Tags": tags_str,
            "tags": tags_str,
            "Custom": self.config.custom_text,
            "ext": getattr(item, "extension", "") or "",
        })
        
        part_label, part_val, part_sep = self._build_part_info(item)
        ctx.update({"PartType": part_label, "Part": part_val, "PartSep": part_sep})
        return ctx

    def build_tv_context(self, item: Any, match: Any, loc: Any, children: List[Any] = None) -> Dict[str, Any]:
        """Builds context variables for TV Shows, Seasons, and Episodes."""
        ctx = self.tech_parser.get_tech_context(item)
        if children:
            mixed_res = self.tech_parser.calculate_mixed_resolution(children)
            ctx["Resolution"] = mixed_res
            ctx["resolution"] = mixed_res

        # Safely resolve titles using the new hierarchy schema
        from app.shared_kernel.enums import MediaType
        
        locale = getattr(loc, "locale", DEFAULT_FALLBACK_LANGUAGE) if loc else DEFAULT_FALLBACK_LANGUAGE
        
        tv_match = None
        season_match = None
        
        current = match
        while current:
            if getattr(current, "media_type", None) == MediaType.SEASON:
                season_match = current
            elif getattr(current, "media_type", None) == MediaType.TV:
                tv_match = current
                break
            parent = getattr(current, "parent", None)
            if not parent and getattr(current, "parent_id", None) is not None:
                session = object_session(current)
                if session:
                    from app.domains.metadata.models import MetadataMatch
                    parent = session.query(MetadataMatch).filter(MetadataMatch.id == current.parent_id).first()
            current = parent

        if match and getattr(match, "media_type", None) == MediaType.EPISODE:
            session = object_session(match)
            if session:
                from app.domains.metadata.models import MetadataMatch
                if not tv_match and getattr(match, "external_id", None):
                    tv_match = session.query(MetadataMatch).filter(
                        MetadataMatch.provider == match.provider,
                        MetadataMatch.external_id == match.external_id,
                        MetadataMatch.media_type == MediaType.TV
                    ).first()
                if tv_match and not season_match and getattr(match, "season_number", None) is not None:
                    season_match = session.query(MetadataMatch).filter(
                        MetadataMatch.provider == match.provider,
                        MetadataMatch.media_type == MediaType.SEASON,
                        MetadataMatch.season_number == match.season_number
                    ).filter(
                        (MetadataMatch.parent_id == tv_match.id) | (MetadataMatch.external_id.like(f"{tv_match.external_id}-%"))
                    ).first()

        def get_loc(m):
            if not m:
                return None
            for l in getattr(m, "localizations", []):
                if l.locale == locale:
                    return l
            if getattr(m, "localizations", None):
                return m.localizations[0]
            return None

        tv_loc = get_loc(tv_match) if tv_match else None
        season_loc = get_loc(season_match) if season_match else None
        
        # If we didn't find them via parent traversal, but loc is provided and match fits the type:
        if match:
            if match.media_type == MediaType.TV:
                tv_match = match
                tv_loc = loc
            elif match.media_type == MediaType.SEASON:
                season_match = match
                season_loc = loc
                if not tv_match and match.parent:
                    tv_match = match.parent
                    tv_loc = get_loc(tv_match)
            elif match.media_type == MediaType.EPISODE:
                # loc is the episode localization
                pass

        first_air_date, last_air_date = self._resolve_air_dates(tv_match or match)
        first_air_year = str(first_air_date.year) if first_air_date else ""
        last_air_year = str(last_air_date.year) if last_air_date else ""
        if first_air_year and last_air_year:
            year_range = first_air_year if first_air_year == last_air_year else f"{first_air_year}-{last_air_year}"
        elif first_air_year:
            year_range = f"{first_air_year}-"
        else:
            year_range = ""

        tv_title = ""
        tv_orig_title = ""
        season_number = ""
        season_title = ""
        episode_number = ""
        episode_title = ""
        tv_tmdb_id = ""

        if tv_match:
            tv_tmdb_id = str(getattr(tv_match, "tmdb_id", None) or getattr(tv_match, "external_id", "") or "")
            tv_orig_title = getattr(tv_match, "original_title", "") or ""
        if tv_loc:
            tv_title = tv_loc.title
            
        parsed_info = getattr(item, "parsed_info", None) or {}
        custom_season = parsed_info.get("season")
        custom_episode = parsed_info.get("episode")

        if custom_season is not None and str(custom_season).strip() != "":
            season_number = self._format_number(custom_season)
        elif season_match:
            season_number = self._format_number(getattr(season_match, "season_number", None))
            
        if season_match and season_loc:
            season_title = season_loc.title
                
        if custom_episode is not None and str(custom_episode).strip() != "":
            episode_number = self._format_number(custom_episode)
            
            # Check if active match is already this episode
            match_ep = getattr(match, "episode_number", None) if match else None
            match_se = getattr(match, "season_number", None) if match else None
            is_same_episode = False
            if match and getattr(match, "media_type", None) == MediaType.EPISODE:
                try:
                    se_matches = (custom_season is None or str(custom_season).strip() == "" or int(match_se) == int(custom_season))
                    ep_matches = (int(match_ep) == int(custom_episode))
                    if se_matches and ep_matches:
                        is_same_episode = True
                except (ValueError, TypeError):
                    is_same_episode = (str(match_se) == str(custom_season) and str(match_ep) == str(custom_episode))
            
            if is_same_episode and loc:
                episode_title = getattr(loc, "title", "") or ""
            else:
                # Try to lookup correct episode title in the database
                if tv_match:
                    session = object_session(tv_match)
                    if session:
                        from app.domains.metadata.models import MetadataMatch
                        try:
                            target_season_num = int(custom_season) if custom_season is not None and str(custom_season).isdigit() else (getattr(season_match, "season_number", None) or getattr(match, "season_number", None))
                            target_ep_num = int(custom_episode) if str(custom_episode).isdigit() else None
                            
                            if target_ep_num is not None:
                                seasons_ids_query = session.query(MetadataMatch.id).filter(
                                    MetadataMatch.parent_id == tv_match.id,
                                    MetadataMatch.media_type == MediaType.SEASON
                                )
                                if target_season_num is not None:
                                    seasons_ids_query = seasons_ids_query.filter(MetadataMatch.season_number == target_season_num)
                                season_ids = [r[0] for r in seasons_ids_query.all()]
                                
                                if season_ids:
                                    ep_matches = session.query(MetadataMatch).filter(
                                        MetadataMatch.parent_id.in_(season_ids),
                                        MetadataMatch.media_type == MediaType.EPISODE
                                    ).all()
                                    target_ep_match = None
                                    for ep_m in ep_matches:
                                        ep_num_val = getattr(ep_m, "episode_number", None)
                                        if ep_num_val == target_ep_num or ep_num_val == str(target_ep_num) or (isinstance(ep_num_val, list) and target_ep_num in ep_num_val):
                                            target_ep_match = ep_m
                                            break
                                    
                                    if target_ep_match:
                                        target_loc = None
                                        for l in getattr(target_ep_match, "localizations", []):
                                            if l.locale == locale:
                                                target_loc = l
                                                break
                                        if not target_loc and getattr(target_ep_match, "localizations", None):
                                            target_loc = target_ep_match.localizations[0]
                                        if target_loc:
                                            episode_title = target_loc.title
                            if not episode_title and loc:
                                episode_title = getattr(loc, "title", "") or ""
                        except Exception as e:
                            logger.error(f"Error resolving override episode title: {e}")
                            if loc:
                                episode_title = getattr(loc, "title", "") or ""
        elif match and match.media_type == MediaType.EPISODE:
            episode_number = self._format_number(getattr(match, "episode_number", None))
            if loc:
                episode_title = loc.title

        # Backwards compatibility / defaults
        if not tv_title and loc and match and match.media_type == MediaType.TV:
            tv_title = loc.title
        if not tv_tmdb_id and match:
            tv_tmdb_id = str(getattr(match, "tmdb_id", "") or "")

        # Fallbacks for season and episode if not resolved via parent matches
        if not season_number and match and getattr(match, "season_number", None) is not None:
            season_number = self._format_number(match.season_number)
        if not episode_number and match and getattr(match, "episode_number", None) is not None:
            episode_number = self._format_number(match.episode_number)

        edition_val = getattr(item, "edition", None)
        source_val = getattr(item, "source", None)
        audio_type_val = getattr(item, "audio_type", None)
        
        from app.shared_kernel.enums import MovieEdition, MediaSource, MediaAudioType
        overrides = getattr(item, "overrides", None)
        if overrides:
            if getattr(overrides, "custom_edition", None) and overrides.custom_edition != MovieEdition.NONE:
                edition_val = overrides.custom_edition
            if getattr(overrides, "custom_source", None) and overrides.custom_source != MediaSource.NONE:
                source_val = overrides.custom_source
            if getattr(overrides, "custom_audio_type", None) and overrides.custom_audio_type != MediaAudioType.NONE:
                audio_type_val = overrides.custom_audio_type

        ctx.update({
            "TvTitle": tv_title,
            "ShowTitle": tv_title,
            "TvOriginalTitle": tv_orig_title,
            "ShowOriginalTitle": tv_orig_title,
            "TvTmdbId": tv_tmdb_id,
            "FirstAirDate": first_air_date.strftime("%Y-%m-%d") if first_air_date else "",
            "FirstAirYear": first_air_year,
            "LastAirDate": last_air_date.strftime("%Y-%m-%d") if last_air_date else "",
            "LastAirYear": last_air_year,
            "YearRange": year_range,
            
            "SeasonNumber": season_number,
            "Season": season_number,
            "SeasonName": season_title,
            
            "EpisodeNumber": episode_number,
            "Episode": episode_number,
            "EpisodeTitle": episode_title,
            
            "Edition": self.tech_parser.format_enum_val(edition_val),
            "Source": self.tech_parser.format_source(source_val),
            "AudioType": self.tech_parser.format_enum_val(audio_type_val),
            
            "Custom": self.config.custom_text,
            "ext": getattr(item, "extension", "") or "",
        })

        part_label, part_val, part_sep = self._build_part_info(item)
        ctx.update({"PartType": part_label, "Part": part_val, "PartSep": part_sep})
        return ctx

    def build_extra_context(self, extra: Any, parent_formatted_name: str) -> Dict[str, Any]:
        """Builds context variables for Extra files."""
        sub_cat = extra.subtype.value.replace("_", " ").title() if getattr(extra, "subtype", None) else ""
        category = extra.category.value if hasattr(extra.category, "value") else str(extra.category or "")
        if category.lower() == "metadata" and sub_cat.lower() == (extra.extension or "").lower().strip("."):
            sub_cat = ""

        return {
            "ParentName": parent_formatted_name,
            "Category": category,
            "category": category,
            "SubCategory": sub_cat,
            "sub_category": sub_cat,
            "Language": extra.language.upper() if getattr(extra, "language", None) else "",
            "language": extra.language.upper() if getattr(extra, "language", None) else "",
            "ext": extra.extension or "",
            "custom": self.config.custom_text
        }

    def _build_part_info(self, item: Any) -> (str, str, str):
        """Calculates part-related naming components."""
        label = "cd"
        val = ""
        sep = " "
        
        part_num = getattr(item, "part_number", None)
        if part_num is None:
            part_num = getattr(item, "part", None)

        if part_num is not None:
            val = str(part_num)
                
        return label, val, sep

    def _format_number(self, num: Any, prefix_multi: str = "") -> str:
        """Formats season/episode numbers with zero padding if enabled."""
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
                    formatted_n = self._format_single_num(n)
                    if prefix_multi:
                        parts.append(f"{prefix_multi}{formatted_n}")
                    elif i > 0:
                        parts.append(f"{prefix_multi}{formatted_n}")
                    else:
                        parts.append(formatted_n)
                return "-".join(parts)
            return self._format_single_num(num)
        except:
            return str(num)

    def _resolve_collection_name(self, match: Any, loc: Any) -> str:
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

    def _resolve_air_dates(self, match: Any) -> tuple[Optional[datetime], Optional[datetime]]:
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

    def _format_single_num(self, n: Any) -> str:
        if self.config.zero_pad:
            return f"{int(n):02d}"
        return str(n)
