import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.domains.users.models import UserOverride, Tag
from app.domains.media_assets.services.images import ImageProcessingService
from app.domains.users.schemas import (
    ItemOverridesUpdate,
    BulkOverridesUpdate,
    BulkTagsUpdate,
    BulkWatchedUpdate,
)

logger = logging.getLogger(__name__)

class OverridesService:
    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_override(self, item_id: str) -> Optional[UserOverride]:
        user_id = 1  # Default single user anchor
        media_item_id = None
        metadata_match_id = None

        if isinstance(item_id, str) and item_id.startswith("tmdb_"):
            tmdb_id = item_id.split("_")[1]
            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.external_id == tmdb_id
            ).first()
            if not match:
                # Create a placeholder match record to link the override to
                match = MetadataMatch(provider=Provider.TMDB, external_id=tmdb_id, media_type=MediaType.MOVIE)
                self.db.add(match)
                self.db.flush()
            metadata_match_id = match.id
        elif isinstance(item_id, str) and item_id.startswith("stash_"):
            stash_id = item_id.split("_")[1]
            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == Provider.STASHDB,
                MetadataMatch.external_id == stash_id
            ).first()
            if not match:
                match = MetadataMatch(provider=Provider.STASHDB, external_id=stash_id, media_type=MediaType.SCENE)
                self.db.add(match)
                self.db.flush()
            metadata_match_id = match.id
        else:
            try:
                media_item_id = int(item_id)
            except ValueError:
                # Fallback check if it is a pure tmdb string id passed directly
                match = self.db.query(MetadataMatch).filter(
                    MetadataMatch.provider == Provider.TMDB,
                    MetadataMatch.external_id == str(item_id)
                ).first()
                if match:
                    metadata_match_id = match.id
                else:
                    return None

        # Retrieve or create UserOverride
        if media_item_id:
            override = self.db.query(UserOverride).filter(
                UserOverride.user_id == user_id,
                UserOverride.media_item_id == media_item_id
            ).first()
            if not override:
                override = UserOverride(user_id=user_id, media_item_id=media_item_id)
                self.db.add(override)
            return override
        elif metadata_match_id:
            override = self.db.query(UserOverride).filter(
                UserOverride.user_id == user_id,
                UserOverride.metadata_match_id == metadata_match_id
            ).first()
            if not override:
                override = UserOverride(user_id=user_id, metadata_match_id=metadata_match_id)
                self.db.add(override)
            return override

        return None

    def update_item_overrides(self, request: ItemOverridesUpdate) -> Dict[str, Any]:
        item_id = request.item_id
        override = self._get_or_create_override(str(item_id))
        if not override:
            return {"error": "Target item not found"}

        # Custom text and details
        if request.custom_title is not None:
            override.custom_title = request.custom_title
        if request.custom_overview is not None:
            override.custom_overview = request.custom_overview
        if request.custom_language is not None:
            override.custom_language = request.custom_language

        # Rating, comments, favorite
        rating_val = request.user_rating if request.user_rating is not None else request.rating
        if rating_val is not None:
            override.user_rating = rating_val
            override.user_rating_at = datetime.now(timezone.utc)

        comment_val = request.user_comment if request.user_comment is not None else request.comment
        if comment_val is not None:
            override.user_comment = comment_val
            override.user_comment_at = datetime.now(timezone.utc)

        if request.is_favorite is not None:
            override.is_favorite = bool(request.is_favorite)
            override.is_favorite_at = datetime.now(timezone.utc) if override.is_favorite else None

        if request.is_watched is not None:
            override.is_watched = bool(request.is_watched)
            if override.is_watched:
                override.watch_count = max(override.watch_count, 1)
                override.last_watched_at = datetime.now(timezone.utc)

        if request.resume_position is not None:
            override.resume_position = int(request.resume_position or 0)

        # Tags resolution
        tags_input = request.tags
        if tags_input is not None:
            tags_list = []
            for t in tags_input:
                tag_obj = None
                if isinstance(t, dict):
                    tag_id = t.get("id")
                    tag_name = t.get("name")
                    if tag_id:
                        tag_obj = self.db.query(Tag).filter(Tag.id == tag_id).first()
                    elif tag_name:
                        tag_obj = self.db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name)).first()
                elif isinstance(t, int):
                    tag_obj = self.db.query(Tag).filter(Tag.id == t).first()
                elif isinstance(t, str):
                    tag_obj = self.db.query(Tag).filter(func.lower(Tag.name) == func.lower(t)).first()
                    if not tag_obj:
                        tag_obj = Tag(name=t)
                        self.db.add(tag_obj)
                        self.db.flush()
                if tag_obj and tag_obj not in tags_list:
                    tags_list.append(tag_obj)
            override.tags = tags_list

        self.db.commit()
        return {"status": "success", "item_id": item_id}

    def update_item_status(self, item_id: int, status: str) -> Dict[str, Any]:
        item = self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if not item:
            return {"error": "Item not found"}

        try:
            new_status = ItemStatus(status.lower())
        except ValueError:
            return {"error": f"Invalid status: {status}"}

        if new_status == ItemStatus.IGNORED and item.status != ItemStatus.IGNORED:
            item.ignored_previous_status = item.status
            item.ignored_at = datetime.now(timezone.utc)
        elif new_status != ItemStatus.IGNORED:
            item.ignored_previous_status = None
            item.ignored_at = None

        item.status = new_status
        self.db.commit()
        return {"status": "success", "item_id": item_id, "new_status": item.status.value}

    def update_item_image(self, item_id: str, image_type: str, path: str) -> Dict[str, Any]:
        override = self._get_or_create_override(item_id)
        if not override:
            return {"error": "Target item not found"}

        if image_type == "poster":
            override.custom_poster = path
        elif image_type == "backdrop":
            override.custom_backdrop = path
        elif image_type == "logo":
            override.custom_logo = path
        else:
            return {"error": f"Invalid image type: {image_type}"}

        self.db.commit()
        return {"status": "success", "image_type": image_type, "path": path}

    def handle_image_upload(self, item_id: str, image_type: str, filename: str, file_stream) -> Dict[str, Any]:
        override = self._get_or_create_override(item_id)
        if not override:
            return {"error": "Target item not found"}

        subfolder = "posters"
        if image_type == "backdrop":
            subfolder = "backdrops"
        elif image_type == "logo":
            subfolder = "logos"

        img_service = ImageProcessingService()
        img_service.ensure_folders()

        ext = os.path.splitext(filename)[1] or ".jpg"
        new_filename = f"upload_{uuid.uuid4().hex}{ext}"
        original_path = img_service.get_original_path(subfolder, new_filename)
        thumbnail_path = img_service.get_thumbnail_path(subfolder, new_filename)

        # Write uploaded image file stream
        saved_path = img_service.write_upload(original_path, file_stream)
        if not saved_path:
            return {"error": "Failed to save uploaded image"}

        # Try to generate a thumbnail
        img_service.generate_thumbnail(original_path, thumbnail_path, subfolder)

        # Store in UserOverride
        relative_path_for_db = new_filename
        if image_type == "poster":
            override.custom_poster = relative_path_for_db
        elif image_type == "backdrop":
            override.custom_backdrop = relative_path_for_db
        elif image_type == "logo":
            override.custom_logo = relative_path_for_db

        self.db.commit()
        
        # Resolve path for returning to front-end
        resolved_url = img_service.resolve_image_url(relative_path_for_db, subfolder)
        return {"status": "success", "path": relative_path_for_db, "url": resolved_url}

    def bulk_update(self, request: BulkOverridesUpdate) -> Dict[str, Any]:
        item_ids = request.item_ids or []
        updates = request.updates or {}
        if not item_ids:
            return {"status": "success", "count": 0}

        count = 0
        for item_id in item_ids:
            override = self._get_or_create_override(str(item_id))
            if override:
                for key, val in updates.items():
                    if hasattr(override, key):
                        setattr(override, key, val)
                count += 1

        self.db.commit()
        return {"status": "success", "count": count}

    def bulk_tags(self, request: BulkTagsUpdate) -> Dict[str, Any]:
        item_ids = request.item_ids or []
        tag_ids = request.tag_ids or []
        tags_input = request.tags or []
        action = request.action or "add" # 'add', 'remove', or 'set'

        if not item_ids:
            return {"status": "success", "count": 0}

        # Resolve tags first
        resolved_tags = []
        for tid in tag_ids:
            tag_obj = self.db.query(Tag).filter(Tag.id == tid).first()
            if tag_obj:
                resolved_tags.append(tag_obj)
        for tname in tags_input:
            tag_obj = self.db.query(Tag).filter(func.lower(Tag.name) == func.lower(tname)).first()
            if not tag_obj:
                tag_obj = Tag(name=tname)
                self.db.add(tag_obj)
                self.db.flush()
            if tag_obj not in resolved_tags:
                resolved_tags.append(tag_obj)

        count = 0
        for item_id in item_ids:
            override = self._get_or_create_override(str(item_id))
            if override:
                current_tags = list(override.tags)
                if action == "add":
                    for t in resolved_tags:
                        if t not in current_tags:
                            current_tags.append(t)
                elif action == "remove":
                    current_tags = [t for t in current_tags if t not in resolved_tags]
                elif action == "set":
                    current_tags = resolved_tags
                override.tags = current_tags
                count += 1

        self.db.commit()
        return {"status": "success", "count": count}

    def bulk_watched(self, request: BulkWatchedUpdate) -> Dict[str, Any]:
        item_ids = request.item_ids or []
        is_watched = bool(request.is_watched)
        watched_at = request.watched_at or request.last_watched_at
        
        parsed_date = datetime.now(timezone.utc)
        if watched_at:
            try:
                parsed_date = datetime.fromisoformat(str(watched_at).replace("Z", "+00:00"))
            except ValueError:
                pass

        if not item_ids:
            return {"status": "success", "count": 0}

        count = 0
        for item_id in item_ids:
            override = self._get_or_create_override(str(item_id))
            if override:
                override.is_watched = is_watched
                if is_watched:
                    override.watch_count = max(override.watch_count, 1)
                    override.last_watched_at = parsed_date
                else:
                    override.watch_count = 0
                    override.last_watched_at = None
                count += 1

        self.db.commit()
        return {"status": "success", "count": count}

    def track_virtual(self, item_id: str, is_tracked: bool) -> Dict[str, Any]:
        override = self._get_or_create_override(item_id)
        if not override:
            return {"error": "Target item not found"}

        override.is_tracked = is_tracked
        self.db.commit()
        return {"status": "success", "item_id": item_id, "is_tracked": is_tracked}
