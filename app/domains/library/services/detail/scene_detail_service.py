import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider
from app.domains.users.models import UserOverride
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.domains.library.services.detail._detail_formatter import DetailFormatter

logger = logging.getLogger(__name__)

class SceneDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers

    def get_scene_detail(self, item_id: str):
        db = self.db
        scene_uuid = item_id.split("_")[1] if "_" in item_id else item_id
        
        stash_scraper = self.scrapers.adult(Provider.STASHDB, db)
        scene_data = stash_scraper.fetch_scene(scene_uuid)
        if not scene_data:
            fans_scraper = self.scrapers.adult(Provider.FANSDB, db)
            scene_data = fans_scraper.fetch_scene(scene_uuid)
        
        if not scene_data:
            return JSONResponse(status_code=404, content={"error": "Scene not found on StashDB/FansDB"})
        
        title = scene_data.get("title") or "Unknown Scene"
        images = scene_data.get("images") or []
        poster_url = images[0].get("url") if images else None
        
        date_str = scene_data.get("date")
        year = None
        if date_str:
            try:
                year = int(date_str.split("-")[0])
            except:
                pass
        
        duration_sec = scene_data.get("duration")
        duration_str = None
        if duration_sec:
            try:
                duration_min = int(float(duration_sec) / 60)
                if duration_min > 0:
                    duration_str = f"{duration_min} min"
            except:
                pass
        
        studio_data = scene_data.get("studio") or {}
        studio_name = studio_data.get("name")
        studio_images = studio_data.get("images") or []
        studio_logo = studio_images[0].get("url") if studio_images else None
        
        parent_data = studio_data.get("parent") or {}
        parent_name = parent_data.get("name")
        parent_images = parent_data.get("images") or []
        parent_logo = parent_images[0].get("url") if parent_images else None
        
        cast = []
        for p_entry in scene_data.get("performers") or []:
            perf = p_entry.get("performer") or {}
            p_images = perf.get("images") or []
            p_img = p_images[0].get("url") if p_images else None
            gender_str = str(perf.get("gender") or "").upper()
            mapped_gender = 0
            if "FEMALE" in gender_str:
                mapped_gender = 1
            elif "MALE" in gender_str:
                mapped_gender = 2
            elif gender_str:
                mapped_gender = 3
            
            cast.append({
                "id": perf.get("id"),
                "name": perf.get("name"),
                "character": None,
                "job": "Actor",
                "profile_path": p_img,
                "popularity": perf.get("rating_porndb") or 0,
                "rating_porndb": perf.get("rating_porndb"),
                "scene_count": perf.get("scene_count"),
                "gender": mapped_gender
            })
        
        override = db.query(UserOverride).filter(
            UserOverride.user_id == 1,
            UserOverride.custom_title == title
        ).first()
        
        result = {
            "id": f"stash_{scene_uuid}",
            "title": title,
            "logo_path": self._resolve_img(studio_logo or parent_logo, "logos"),
            "original_logo_path": studio_logo or parent_logo,
            "original_backdrop_path": poster_url,
            "original_title": None,
            "tagline": None,
            "overview": scene_data.get("details"),
            "genres": [],
            "year": year,
            "release_date": date_str,
            "runtime": duration_sec,
            "formatted_duration": duration_str,
            "rating_tmdb": 0.0,
            "vote_count_tmdb": 0,
            "companies": [{"name": studio_name, "logo_path": self._resolve_img(studio_logo, "logos")}] if studio_name else [],
            "networks": [{"name": parent_name, "logo_path": self._resolve_img(parent_logo, "logos")}] if parent_name else [],
            "poster_path": poster_url,
            "backdrop_path": None,
            "original_language": None,
            "type": "scene",
            "cast": cast,
            "cast_total": len(cast),
            "people_complete": True,
            "directors": [],
            "writers": [],
            "is_adult": True,
            "is_favorite": override.is_favorite if override else False,
            "user_rating": override.user_rating if override else None,
            "user_comment": override.user_comment if override else None,
            "external_ids": {
                "stash_id": scene_uuid,
            },
            "custom_tags": [],
            "tags": [],
            "is_tracked": override.is_tracked if override else False,
            "watch_count": override.watch_count if override else 0,
            "is_watched": override.is_watched if override else False,
            "resume_position": override.resume_position if override else 0,
            "last_watched_at": override.last_watched_at.isoformat() if override and override.last_watched_at else None,
            "playback_logs": [],
            "in_library": False,
        }
        return JSONResponse(content=result)
