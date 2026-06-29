import logging
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session

from app.shared_kernel.enums import MediaType, Provider
from app.domains.people.models import MediaPersonLink
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.ports.library_port import LibraryPort
from app.shared_kernel.ports.image_service_port import ImageServicePort

logger = logging.getLogger(__name__)

class LocalCreditsAggregator:
    def __init__(self, db: Session, library_port: LibraryPort, image_service: ImageServicePort):
        self.db = db
        self.library_port = library_port
        self.image_service = image_service

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return self.image_service.resolve_image_url(path, subfolder, size)

    def aggregate_credits(self, person_id: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        db = self.db
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        
        # Load credits linked to this person
        active_match_ids = self.library_port.get_active_match_ids()
        links = db.query(MediaPersonLink).filter(
            MediaPersonLink.person_id == person_id,
            MediaPersonLink.match_id.in_(active_match_ids)
        ).all()
        
        movies = []
        tv_map = {}
        scenes = []
        
        for link in links:
            match = link.match
            item = match.media_item
            if not item:
                continue
            match_loc = LanguageService.get_best_localization(match.localizations, ui_lang)
            title = match_loc.title if match_loc else item.filename
            
            credit_entry = {
                "id": item.id,
                "title": title,
                "type": match.media_type.value,
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": self._resolve_img(match_loc.poster_path if match_loc else None, "posters"),
                "backdrop_path": self._resolve_img(match.backdrop_path, "backdrops", size="original"),
                "rating": match.rating_tmdb or 0.0,
                "rating_porndb": match.rating_porndb,
                "job": link.role.value if hasattr(link.role, "value") else str(link.role),
                "character": link.character_name,
                "in_library": True,
            }
            
            if match.media_type == MediaType.SCENE:
                scenes.append(credit_entry)
            elif match.media_type == MediaType.MOVIE:
                if match.provider in (Provider.TMDB, Provider.PORNDB, Provider.FANSDB, Provider.STASHDB):
                    movies.append(credit_entry)
            elif match.media_type in (MediaType.TV, MediaType.EPISODE):
                if match.provider == Provider.TMDB:
                    sid = match.parent_id or match.id
                    if sid not in tv_map:
                        tv_map[sid] = credit_entry
        
        return movies, list(tv_map.values()), scenes
