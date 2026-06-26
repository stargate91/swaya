import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import object_session
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

def build_tv_context(
    item: Any,
    match: Any,
    loc: Any,
    tech_parser: Any,
    name_parser: Any,
    config: Any,
    children: List[Any] = None
) -> Dict[str, Any]:
    """Builds context variables for TV Shows, Seasons, and Episodes."""
    ctx = tech_parser.get_tech_context(item)
    if children:
        mixed_res = tech_parser.calculate_mixed_resolution(children)
        ctx["Resolution"] = mixed_res
        ctx["resolution"] = mixed_res

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
            pass

    first_air_date, last_air_date = name_parser.resolve_air_dates(tv_match or match)
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
    if not tv_title:
        tv_title = parsed_info.get("show_name") or parsed_info.get("show") or parsed_info.get("title")
        if not tv_title:
            fn_data = parsed_info.get("fn") or {}
            it_data = parsed_info.get("it") or {}
            fd_data = parsed_info.get("fd") or {}
            tv_title = fn_data.get("show_name") or fn_data.get("show") or it_data.get("show_name") or it_data.get("show") or fd_data.get("show_name") or fd_data.get("show") or getattr(item, "filename", "").rsplit(".", 1)[0]
    if not tv_orig_title:
        tv_orig_title = tv_title
    custom_season = parsed_info.get("season")
    custom_episode = parsed_info.get("episode")

    if custom_season is not None and str(custom_season).strip() != "":
        season_number = name_parser.format_number(custom_season)
    elif season_match:
        season_number = name_parser.format_number(getattr(season_match, "season_number", None))
        
    if season_match and season_loc:
        season_title = season_loc.title
            
    if custom_episode is not None and str(custom_episode).strip() != "":
        episode_number = name_parser.format_number(custom_episode)
        
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
        episode_number = name_parser.format_number(getattr(match, "episode_number", None))
        if loc:
            episode_title = loc.title

    if not tv_title and loc and match and match.media_type == MediaType.TV:
        tv_title = loc.title
    if not tv_tmdb_id and match:
        tv_tmdb_id = str(getattr(match, "tmdb_id", "") or "")

    if not season_number and match and getattr(match, "season_number", None) is not None:
        season_number = name_parser.format_number(match.season_number)
    if not episode_number and match and getattr(match, "episode_number", None) is not None:
        episode_number = name_parser.format_number(match.episode_number)

    edition_val = getattr(item, "edition", None)
    source_val = getattr(item, "source", None)
    audio_type_val = getattr(item, "audio_type", None)
    
    from app.shared_kernel.enums import MovieEdition, MediaSource, MediaAudioType
    if getattr(item, "custom_edition", None) and item.custom_edition != MovieEdition.NONE:
        edition_val = item.custom_edition
    if getattr(item, "custom_source", None) and item.custom_source != MediaSource.NONE:
        source_val = item.custom_source
    if getattr(item, "custom_audio_type", None) and item.custom_audio_type != MediaAudioType.NONE:
        audio_type_val = item.custom_audio_type

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
        
        "Edition": tech_parser.format_enum_val(edition_val),
        "Source": tech_parser.format_source(source_val),
        "AudioType": tech_parser.format_enum_val(audio_type_val),
        
        "Custom": config.custom_text,
        "ext": getattr(item, "extension", "") or "",
    })

    part_label, part_val, part_sep = name_parser.build_part_info(item)
    ctx.update({"PartType": part_label, "Part": part_val, "PartSep": part_sep})
    return ctx
