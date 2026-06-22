import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.users.models import UserOverride
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.library.services.detail._detail_formatter import DetailFormatter

logger = logging.getLogger(__name__)

class TvDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers
        self.tmdb_scraper = scrapers.tmdb(db)

    def get_library_tv_detail(self, tv_tmdb_id: str, seasons_limit: int = 5, initial_episodes_limit: int = 4):
        db = self.db
        try:
            tv_tmdb_id_int = int(tv_tmdb_id.split("_")[1]) if "_" in tv_tmdb_id else int(tv_tmdb_id)
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid tv TMDB ID"})
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        tmdb_data = self.tmdb_scraper.get_details(tv_tmdb_id_int, "tv", language=ui_lang)
        if not tmdb_data:
            return JSONResponse(status_code=404, content={"error": "TV Show not found on TMDB"})
        
        # Load local episodes to see what is in the library
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.media_type == MediaType.EPISODE,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
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
        
        for idx, season_meta in enumerate(all_season_meta[:seasons_limit]):
            season_number = season_meta.get("season_number")
            if season_number is None:
                continue
            
            season_detail = self.tmdb_scraper.get_season_details(tv_tmdb_id_int, season_number, language=ui_lang)
            all_episodes = season_detail.get("episodes", []) or []
            
            episodes = []
            for ep in all_episodes[:initial_episodes_limit]:
                ep_num = ep.get("episode_number")
                local_item = local_episodes_map.get((season_number, ep_num))
                
                override = None
                if local_item:
                    override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == local_item.id).first()
                
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
                    "watch_count": override.watch_count if override else 0,
                    "is_watched": override.is_watched if override else False,
                    "resume_position": override.resume_position if override else 0,
                    "in_library": local_item is not None,
                    "is_missing": local_item is None,
                })
            
            seasons.append({
                "season_number": season_number,
                "title": season_meta.get("name") or f"Season {season_number}",
                "overview": season_meta.get("overview"),
                "poster_path": self._resolve_img(season_meta.get("poster_path"), "posters"),
                "air_date": season_meta.get("air_date"),
                "episode_count": season_meta.get("episode_count") or len(all_episodes),
                "episodes_loaded_count": len(episodes),
                "episodes": episodes,
            })
            
        credits = tmdb_data.get("credits", {})
        cast = []
        directors = []
        writers = []
        
        for actor in credits.get("cast", [])[:15]:
            cast.append({
                "id": actor.get("id"),
                "name": actor.get("name"),
                "character": actor.get("character"),
                "profile_path": self._resolve_img(actor.get("profile_path"), "people"),
            })
            
        for crew in credits.get("crew", []):
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
            UserOverride.user_id == 1,
            MetadataMatch.provider == Provider.TMDB,
            MetadataMatch.external_id == str(tv_tmdb_id_int)
        ).first()
        
        result = {
            "id": f"tmdb_{tv_tmdb_id_int}",
            "tv_tmdb_id": tv_tmdb_id_int,
            "imdb_id": tmdb_data.get("external_ids", {}).get("imdb_id"),
            "title": tmdb_data.get("name") or tmdb_data.get("original_name") or "Unknown TV Show",
            "logo_path": None,
            "backdrop_path": self._resolve_img(tmdb_data.get("backdrop_path"), "backdrops"),
            "poster_path": self._resolve_img(tmdb_data.get("poster_path"), "posters"),
            "year": int(tmdb_data.get("first_air_date", "").split("-")[0]) if tmdb_data.get("first_air_date") else None,
            "first_air_date": tmdb_data.get("first_air_date"),
            "last_air_date": tmdb_data.get("last_air_date"),
            "release_status": tmdb_data.get("status"),
            "number_of_seasons": tmdb_data.get("number_of_seasons") or len(seasons),
            "number_of_episodes": tmdb_data.get("number_of_episodes") or 0,
            "overview": tmdb_data.get("overview"),
            "rating_tmdb": tmdb_data.get("vote_average"),
            "genres": [g["name"] for g in tmdb_data.get("genres", [])] if tmdb_data.get("genres") else [],
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
        }
        return JSONResponse(content=result)

    def get_library_tv_season_detail(self, tv_tmdb_id: str, season_number: int):
        db = self.db
        try:
            tv_tmdb_id_int = int(tv_tmdb_id.split("_")[1]) if "_" in tv_tmdb_id else int(tv_tmdb_id)
        except (ValueError, IndexError):
            return JSONResponse(status_code=400, content={"error": "Invalid tv TMDB ID"})
        
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        season_detail = self.tmdb_scraper.get_season_details(tv_tmdb_id_int, season_number, language=ui_lang)
        if not season_detail:
            return JSONResponse(status_code=404, content={"error": "Season not found"})
        
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MetadataMatch.external_id == str(tv_tmdb_id_int),
            MetadataMatch.season_number == season_number,
            MetadataMatch.media_type == MediaType.EPISODE,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        local_episodes_map = {}
        for item in local_items:
            for match in item.matches:
                if match.episode_number is not None:
                    ep_num = match.episode_number
                    if isinstance(ep_num, list):
                        for num in ep_num:
                            local_episodes_map[num] = item
                    else:
                        local_episodes_map[int(ep_num)] = item
        
        episodes = []
        all_episodes = season_detail.get("episodes", []) or []
        for ep in all_episodes:
            ep_num = ep.get("episode_number")
            local_item = local_episodes_map.get(ep_num)
            
            override = None
            if local_item:
                override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == local_item.id).first()
            
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
                "watch_count": override.watch_count if override else 0,
                "is_watched": override.is_watched if override else False,
                "resume_position": override.resume_position if override else 0,
                "in_library": local_item is not None,
                "is_missing": local_item is None,
            })
            
        result = {
            "season_number": season_number,
            "title": season_detail.get("name") or f"Season {season_number}",
            "overview": season_detail.get("overview"),
            "poster_path": self._resolve_img(season_detail.get("poster_path"), "posters"),
            "air_date": season_detail.get("air_date"),
            "episode_count": len(all_episodes),
            "episodes_loaded_count": len(episodes),
            "episodes": episodes,
        }
        return JSONResponse(content=result)
