import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType
from app.domains.users.models import UserOverride
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.domains.metadata.models import Studio, MetadataMatch
from app.domains.library.services.detail._detail_formatter import DetailFormatter

logger = logging.getLogger(__name__)

class SceneDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers

    def get_scene_detail(self, item_id: str) -> SceneDetailResponse:
        from app.domains.library.schemas import SceneDetailResponse
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
        
        studio_logo = None
        if studio_name:
            studio_db = db.query(Studio).filter(Studio.name == studio_name).first()
            if studio_db:
                studio_logo = studio_db.logo_path
        
        if not studio_logo:
            studio_images = studio_data.get("images") or []
            studio_logo = studio_images[0].get("url") if studio_images else None
        
        parent_data = studio_data.get("parent") or {}
        parent_name = parent_data.get("name")
        
        parent_logo = None
        if parent_name:
            parent_studio_db = db.query(Studio).filter(Studio.name == parent_name).first()
            if parent_studio_db:
                parent_logo = parent_studio_db.logo_path
                
        if not parent_logo:
            parent_images = parent_data.get("images") or []
            parent_logo = parent_images[0].get("url") if parent_images else None
        
        from app.domains.people.models import Person
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
            
            person_db = db.query(Person).filter(Person.name == perf.get("name")).first()
            if person_db and (person_db.local_profile_path or person_db.profile_path):
                resolved_img = self._resolve_img(person_db.local_profile_path or person_db.profile_path, "people")
            else:
                resolved_img = p_img

            cast.append({
                "id": perf.get("id"),
                "name": perf.get("name"),
                "character": None,
                "job": "Actor",
                "profile_path": resolved_img,
                "popularity": perf.get("rating_porndb") or 0,
                "rating_porndb": perf.get("rating_porndb"),
                "scene_count": perf.get("scene_count"),
                "gender": mapped_gender
            })
        
        from app.shared_kernel.user_context import get_current_user_id
        current_uid = get_current_user_id()
        
        # Resolve local paths from DB match if it exists
        match_db = db.query(MetadataMatch).filter(
            MetadataMatch.external_id == scene_uuid,
            MetadataMatch.media_type == MediaType.SCENE
        ).first()
        
        override = None
        if match_db:
            override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.metadata_match_id == match_db.id
            ).first()
            if not override and match_db.media_item_id:
                override = db.query(UserOverride).filter(
                    UserOverride.user_id == current_uid,
                    UserOverride.media_item_id == match_db.media_item_id
                ).first()
        if not override:
            override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.custom_title == title
            ).first()
        
        local_poster = None
        local_backdrop = None
        if match_db:
            local_backdrop = match_db.local_backdrop_path
            loc_db = next((l for l in match_db.localizations if l.locale == "en"), None)
            if loc_db:
                local_poster = loc_db.local_poster_path

        poster_resolved = None
        if local_poster:
            poster_resolved = self._resolve_img(local_poster, "posters")
        if not poster_resolved:
            poster_resolved = poster_url

        backdrop_resolved = None
        if local_backdrop:
            backdrop_resolved = self._resolve_img(local_backdrop, "scene_stills", size="original")
        if not backdrop_resolved:
            backdrop_resolved = poster_url
        
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
            "poster_path": poster_resolved,
            "backdrop_path": backdrop_resolved,
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
            "in_library": match_db is not None and match_db.media_item_id is not None,
            "library_item_id": match_db.media_item_id if match_db else None,
        }
        return SceneDetailResponse(**result)
