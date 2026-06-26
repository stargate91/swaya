import logging
from datetime import datetime
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.enums import MediaType
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.genre_utils import split_genres as _split_genres
from app.infrastructure.scrapers.enrichment.parsers.common import _pick_trailer_key, tv_enrich_lock

logger = logging.getLogger(__name__)

def enrich_tv(parser, match: MetadataMatch, language: str, include_ratings: bool = True):
    # A. TV SHOW LEVEL
    tv_details = parser.enricher._get_details_cached(int(match.external_id), "tv", language)
    if not tv_details:
        return

    with tv_enrich_lock:
        tv_match = parser.metadata_repo.get_tv_match(match.provider, match.external_id)
        if not tv_match:
            try:
                with parser.db.begin_nested():
                    tv_match = parser.metadata_repo.create_match(
                        provider=match.provider,
                        external_id=match.external_id,
                        media_type=MediaType.TV,
                        media_item_id=None
                    )
                    tv_match.confidence_score = 1.0
                    parser.metadata_repo.flush()
            except Exception:
                tv_match = parser.metadata_repo.get_tv_match(match.provider, match.external_id)

        parser.update_match_common(tv_match, tv_details, include_ratings=include_ratings)
        tv_match.is_adult = tv_details.get("adult", False)
        tv_match.release_status = tv_details.get("status")
        tv_match.tv_type = tv_details.get("type")
        tv_match.number_of_seasons = tv_details.get("number_of_seasons")
        tv_match.number_of_episodes = tv_details.get("number_of_episodes")

        tv_first_air_date = tv_details.get("first_air_date")
        if tv_first_air_date:
            try:
                tv_match.first_air_date = datetime.strptime(tv_first_air_date, "%Y-%m-%d")
            except:
                pass
        tv_last_air_date = tv_details.get("last_air_date")
        if tv_last_air_date:
            try:
                tv_match.last_air_date = datetime.strptime(tv_last_air_date, "%Y-%m-%d")
            except:
                pass

        selected_backdrop_path = image_processing_service.pick_backdrop_path(tv_details, preferred_language=language)
        if selected_backdrop_path:
            tv_match.backdrop_path = selected_backdrop_path
        
        tv_loc = parser.get_or_create_loc(tv_match, language)
        tv_loc.title = tv_details.get("name") or tv_details.get("original_name") or "Unknown"
        tv_loc.overview = tv_details.get("overview")
        tv_loc.poster_path = image_processing_service.pick_poster_path(tv_details, preferred_language=language)
        tv_loc.logo_path = image_processing_service.pick_logo_path(tv_details, preferred_language=language)
        tv_loc.genres = _split_genres([g["name"] for g in tv_details.get("genres") or []])
        tv_loc.original_language = tv_details.get("original_language")
        tv_loc.trailer_url = _pick_trailer_key(tv_details, language, tv_details.get("original_language"))

        localized_asset_prefix = f"tmdb_tv_{tv_match.external_id}_{language}"
        tv_match.local_backdrop_path = parser.enricher._queue_image(
            tv_match.backdrop_path,
            "backdrops",
            f"tmdb_tv_{tv_match.external_id}",
        )
        tv_loc.local_poster_path = parser.enricher._queue_image(tv_loc.poster_path, "posters", localized_asset_prefix)
        tv_loc.local_logo_path = parser.enricher._queue_image(tv_loc.logo_path, "logos", localized_asset_prefix)

    # B. SEASON LEVEL
    season_match = None
    if match.season_number is not None:
        if tv_match.id is None:
            parser.metadata_repo.flush()
        with tv_enrich_lock:
            season_match = parser.metadata_repo.get_season_match(match.provider, tv_match.id, match.season_number)
            if not season_match:
                try:
                    with parser.db.begin_nested():
                        season_match = parser.metadata_repo.create_match(
                            provider=match.provider,
                            external_id=f"{match.external_id}-s{match.season_number}",
                            media_type=MediaType.SEASON,
                            media_item_id=None
                        )
                        season_match.season_number = match.season_number
                        season_match.parent = tv_match
                        season_match.parent_id = tv_match.id
                        season_match.confidence_score = 1.0
                        parser.metadata_repo.flush()
                except Exception:
                    season_match = parser.metadata_repo.get_season_match(match.provider, tv_match.id, match.season_number)

            seasons = tv_details.get("seasons", [])
            season_data = next((s for s in seasons if s.get("season_number") is not None and int(s.get("season_number")) == int(match.season_number)), None)
            
            if season_data:
                season_match.number_of_episodes = season_data.get("episode_count")
                season_loc = parser.get_or_create_loc(season_match, language)
                season_loc.title = season_data.get("name") or f"Season {match.season_number}"
                season_loc.overview = season_data.get("overview")
                if season_data.get("poster_path"):
                    season_loc.poster_path = season_data.get("poster_path")
                season_loc.local_poster_path = parser.enricher._queue_image(
                    season_loc.poster_path,
                    "posters",
                    f"tmdb_tv_{match.external_id}_s{match.season_number}_{language}",
                )
                if tv_match.release_date:
                    season_match.release_date = tv_match.release_date

    # C. EPISODE LEVEL
    if match.season_number is not None and match.episode_number is not None:
        if season_match:
            if season_match.id is None:
                parser.metadata_repo.flush()
            match.parent = season_match
            match.parent_id = season_match.id
        else:
            if tv_match.id is None:
                parser.metadata_repo.flush()
            match.parent = tv_match
            match.parent_id = tv_match.id

        ep_nums = []
        raw_ep = match.episode_number
        if isinstance(raw_ep, list):
            ep_nums = raw_ep
        else:
            ep_nums = [raw_ep]

        titles = []
        overviews = []
        all_stills = []
        first_still = None
        first_air_date = None
        
        for ename in ep_nums:
            try:
                ep_details = parser.enricher._get_episode_details_cached(
                    int(match.external_id), match.season_number, int(ename), language=language
                )
                if ep_details:
                    titles.append(ep_details.get("name") or f"Episode {ename}")
                    if ep_details.get("overview"):
                        overviews.append(ep_details.get("overview"))
                    
                    s_path = ep_details.get("still_path")
                    if s_path:
                        all_stills.append(s_path)
                        if not first_still:
                            first_still = s_path
                            
                    if not first_air_date:
                        first_air_date = ep_details.get("air_date")
                        
                    if ename == ep_nums[0]:
                        match.rating_tmdb = ep_details.get("vote_average")
                        match.vote_count_tmdb = ep_details.get("vote_count")
                        match.runtime = ep_details.get("runtime") or match.runtime
            except Exception as e:
                logger.warning(f"Failed to fetch metadata for episode {ename}: {e}")

        loc = parser.get_or_create_loc(match, language)
        if titles:
            loc.title = " / ".join(titles)
            match.still_path = first_still
            match.stills = all_stills
            still_prefix = f"tmdb_tv_{match.external_id}_s{match.season_number}_e{ep_nums[0]}"
            match.local_stills = [
                local_path
                for index, still_path in enumerate(all_stills)
                if (local_path := parser.enricher._queue_image(still_path, "stills", f"{still_prefix}_{index}"))
            ]
            match.local_still_path = match.local_stills[0] if match.local_stills else None
            if overviews:
                loc.overview = "\n\n".join(overviews)
            
            if first_air_date:
                try:
                    match.release_date = datetime.strptime(first_air_date, "%Y-%m-%d")
                except:
                    pass
            
            match.media_type = MediaType.EPISODE
