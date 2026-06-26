from typing import Optional, Any
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse
from datetime import datetime

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.users.models import UserOverride
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.library.services.detail._detail_formatter import DetailFormatter

class TvShowFormatter(DetailFormatter):
    def format(
        self,
        tv_tmdb_id: str,
        db: Session,
        tmdb_scraper: Any,
        seasons_limit: int = 999,
        initial_episodes_limit: int = 999,
        language: str = None
    ):
        from app.application.library.schemas import TvShowDetailResponse
        try:
            tv_tmdb_id_int = int(tv_tmdb_id.split("_")[1]) if "_" in tv_tmdb_id else int(tv_tmdb_id)
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid tv TMDB ID"})
        
        ui_lang = language or DEFAULT_FALLBACK_LANGUAGE
        tmdb_data = tmdb_scraper.get_details(tv_tmdb_id_int, "tv", language=ui_lang)
        if not tmdb_data:
            return JSONResponse(status_code=404, content={"error": "TV Show not found on TMDB"})
        
        # Load local episodes to see what is in the library
        local_items = db.query(MediaItem).options(
            joinedload(MediaItem.extras),
            joinedload(MediaItem.matches)
        ).join(MediaItem.matches).filter(
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.EPISODE,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()

        extras_list = []
        for item in local_items:
            if item.extras:
                match = next((m for m in item.matches if m.season_number is not None and m.episode_number is not None), None)
                if match:
                    parent_label = f"S{match.season_number:02d}E{match.episode_number:02d}"
                else:
                    parent_label = "Extras"

                for ex in item.extras:
                    extras_list.append({
                        "id": ex.id,
                        "name": ex.filename,
                        "path": ex.current_path,
                        "category": ex.category.value if hasattr(ex.category, "value") else str(ex.category),
                        "subtype": ex.subtype.value if (ex.subtype and hasattr(ex.subtype, "value")) else (str(ex.subtype) if ex.subtype else None),
                        "language": ex.language,
                        "parent_label": parent_label,
                    })
        
        local_episodes_map = {}
        for item in local_items:
            for match in item.matches:
                if match.season_number is not None and match.episode_number is not None:
                    ep_num = match.episode_number
                    if isinstance(ep_num, list):
                        for num in ep_num:
                            local_episodes_map[(match.season_number, num)] = item
                    else:
                        local_episodes_map[(match.season_number, int(ep_num))] = item
        
        seasons = []
        all_season_meta = sorted(tmdb_data.get("seasons", []), key=lambda x: x.get("season_number") or 0)
        
        for idx, season_meta in enumerate(all_season_meta):
            season_number = season_meta.get("season_number")
            if season_number is None:
                continue
            
            if idx < seasons_limit:
                season_detail = tmdb_scraper.get_season_details(tv_tmdb_id_int, season_number, language=ui_lang)
                all_episodes = season_detail.get("episodes", []) or []
                
                is_in_library = len(local_items) > 0
                ep_limit = len(all_episodes) if is_in_library else initial_episodes_limit

                episodes = []
                for ep in all_episodes[:ep_limit]:
                    ep_num = ep.get("episode_number")
                    local_item = local_episodes_map.get((season_number, ep_num))
                    
                    override = None
                    from app.shared_kernel.user_context import get_current_user_id
                    current_uid = get_current_user_id()
                    
                    episode_match = db.query(MetadataMatch).filter(
                        MetadataMatch.provider == Provider.TMDB,
                        MetadataMatch.media_type == MediaType.EPISODE,
                        MetadataMatch.season_number == season_number,
                        MetadataMatch.episode_number == ep_num,
                        MetadataMatch.external_id == str(tv_tmdb_id_int)
                    ).first()
                    
                    if episode_match:
                        override = db.query(UserOverride).filter(
                            UserOverride.user_id == current_uid,
                            UserOverride.metadata_match_id == episode_match.id
                        ).first()
                    
                    if not override and local_item:
                        override = db.query(UserOverride).filter(
                            UserOverride.user_id == current_uid,
                            UserOverride.media_item_id == local_item.id
                        ).first()
                    
                    is_watched = False
                    watch_count = 0
                    resume_position = 0
                    if override:
                        is_watched = override.is_watched
                        watch_count = override.watch_count or 0
                        resume_position = override.resume_position or 0

                    is_multi_episode = False
                    if local_item:
                        siblings = [k for k, v in local_episodes_map.items() if v.id == local_item.id]
                        if len(siblings) > 1:
                            is_multi_episode = True
                            match_ids = [m.id for m in local_item.matches]
                            sibling_overrides = db.query(UserOverride).filter(
                                UserOverride.user_id == current_uid,
                                (UserOverride.media_item_id == local_item.id) | (UserOverride.metadata_match_id.in_(match_ids))
                            ).all()
                            for sov in sibling_overrides:
                                if sov.is_watched:
                                    is_watched = True
                                if sov.watch_count and sov.watch_count > watch_count:
                                    watch_count = sov.watch_count
                                if sov.resume_position and sov.resume_position > resume_position:
                                    resume_position = sov.resume_position
                    
                    episodes.append({
                        "id": f"tmdb_{tv_tmdb_id_int}_{season_number}_{ep_num}",
                        "episode_number": ep_num,
                        "title": ep.get("name") or f"Episode {ep_num}",
                        "overview": ep.get("overview"),
                        "still_path": self._resolve_img(ep.get("still_path"), "stills"),
                        "runtime": ep.get("runtime"),
                        "rating_tmdb": ep.get("vote_average"),
                        "vote_count_tmdb": ep.get("vote_count"),
                        "air_date": ep.get("air_date"),
                        "path": local_item.current_path if local_item else None,
                        "filename": local_item.filename if local_item else None,
                        "watch_count": watch_count,
                        "is_watched": is_watched,
                        "resume_position": resume_position,
                        "in_library": local_item is not None,
                        "is_missing": local_item is None,
                        "is_multi_episode": is_multi_episode,
                    })
                
                local_count = sum(1 for ep in all_episodes if (season_number, ep.get("episode_number")) in local_episodes_map)
                episodes_loaded_count = len(episodes)
                episodes_complete = True
            else:
                episodes = []
                episodes_loaded_count = 0
                episodes_complete = False
                local_count = sum(1 for (s, e) in local_episodes_map.keys() if s == season_number)
                all_episodes = []

            seasons.append({
                "season_number": season_number,
                "title": season_meta.get("name") or f"Season {season_number}",
                "overview": season_meta.get("overview"),
                "poster_path": self._resolve_img(season_meta.get("poster_path"), "posters"),
                "air_date": season_meta.get("air_date"),
                "episode_count": season_meta.get("episode_count") or len(all_episodes),
                "local_episode_count": local_count,
                "episodes_loaded_count": episodes_loaded_count,
                "episodes_complete": episodes_complete,
                "episodes": episodes,
            })
            
        tv_credits = tmdb_data.get("aggregate_credits", {}) or tmdb_data.get("credits", {})
        cast = []
        directors = []
        writers = []
        
        for creator in tmdb_data.get("created_by", []) or []:
            directors.append({
                "id": creator.get("id"),
                "name": creator.get("name"),
                "job": "Creator",
                "profile_path": self._resolve_img(creator.get("profile_path"), "people"),
            })
            
        for actor in tv_credits.get("cast", [])[:15]:
            character = actor.get("character")
            if not character and "roles" in actor:
                roles = actor.get("roles", [])
                if roles:
                    character = ", ".join(filter(None, [r.get("character") for r in roles]))
            cast.append({
                "id": actor.get("id"),
                "name": actor.get("name"),
                "character": character,
                "profile_path": self._resolve_img(actor.get("profile_path"), "people"),
            })
            
        crew_list = tmdb_data.get("credits", {}).get("crew", [])
        for crew in crew_list:
            crew_member = {
                "id": crew.get("id"),
                "name": crew.get("name"),
                "job": crew.get("job"),
                "profile_path": self._resolve_img(crew.get("profile_path"), "people"),
            }
            if crew.get("job") == "Director":
                directors.append(crew_member)
            elif crew.get("job") in ("Writer", "Screenplay"):
                writers.append(crew_member)
        
        override = db.query(UserOverride).join(MetadataMatch, UserOverride.metadata_match_id == MetadataMatch.id).filter(
            UserOverride.user_id == current_uid,
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.TV
        ).first()
        
        from app.domains.media_assets.services.images import image_processing_service
        effective_backdrop = None
        if override and override.custom_backdrop:
            effective_backdrop = override.custom_backdrop
        else:
            effective_backdrop = image_processing_service.pick_backdrop_path(tmdb_data, preferred_language=ui_lang, allow_low_res=True)

        effective_logo = None
        if override and override.custom_logo:
            effective_logo = override.custom_logo
        else:
            effective_logo = image_processing_service.pick_logo_path(tmdb_data, preferred_language=ui_lang)
        
        series_match = db.query(MetadataMatch).filter(
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.TV
        ).first()

        keywords_list = []
        if tmdb_data.get("keywords"):
            raw_kws = tmdb_data.get("keywords", {})
            if isinstance(raw_kws, dict):
                keywords_list = [k["name"] for k in raw_kws.get("results", []) if isinstance(k, dict) and "name" in k]

        videos = (tmdb_data.get("videos") or {}).get("results") or []
        trailer_key = None
        youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer" and v.get("key")]
        if not youtube_trailers:
            youtube_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("key")]
        if youtube_trailers:
            trailer_key = youtube_trailers[0].get("key")

        from app.shared_kernel.genre_utils import split_genres as _split_genres
        result = {
            "id": f"tmdb_{tv_tmdb_id_int}",
            "tv_tmdb_id": tv_tmdb_id_int,
            "keywords": keywords_list,
            "trailer_key": trailer_key,
            "extras": extras_list,
            "imdb_id": tmdb_data.get("external_ids", {}).get("imdb_id") or (series_match.imdb_id if series_match else None),
            "title": tmdb_data.get("name") or tmdb_data.get("original_name") or "Unknown TV Show",
            "logo_path": self._resolve_img(effective_logo, "logos"),
            "backdrop_path": self._resolve_img(effective_backdrop, "backdrops", size="original"),
            "poster_path": self._resolve_img(override.custom_poster if (override and override.custom_poster) else tmdb_data.get("poster_path"), "posters"),
            "year": int(tmdb_data.get("first_air_date", "").split("-")[0]) if tmdb_data.get("first_air_date") else None,
            "first_air_date": tmdb_data.get("first_air_date"),
            "last_air_date": tmdb_data.get("last_air_date"),
            "release_status": tmdb_data.get("status"),
            "number_of_seasons": tmdb_data.get("number_of_seasons") or len(seasons),
            "number_of_episodes": tmdb_data.get("number_of_episodes") or 0,
            "overview": tmdb_data.get("overview"),
            "rating_tmdb": tmdb_data.get("vote_average"),
            "rating_imdb": series_match.rating_imdb if series_match else None,
            "rating_rotten": series_match.rating_rotten if series_match else None,
            "rating_meta": series_match.rating_meta if series_match else None,
            "genres": _split_genres([g["name"] for g in tmdb_data.get("genres", [])]) if tmdb_data.get("genres") else [],
            "type": "tv",
            "cast": cast,
            "directors": directors,
            "writers": writers,
            "seasons": seasons,
            "companies": [{"name": c.get("name"), "logo_path": self._resolve_img(c.get("logo_path"), "logos")} for c in tmdb_data.get("production_companies", [])] if tmdb_data.get("production_companies") else [],
            "networks": [{"name": n.get("name"), "logo_path": self._resolve_img(n.get("logo_path"), "logos")} for n in tmdb_data.get("networks", [])] if tmdb_data.get("networks") else [],
            "is_adult": tmdb_data.get("adult", False),
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "is_tracked": override.is_tracked if override else False,
            "in_library": len(local_items) > 0,
            "progressive_seasons": True,
        }
        return TvShowDetailResponse(**result)
