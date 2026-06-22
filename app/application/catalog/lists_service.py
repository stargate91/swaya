import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, func

from app.domains.users.models import CustomList, CustomListItem, UserOverride
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.people.models import Person, PersonLocalization
from app.shared_kernel.enums import Provider, MediaType, ItemStatus, CustomListType

logger = logging.getLogger(__name__)

class ListsService:
    def __init__(self, db: Session):
        self.db = db

    def _serialize_item(self, item: CustomListItem) -> Dict[str, Any]:
        res = {
            "id": item.id,
            "media_item_id": item.media_item_id,
            "match_id": item.match_id,
            "person_id": item.person_id,
            "studio_id": item.studio_id,
            "collection_id": item.collection_id,
            "added_at": item.added_at.isoformat() if item.added_at else None,
        }
        
        # Populate basic info based on what is linked
        if item.media_item:
            res["title"] = item.media_item.filename
            match = next((m for m in item.media_item.matches), None)
            if match:
                res["tmdb_id"] = int(match.external_id) if match.external_id.isdigit() else None
                res["media_type"] = match.media_type.value
                loc = next((l for l in match.localizations), None)
                if loc:
                    res["poster_path"] = loc.poster_path
        elif item.match:
            res["tmdb_id"] = int(item.match.external_id) if item.match.external_id.isdigit() else None
            res["media_type"] = item.match.media_type.value
            loc = next((l for l in item.match.localizations), None)
            res["title"] = loc.title if loc else item.match.original_title or f"Match #{item.match.id}"
            if loc:
                res["poster_path"] = loc.poster_path
        elif item.person:
            res["title"] = item.person.name
            res["media_type"] = "person"
            res["poster_path"] = item.person.profile_path
            
        return res

    def get_all_lists(self) -> List[Dict[str, Any]]:
        # Ensure Watchlist exists
        watchlist = self.db.query(CustomList).filter(CustomList.name == "Watchlist").first()
        if not watchlist:
            watchlist = CustomList(
                name="Watchlist",
                description="Default system watchlist.",
                list_type=CustomListType.MATCH,
                color="#3b82f6",
                icon="Bookmark"
            )
            self.db.add(watchlist)
            self.db.commit()

        lists = self.db.query(CustomList).all()
        result = []
        for l in lists:
            item_count = len(l.items)
            posters = [self._serialize_item(item).get("poster_path") for item in l.items[:4]]
            posters = [p for p in posters if p]
            
            result.append({
                "id": l.id,
                "name": l.name,
                "is_watchlist": l.name == "Watchlist",
                "description": l.description,
                "color": l.color or "#3b82f6",
                "icon": l.icon or "ListVideo",
                "created_at": l.created_at.isoformat() if l.created_at else None,
                "item_count": item_count,
                "sample_posters": posters
            })
        return result

    def get_list_details(self, list_id: int) -> Dict[str, Any]:
        l = self.db.query(CustomList).filter(CustomList.id == list_id).first()
        if not l:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Not found")

        return {
            "id": l.id,
            "name": l.name,
            "is_watchlist": l.name == "Watchlist",
            "description": l.description,
            "color": l.color,
            "icon": l.icon,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "items": [self._serialize_item(item) for item in l.items]
        }

    def create_list(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get("name", "").strip()
        description = payload.get("description", "").strip() or None
        color = payload.get("color", "").strip() or "#3b82f6"
        icon = payload.get("icon", "").strip() or "ListVideo"

        if not name:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("List name is required")

        existing = self.db.query(CustomList).filter(CustomList.name == name).first()
        if existing:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("A list with this name already exists")

        new_list = CustomList(name=name, description=description, color=color, icon=icon)
        self.db.add(new_list)
        self.db.commit()
        return {
            "id": new_list.id,
            "name": new_list.name,
            "is_watchlist": False,
            "description": new_list.description,
            "color": new_list.color,
            "icon": new_list.icon,
            "created_at": new_list.created_at.isoformat() if new_list.created_at else None,
            "item_count": 0,
            "sample_posters": []
        }

    def update_list(self, list_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        l = self.db.query(CustomList).filter(CustomList.id == list_id).first()
        if not l:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Not found")

        l.name = payload.get("name", l.name).strip()
        l.description = payload.get("description", l.description)
        l.color = payload.get("color", l.color or "#3b82f6").strip()
        l.icon = payload.get("icon", l.icon or "ListVideo").strip()
        self.db.commit()
        return self.get_list_details(list_id)

    def delete_list(self, list_id: int) -> Dict[str, Any]:
        l = self.db.query(CustomList).filter(CustomList.id == list_id).first()
        if not l:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Not found")
        if l.name == "Watchlist":
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("Watchlist cannot be deleted")

        self.db.delete(l)
        self.db.commit()
        return {"status": "success"}

    def add_item_to_list(self, list_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        l = self.db.query(CustomList).filter(CustomList.id == list_id).first()
        if not l:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Not found")

        media_item_id = payload.get("media_item_id")
        tmdb_id = payload.get("tmdb_id")
        media_type = payload.get("media_type", "movie")

        match_id = None
        if tmdb_id:
            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.external_id == str(tmdb_id)
            ).first()
            if not match:
                match = MetadataMatch(
                    provider=Provider.TMDB,
                    external_id=str(tmdb_id),
                    media_type=MediaType.MOVIE if media_type == "movie" else MediaType.TV
                )
                self.db.add(match)
                self.db.commit()
            match_id = match.id

        # Check if already exists
        exists_query = self.db.query(CustomListItem).filter(CustomListItem.list_id == list_id)
        if media_item_id:
            exists_query = exists_query.filter(CustomListItem.media_item_id == media_item_id)
        elif match_id:
            exists_query = exists_query.filter(CustomListItem.match_id == match_id)
        else:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("Missing item identifier")

        exists = exists_query.first()
        if exists:
            return self._serialize_item(exists)

        item = CustomListItem(list_id=list_id, media_item_id=media_item_id, match_id=match_id)
        self.db.add(item)
        self.db.commit()
        return self._serialize_item(item)

    def remove_item_from_list(self, list_id: int, item_id: int) -> Dict[str, Any]:
        item = self.db.query(CustomListItem).filter(CustomListItem.list_id == list_id, CustomListItem.id == item_id).first()
        if not item:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Not found")
        self.db.delete(item)
        self.db.commit()
        return {"status": "success"}

    def get_item_membership(self, item_id: str) -> Dict[str, Any]:
        # Emulate legacy membership check
        tmdb_id = None
        media_item_id = None

        if item_id.startswith("tmdb_"):
            tmdb_id = item_id.split("_")[1]
        else:
            media_item_id = int(item_id)

        query = self.db.query(CustomListItem)
        if media_item_id:
            query = query.filter(CustomListItem.media_item_id == media_item_id)
        elif tmdb_id:
            match = self.db.query(MetadataMatch).filter(MetadataMatch.provider == Provider.TMDB, MetadataMatch.external_id == tmdb_id).first()
            if match:
                query = query.filter(CustomListItem.match_id == match.id)
            else:
                return {"list_ids": []}

        items = query.all()
        return {"list_ids": list(set(item.list_id for item in items))}

    def get_user_catalog(
        self,
        tab: Optional[str] = None,
        offset: int = 0,
        limit: int = 40,
        search: str = "",
        favorite_only: bool = False,
    ) -> Dict[str, Any]:
        # Quick simplified catalog query returning matching physical and virtual elements
        items_list = []
        

        if tab == "people":
            query = self.db.query(Person)
            if search:
                query = query.filter(Person.name.ilike(f"%{search}%"))
            total = query.count()
            people = query.offset(offset).limit(limit).all()
            for p in people:
                override = self.db.query(UserOverride).filter(UserOverride.person_id == p.id).first()
                if favorite_only and (not override or not override.is_favorite):
                    continue
                items_list.append({
                    "id": p.id,
                    "title": p.name,
                    "media_type": "person",
                    "poster_path": p.profile_path,
                    "user_rating": override.user_rating if override else 0,
                    "is_favorite": override.is_favorite if override else False,
                })
        else:
            # tab == "movies" or "tv"
            query = self.db.query(MediaItem).options(joinedload(MediaItem.matches))
            if search:
                query = query.filter(MediaItem.filename.ilike(f"%{search}%"))
            total = query.count()
            items = query.offset(offset).limit(limit).all()
            for item in items:
                override = self.db.query(UserOverride).filter(UserOverride.media_item_id == item.id).first()
                if favorite_only and (not override or not override.is_favorite):
                    continue
                match = next((m for m in item.matches), None)
                items_list.append({
                    "id": item.id,
                    "title": item.filename,
                    "media_type": match.media_type.value if match else "movie",
                    "user_rating": override.user_rating if override else 0,
                    "is_favorite": override.is_favorite if override else False,
                })

        counts = {"movies": total if tab == "movies" else 0, "tv": total if tab == "tv" else 0, "people": total if tab == "people" else 0}
        return {
            "movies": items_list if tab == "movies" else [],
            "tv": items_list if tab == "tv" else [],
            "people": items_list if tab == "people" else [],
            "counts": counts,
            "page": {
                "tab": tab,
                "offset": offset,
                "limit": limit,
                "returned": len(items_list),
                "has_more": offset + len(items_list) < total,
            }
        }

    def bulk_update_catalog_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        tab = payload.get("tab", "movies")
        updates = payload.get("updates", {})
        ids = payload.get("ids", [])

        if not ids:
            return {"status": "success", "updated_ids": []}

        user_rating = updates.get("user_rating")
        is_favorite = updates.get("is_favorite")

        updated_ids = []
        for raw_id in ids:
            # Resolve id
            if str(raw_id).startswith("tmdb_"):
                # Virtual ID
                tmdb_id = str(raw_id).split("_")[1]
                match = self.db.query(MetadataMatch).filter(MetadataMatch.provider == Provider.TMDB, MetadataMatch.external_id == tmdb_id).first()
                if match:
                    override = self.db.query(UserOverride).filter(UserOverride.metadata_match_id == match.id).first()
                    if not override:
                        override = UserOverride(metadata_match_id=match.id)
                        self.db.add(override)
                    if user_rating is not None: override.user_rating = user_rating
                    if is_favorite is not None: override.is_favorite = is_favorite
                    updated_ids.append(raw_id)
            else:
                item_id = int(raw_id)
                if tab == "people":
                    override = self.db.query(UserOverride).filter(UserOverride.person_id == item_id).first()
                    if not override:
                        override = UserOverride(person_id=item_id)
                        self.db.add(override)
                    if user_rating is not None: override.user_rating = user_rating
                    if is_favorite is not None: override.is_favorite = is_favorite
                    updated_ids.append(raw_id)
                else:
                    override = self.db.query(UserOverride).filter(UserOverride.media_item_id == item_id).first()
                    if not override:
                        override = UserOverride(media_item_id=item_id)
                        self.db.add(override)
                    if user_rating is not None: override.user_rating = user_rating
                    if is_favorite is not None: override.is_favorite = is_favorite
                    updated_ids.append(raw_id)

        self.db.commit()
        return {"status": "success", "tab": tab, "updated_ids": updated_ids}
