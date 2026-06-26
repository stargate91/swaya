from typing import Dict, Any
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.enums import Provider
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.genre_utils import split_genres as _split_genres
from app.infrastructure.scrapers.enrichment.parsers.common import _pick_trailer_key

def enrich_movie(parser, match: MetadataMatch, language: str, include_ratings: bool = True):
    details = parser.enricher._get_details_cached(int(match.external_id), "movie", language)
    if not details:
        return

    parser.update_match_common(match, details, include_ratings=include_ratings)
    match.is_adult = details.get("adult", False)
    match.release_status = details.get("status")
    match.budget = details.get("budget")
    match.revenue = details.get("revenue")

    # Collection details
    coll = details.get("belongs_to_collection")
    if coll:
        coll_id = str(coll["id"])
        collection = parser.metadata_repo.get_collection(Provider.TMDB, coll_id)
        if not collection:
            collection = parser.metadata_repo.create_collection(
                provider=Provider.TMDB,
                external_id=coll_id,
                backdrop_path=coll.get("backdrop_path")
            )
            parser.metadata_repo.flush()
        match.collection = collection

        lang_code = language.split("-", 1)[0].lower()
        loc = None
        if collection.id is not None:
            loc = parser.metadata_repo.get_collection_localization(collection.id, lang_code)
        if not loc:
            loc = parser.metadata_repo.create_collection_localization(
                collection_id=collection.id,
                locale=lang_code
            )
        loc.title = coll.get("name") or loc.title
        loc.poster_path = coll.get("poster_path") or loc.poster_path

        if loc.poster_path and not loc.local_poster_path:
            asset_prefix = f"tmdb_{collection.external_id}"
            loc.local_poster_path = parser.enricher._queue_image(loc.poster_path, "posters", asset_prefix)
        
        if collection.backdrop_path and not collection.local_backdrop_path:
            asset_prefix = f"tmdb_{collection.external_id}"
            collection.local_backdrop_path = parser.enricher._queue_image(collection.backdrop_path, "backdrops", asset_prefix)
        
    selected_backdrop_path = image_processing_service.pick_backdrop_path(details, preferred_language=language)
    if selected_backdrop_path:
        match.backdrop_path = selected_backdrop_path

    # Localization
    loc = parser.get_or_create_loc(match, language)
    loc.title = details.get("title") or details.get("original_title") or "Unknown"
    loc.overview = details.get("overview")
    loc.tagline = details.get("tagline")
    loc.poster_path = image_processing_service.pick_poster_path(details, preferred_language=language)
    loc.logo_path = image_processing_service.pick_logo_path(details, preferred_language=language)
    localized_asset_prefix = f"tmdb_movie_{match.external_id}_{language}"
    match.local_backdrop_path = parser.enricher._queue_image(
        match.backdrop_path,
        "backdrops",
        f"tmdb_movie_{match.external_id}",
    )
    loc.local_poster_path = parser.enricher._queue_image(loc.poster_path, "posters", localized_asset_prefix)
    loc.local_logo_path = parser.enricher._queue_image(loc.logo_path, "logos", localized_asset_prefix)
    loc.genres = _split_genres([g["name"] for g in details.get("genres") or []])
    loc.original_language = details.get("original_language")

    # Trailer
    loc.trailer_url = _pick_trailer_key(details, language, details.get("original_language"))
