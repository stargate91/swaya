import math
import logging
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.shared_kernel.enums import MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.people.models import MediaPersonLink
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE

from app.domains.media_assets.services.images import image_processing_service

logger = logging.getLogger(__name__)

class FilmographyService:
    def __init__(self, db: Session):
        self.db = db

    def _resolve_img(self, path: Optional[str], subfolder: str) -> Optional[str]:
        return image_processing_service.resolve_image_url(path, subfolder)


    def aggregate_credits(self, person_id: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        db = self.db
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        
        # Load credits linked to this person
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        movies = []
        tv_map = {}
        scenes = []
        
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            credit_entry = {
                "id": item.id,
                "title": title,
                "type": item.item_type.value,
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
                "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            }
            
            if item.item_type == MediaType.SCENE:
                scenes.append(credit_entry)
            elif item.item_type == MediaType.MOVIE:
                movies.append(credit_entry)
            elif item.item_type in (MediaType.TV, MediaType.EPISODE):
                sid = match.parent_id or match.id
                if sid not in tv_map:
                    tv_map[sid] = credit_entry
        
        return movies, list(tv_map.values()), scenes

    def get_person_movies(self, person_id: int, page: int = 1, page_size: int = 12):
        db = self.db
        # Load movie credits
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type == MediaType.MOVIE,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        movies = []
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            movies.append({
                "id": item.id,
                "title": title,
                "type": "movie",
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
                "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            })
            
        total_items = len(movies)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = movies[start_idx : start_idx + page_size]
        
        return {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }

    def get_person_tv(self, person_id: int, page: int = 1, page_size: int = 12):
        db = self.db
        # Load tv credits
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type.in_([MediaType.TV, MediaType.EPISODE]),
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        tv_map = {}
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            sid = match.parent_id or match.id
            if sid not in tv_map:
                tv_map[sid] = {
                    "id": item.id,
                    "title": title,
                    "type": "tv",
                    "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                    "year": match.release_date.year if match.release_date else None,
                    "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                    "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
                    "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                    "rating_porndb": match.rating_porndb,
                    "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                    "character": link.character_name,
                    "in_library": True,
                }
                
        tv_list = list(tv_map.values())
        total_items = len(tv_list)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = tv_list[start_idx : start_idx + page_size]
        
        return {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }

    def get_person_scenes(self, person_id: int, page: int = 1, page_size: int = 12):
        db = self.db
        # Load scene credits
        links = db.query(MediaPersonLink).join(MediaPersonLink.match).join(MetadataMatch.media_item).filter(
            MediaPersonLink.person_id == person_id,
            MetadataMatch.media_type == MediaType.SCENE,
            MetadataMatch.is_active == True,
            MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED])
        ).all()
        
        scenes = []
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for link in links:
            match = link.match
            item = match.media_item
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            scenes.append({
                "id": item.id,
                "title": title,
                "type": "scene",
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops"),
                "rating": match.rating_porndb or match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            })
            
        total_items = len(scenes)
        total_pages = max(1, math.ceil(total_items / page_size))
        start_idx = (page - 1) * page_size
        sliced = scenes[start_idx : start_idx + page_size]
        
        return {
            "items": sliced,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
        }

