import logging
from typing import Optional, Any
from sqlalchemy.orm import Session, selectinload

from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MediaCollection
from app.domains.users.models import UserOverride
from app.shared_kernel.enums import ItemStatus, MediaType
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService as LangHelper
from app.domains.settings.models import UserSetting, SystemSetting
from app.infrastructure.settings.formatter_config_adapter import load_formatter_config_from_db

logger = logging.getLogger(__name__)

class LibraryCollectionService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_movie_collections(
        self,
        page: int = 1,
        page_size: Optional[int] = 40,
        search: str = "",
        tab: str = "movies",
        include_adult: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieves a paginated and filtered list of movie collections in the library.
        """
        # Get ui language
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        try:
            setting = self.db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == "ui_language").first()
            if not setting:
                setting = self.db.query(SystemSetting).filter(SystemSetting.key == "ui_language").first()
            if setting and setting.value:
                ui_lang = str(setting.value).split("-", 1)[0].strip().lower()
        except:
            pass

        lib_statuses = [ItemStatus.RENAMED, ItemStatus.ORGANIZED]
        
        query = self.db.query(MetadataMatch).join(
            MediaItem, MetadataMatch.media_item_id == MediaItem.id
        ).filter(
            MediaItem.status.in_(lib_statuses),
            MetadataMatch.collection_id != None
        )

        query = query.filter(MetadataMatch.is_adult == include_adult)

        if tab == "movies":
            query = query.filter(MetadataMatch.media_type == MediaType.MOVIE)

        matches = query.options(
            selectinload(MetadataMatch.collection).selectinload(MediaCollection.localizations),
            selectinload(MetadataMatch.localizations),
            selectinload(MetadataMatch.overrides)
        ).all()

        collections_map = {}
        normalized_search = search.strip().lower() if search else ""

        for match in matches:
            collection = match.collection
            if not collection:
                continue

            col_loc = LangHelper.get_best_localization(collection.localizations, ui_lang) if collection.localizations else None
            collection_title = col_loc.title if col_loc and col_loc.title else f"Collection {collection.external_id}"

            if normalized_search and normalized_search not in collection_title.lower():
                continue

            col_id = collection.id
            entry = collections_map.get(col_id)
            if not entry:
                entry = {
                    "id": f"collection_{collection.external_id}",
                    "tmdb_id": int(collection.external_id) if collection.external_id.isdigit() else 0,
                    "title": collection_title,
                    "overview": col_loc.overview if col_loc else None,
                    "poster_path": col_loc.poster_path if col_loc else None,
                    "has_local_poster": bool(col_loc and col_loc.local_poster_path),
                    "poster_remote_path": None,
                    "backdrop_path": collection.backdrop_path,
                    "owned_count": 0,
                    "total_count": 0,
                    "type": "collection",
                    "movies": []
                }
                collections_map[col_id] = entry

            loc = match.localizations[0] if match.localizations else None
            item = match.media_item
            o = next((ov for ov in match.overrides if ov.user_id == 1), None) if match.overrides else None
            
            title = (o.custom_title if (o and o.custom_title) else None) or (loc.title if loc else (item.filename if item else "Unknown"))
            poster_path = (o.custom_poster if (o and o.custom_poster) else None) or (loc.poster_path if loc else None)
            backdrop_path = (o.custom_backdrop if (o and o.custom_backdrop) else None) or (match.backdrop_path or None)
            rating = (o.user_rating if (o and o.user_rating is not None) else None)
            if rating is None:
                rating = match.rating_porndb or match.rating_tmdb or 0.0

            entry["owned_count"] += 1
            entry["movies"].append({
                "id": item.id if item else None,
                "title": title,
                "year": match.release_date.year if match.release_date else None,
                "poster_path": poster_path,
                "backdrop_path": backdrop_path,
                "rating": rating,
                "rating_porndb": match.rating_porndb,
                "rating_imdb": match.rating_imdb,
                "type": match.media_type.value,
                "tmdb_id": int(match.external_id) if match.external_id.isdigit() else 0,
                "path": item.current_path if item else None,
                "is_favorite": o.is_favorite if o else False,
                "user_rating": o.user_rating if o else None
            })

        # Apply config filtering
        config = load_formatter_config_from_db(self.db)
        collection_mode = config.collection_folder_mode
        threshold = config.collection_folder_threshold

        filtered_collections = []
        for col in collections_map.values():
            if collection_mode == "never":
                continue
            elif collection_mode == "threshold":
                if col["owned_count"] >= threshold:
                    filtered_collections.append(col)
            else:
                if col["owned_count"] >= 1:
                    filtered_collections.append(col)

        sorted_collections = sorted(
            filtered_collections,
            key=lambda c: (-c["owned_count"], str(c["title"]).lower(), c["tmdb_id"])
        )

        total_items = len(sorted_collections)
        total_pages = (total_items + page_size - 1) // page_size if page_size and total_items > 0 else 1
        current_page = max(1, min(page, total_pages))
        
        start_idx = (current_page - 1) * page_size if page_size else 0
        end_idx = start_idx + page_size if page_size else total_items
        paged_collections = sorted_collections[start_idx:end_idx]

        return {
            "items": paged_collections,
            "total_items": total_items,
            "page": current_page,
            "page_size": page_size,
            "total_pages": total_pages
        }
