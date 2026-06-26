from typing import Dict, Any

def build_movie_context(
    item: Any,
    match: Any,
    loc: Any,
    tech_parser: Any,
    name_parser: Any,
    config: Any
) -> Dict[str, Any]:
    """Builds context variables for a Movie."""
    ctx = tech_parser.get_tech_context(item)
    collection_name = name_parser.resolve_collection_name(match, loc)
    
    from app.shared_kernel.enums import Provider, MovieEdition, MediaSource, MediaAudioType
    tmdb_id = ""
    if match and getattr(match, "provider", None) == Provider.TMDB:
        tmdb_id = str(match.external_id)
    
    edition_val = getattr(item, "edition", None)
    source_val = getattr(item, "source", None)
    audio_type_val = getattr(item, "audio_type", None)
    
    if getattr(item, "custom_edition", None) and item.custom_edition != MovieEdition.NONE:
        edition_val = item.custom_edition
    if getattr(item, "custom_source", None) and item.custom_source != MediaSource.NONE:
        source_val = item.custom_source
    if getattr(item, "custom_audio_type", None) and item.custom_audio_type != MediaAudioType.NONE:
        audio_type_val = item.custom_audio_type

    parsed_info = getattr(item, "parsed_info", None) or {}
    title_val = loc.title if loc and loc.title else ""
    if not title_val:
        title_val = parsed_info.get("title") or parsed_info.get("name") or getattr(item, "filename", "").rsplit(".", 1)[0]
        
    orig_title_val = getattr(match, "original_title", "") or ""
    if not orig_title_val:
        orig_title_val = title_val

    ctx.update({
        "Title": title_val,
        "OriginalTitle": orig_title_val,
        "Year": str(match.release_date.year) if match and match.release_date else "",
        "ReleaseDate": match.release_date.strftime("%Y-%m-%d") if match and match.release_date else "",
        "Edition": tech_parser.format_enum_val(edition_val),
        "Source": tech_parser.format_source(source_val),
        "AudioType": tech_parser.format_enum_val(audio_type_val),
        "Custom": config.custom_text,
        "ImdbId": getattr(match, "imdb_id", "") or "",
        "TmdbId": tmdb_id,
        "RatingImdb": str(match.rating_imdb) if match and getattr(match, "rating_imdb", None) else "",
        "Collection": collection_name,
        "ext": getattr(item, "extension", "") or "",
    })

    part_label, part_val, part_sep = name_parser.build_part_info(item)
    ctx.update({"PartType": part_label, "Part": part_val, "PartSep": part_sep})
    return ctx
