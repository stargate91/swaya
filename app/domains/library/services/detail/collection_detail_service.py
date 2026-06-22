import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService
from app.domains.library.services.detail._detail_formatter import DetailFormatter

logger = logging.getLogger(__name__)

class CollectionDetailService(DetailFormatter):
    def __init__(self, db: Session, scrapers: ScraperGatewayPort):
        super().__init__()
        self.db = db
        self.scrapers = scrapers
        self.tmdb_scraper = scrapers.tmdb(db)

    def get_collection_detail(self, collection_tmdb_id: str, language: str | None = None):
        db = self.db
        try:
            collection_tmdb_id_int = int(collection_tmdb_id)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid collection TMDB ID"})
        
        ui_lang = language or DEFAULT_FALLBACK_LANGUAGE
        
        tmdb_details = {}
        try:
            tmdb_details = self.tmdb_scraper._call_api(
                f"/collection/{collection_tmdb_id_int}",
                {"language": ui_lang}
            ) or {}
        except Exception:
            tmdb_details = {}
            
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MediaItem.status.in_([ItemStatus.ORGANIZED, ItemStatus.RENAMED]),
            MediaItem.item_type == MediaType.MOVIE,
            MetadataMatch.collection_id != None,
            MetadataMatch.is_active == True,
        ).all()
        
        collection_items = []
        for item in local_items:
            for match in item.matches:
                if match.collection and match.collection.external_id == str(collection_tmdb_id_int):
                    collection_items.append(item)
                    break
        
        owned_tmdb_ids = set()
        movies = []
        
        for item in collection_items:
            active_match = next((m for m in item.matches if m.is_active), None)
            if not active_match:
                continue
            owned_tmdb_ids.add(active_match.tmdb_id)
            loc = LanguageService.get_best_localization(active_match.localizations, ui_lang)
            
            movies.append({
                "id": item.id,
                "tmdb_id": active_match.tmdb_id,
                "library_item_id": item.id,
                "title": loc.title if loc else item.filename,
                "year": active_match.release_date.year if active_match.release_date else None,
                "poster_path": self._resolve_img(loc.poster_path if loc else None, "posters"),
                "backdrop_path": self._resolve_img(active_match.backdrop_path, "backdrops"),
                "rating": active_match.rating_porndb or active_match.rating_tmdb or 0.0,
                "rating_porndb": active_match.rating_porndb,
                "type": item.item_type.value,
                "path": item.current_path,
                "in_library": True,
            })
            
        for part in tmdb_details.get("parts", []) or []:
            part_tmdb_id = part.get("id")
            if not part_tmdb_id or part_tmdb_id in owned_tmdb_ids:
                continue
            
            release_date = part.get("release_date")
            year = None
            if release_date:
                try:
                    year = int(release_date.split("-")[0])
                except:
                    pass
            
            movies.append({
                "id": part_tmdb_id,
                "tmdb_id": part_tmdb_id,
                "library_item_id": None,
                "title": part.get("title") or part.get("original_title") or f"Movie {part_tmdb_id}",
                "year": year,
                "poster_path": self._resolve_img(part.get("poster_path"), "posters"),
                "backdrop_path": self._resolve_img(part.get("backdrop_path"), "backdrops"),
                "rating": part.get("vote_average") or 0.0,
                "type": "movie",
                "path": None,
                "in_library": False,
            })
            
        movies.sort(key=lambda x: (0 if x["in_library"] else 1, -(x["year"] or 0), x["title"]))
        
        result = {
            "tmdb_id": collection_tmdb_id_int,
            "title": tmdb_details.get("name") or f"Collection {collection_tmdb_id_int}",
            "overview": tmdb_details.get("overview"),
            "poster_path": self._resolve_img(tmdb_details.get("poster_path"), "posters"),
            "backdrop_path": self._resolve_img(tmdb_details.get("backdrop_path"), "backdrops"),
            "owned_count": len(owned_tmdb_ids),
            "total_count": len(movies),
            "movies": movies,
        }
        return JSONResponse(content=result)
