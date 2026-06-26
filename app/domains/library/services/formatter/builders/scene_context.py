import re
from typing import List, Dict, Any, Optional

def build_scene_context(
    item: Any,
    match: Any,
    loc: Any,
    tech_parser: Any,
    name_parser: Any,
    config: Any,
    people_links: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """Builds context variables for an adult Scene."""
    ctx = tech_parser.get_tech_context(item)
    
    studio_name, parent_studio_name, studio_family_name = name_parser.resolve_studios(match)
    performers_str, performer_names = name_parser.resolve_performers(match, people_links)
    
    # Date formatting
    date_str = ""
    year_str = ""
    if match and match.release_date:
        date_format = config.scene_date_format or "%Y-%m-%d"
        try:
            date_str = match.release_date.strftime(date_format)
        except Exception:
            date_str = match.release_date.strftime("%Y-%m-%d")
        year_str = str(match.release_date.year)
        
    title_value = loc.title if loc and loc.title else (getattr(match, "original_title", "") or "")
    if config.scene_prevent_title_performer and performers_str and title_value:
        normalized_title = title_value.strip()
        for performer_name in performer_names:
            normalized_title = re.sub(
                rf"^\s*{re.escape(performer_name)}\s*[-:|]?\s*",
                "",
                normalized_title,
                flags=re.IGNORECASE,
            )
        title_value = normalized_title or title_value

    tags_str = name_parser.resolve_tags(item, match)
    
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
        "Edition": tech_parser.format_enum_val(edition_val),
        "Source": tech_parser.format_source(source_val),
        "AudioType": tech_parser.format_enum_val(audio_type_val),
        "Custom": config.custom_text,
        "ext": getattr(item, "extension", "") or "",
    })
    
    part_label, part_val, part_sep = name_parser.build_part_info(item)
    ctx.update({"PartType": part_label, "Part": part_val, "PartSep": part_sep})
    return ctx
