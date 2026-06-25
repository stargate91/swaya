import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.users.models import UserOverride
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

    def get_collection_detail(self, collection_tmdb_id: str, language: str | None = None) -> CollectionDetailResponse:
        from app.domains.library.schemas import CollectionDetailResponse
        db = self.db
        try:
            collection_tmdb_id_int = int(collection_tmdb_id)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid collection TMDB ID"})
        
        ui_lang = language or DEFAULT_FALLBACK_LANGUAGE
        
        tmdb_details = {}
        try:
            tmdb_details = self.tmdb_scraper.get_collection_details(
                collection_tmdb_id_int,
                language=ui_lang
            ) or {}
        except Exception:
            tmdb_details = {}
            
        if tmdb_details:
            from app.domains.metadata.models import MediaCollection, MediaCollectionLocalization
            from app.shared_kernel.enums import Provider
            collection = db.query(MediaCollection).filter(
                MediaCollection.provider == Provider.TMDB,
                MediaCollection.external_id == str(collection_tmdb_id_int)
            ).first()
            if collection:
                if tmdb_details.get("backdrop_path"):
                    collection.backdrop_path = tmdb_details["backdrop_path"]
                lang_code = LanguageService.clean_locale(ui_lang)
                loc = None
                if collection.id is not None:
                    loc = db.query(MediaCollectionLocalization).filter(
                        MediaCollectionLocalization.collection_id == collection.id,
                        MediaCollectionLocalization.locale == lang_code
                    ).first()
                if not loc:
                    loc = MediaCollectionLocalization(
                        collection=collection,
                        locale=lang_code
                    )
                    db.add(loc)
                loc.title = tmdb_details.get("name") or loc.title
                loc.overview = tmdb_details.get("overview") or loc.overview
                loc.poster_path = tmdb_details.get("poster_path") or loc.poster_path
                try:
                    from app.domains.tasks import task_manager
                    image_service = task_manager.download_worker.image_service
                    
                    def queue_image(path: str, subfolder: str, prefix: str) -> Optional[str]:
                        url = image_service.get_download_url(path, subfolder)
                        if not url:
                            return None
                        import os
                        import re
                        from urllib.parse import urlparse
                        basename = os.path.basename(urlparse(path).path)
                        ext = os.path.splitext(basename)[1].lower() or ".jpg"
                        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
                        filename = f"{safe_prefix}_{basename}{ext}"
                        task_manager.download_worker.enqueue_download(url, subfolder, filename)
                        return f"{subfolder}/{filename}"
                    
                    asset_prefix = f"tmdb_{collection.external_id}"
                    if loc.poster_path and not loc.local_poster_path:
                        loc.local_poster_path = queue_image(loc.poster_path, "posters", asset_prefix)
                    if collection.backdrop_path and not collection.local_backdrop_path:
                        collection.local_backdrop_path = queue_image(collection.backdrop_path, "backdrops", asset_prefix)
                except Exception as e:
                    logger.error(f"Failed to queue image download for collection detail: {e}")

                try:
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error(f"Failed to commit collection metadata: {e}")
            
        local_items = db.query(MediaItem).join(MediaItem.matches).filter(
            MediaItem.status.in_([ItemStatus.ORGANIZED, ItemStatus.RENAMED]),
            MetadataMatch.media_type == MediaType.MOVIE,
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
            active_match_tmdb_id = int(active_match.external_id) if active_match.external_id.isdigit() else 0
            owned_tmdb_ids.add(active_match_tmdb_id)
            loc = LanguageService.get_best_localization(active_match.localizations, ui_lang)
            
            movies.append({
                "id": item.id,
                "tmdb_id": active_match_tmdb_id,
                "library_item_id": item.id,
                "title": loc.title if loc else item.filename,
                "year": active_match.release_date.year if active_match.release_date else None,
                "poster_path": self._resolve_img(loc.poster_path if loc else None, "posters"),
                "backdrop_path": self._resolve_img(active_match.backdrop_path, "backdrops"),
                "rating": active_match.rating_porndb or active_match.rating_tmdb or 0.0,
                "rating_imdb": active_match.rating_imdb,
                "rating_tmdb": active_match.rating_tmdb,
                "rating_porndb": active_match.rating_porndb,
                "type": active_match.media_type.value,
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
                "rating_imdb": None,
                "rating_tmdb": part.get("vote_average"),
                "type": "movie",
                "path": None,
                "in_library": False,
            })
            
        movies.sort(key=lambda x: (0 if x["in_library"] else 1, -(x["year"] or 0), x["title"]))
        
        raw_posters = tmdb_details.get("images", {}).get("posters", [])
        if not raw_posters and tmdb_details.get("poster_path"):
            raw_posters = [{"file_path": tmdb_details.get("poster_path")}]

        raw_backdrops = tmdb_details.get("images", {}).get("backdrops", [])
        if not raw_backdrops and tmdb_details.get("backdrop_path"):
            raw_backdrops = [{"file_path": tmdb_details.get("backdrop_path")}]

        # Check for user overrides
        col_override = None
        if collection:
            from app.shared_kernel.user_context import get_current_user_id
            current_uid = get_current_user_id()
            col_override = db.query(UserOverride).filter(
                UserOverride.user_id == current_uid,
                UserOverride.collection_id == collection.id
            ).first()

        final_poster = self._resolve_img(loc.local_poster_path or loc.poster_path or tmdb_details.get("poster_path") if loc else tmdb_details.get("poster_path"), "posters")
        final_backdrop = self._resolve_img(collection.local_backdrop_path or collection.backdrop_path or tmdb_details.get("backdrop_path") if collection else tmdb_details.get("backdrop_path"), "backdrops")

        if col_override:
            if col_override.custom_poster:
                final_poster = self._resolve_img(col_override.custom_poster, "posters")
            if col_override.custom_backdrop:
                final_backdrop = self._resolve_img(col_override.custom_backdrop, "backdrops")

        result = {
            "tmdb_id": collection_tmdb_id_int,
            "title": tmdb_details.get("name") or f"Collection {collection_tmdb_id_int}",
            "overview": tmdb_details.get("overview"),
            "poster_path": final_poster,
            "backdrop_path": final_backdrop,
            "owned_count": len(owned_tmdb_ids),
            "total_count": len(movies),
            "movies": movies,
            "images": tmdb_details.get("images", {}),
            "collection_posters": raw_posters,
            "collection_backdrops": raw_backdrops,
        }
        return CollectionDetailResponse(**result)
