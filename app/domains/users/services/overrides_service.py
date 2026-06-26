import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.domains.users.models import UserOverride
from app.application.users.schemas import (
    ItemOverridesUpdate,
    BulkOverridesUpdate,
    BulkTagsUpdate,
    BulkWatchedUpdate,
)
from app.shared_kernel.ports.media_resolver import MediaResolverPort
from app.shared_kernel.ports.library_port import LibraryPort
from app.shared_kernel.ports.image_download_port import ImageDownloadPort
from app.domains.users.services.overrides.title_lock_service import TitleLockService
from app.domains.users.services.overrides.image_override_service import ImageOverrideService
from app.domains.users.services.overrides.tag_override_service import TagOverrideService

logger = logging.getLogger(__name__)

class OverridesService:
    def __init__(self, db: Session, resolver: MediaResolverPort, user_id: Optional[int] = None, image_downloader: Optional[ImageDownloadPort] = None):
        self.db = db
        self.resolver = resolver
        self.library_port: LibraryPort = resolver  # type: ignore[assignment]
        self.image_downloader = image_downloader
        if user_id is None:
            from app.shared_kernel.user_context import get_current_user_id
            user_id = get_current_user_id()
        self.user_id = user_id

        self.title_lock_service = TitleLockService(self)
        self.image_override_service = ImageOverrideService(self)
        self.tag_override_service = TagOverrideService(self)

    def _enrich_language_if_needed(self, media_item_id: int, language: str):
        if not language or language == "none":
            return
        try:
            self.library_port.enrich_item_language(media_item_id, language)
        except Exception as e:
            logger.error(f"Error enriching language {language} for item {media_item_id}: {e}")

    def _get_or_create_metadata_override(self, item_id: str, media_type: Optional[str] = None) -> Optional[UserOverride]:
        media_item_id, metadata_match_id = self.resolver.resolve_ids(item_id, media_type)

        if not media_item_id and not metadata_match_id:
            return None

        if media_item_id and not metadata_match_id:
            metadata_match_id = self.library_port.get_active_match_id(media_item_id)

        if not metadata_match_id:
            return None

        from sqlalchemy.exc import IntegrityError

        def query_meta():
            return self.db.query(UserOverride).filter(
                UserOverride.user_id == self.user_id,
                UserOverride.metadata_match_id == metadata_match_id
            ).first()

        override = query_meta()
        
        if not override and media_item_id:
            physical_override = self.db.query(UserOverride).filter(
                UserOverride.user_id == self.user_id,
                UserOverride.media_item_id == media_item_id,
                UserOverride.metadata_match_id == None
            ).first()
            if physical_override:
                try:
                    with self.db.begin_nested():
                        existing_meta = query_meta()
                        if existing_meta:
                            for field in ["custom_title", "custom_overview", "custom_poster", "custom_backdrop", "custom_logo", "custom_language", "user_rating", "user_comment", "is_favorite", "is_watched"]:
                                val = getattr(physical_override, field, None)
                                if val is not None and getattr(existing_meta, field, None) is None:
                                    setattr(existing_meta, field, val)
                            if physical_override.resume_position:
                                physical_override.custom_title = None
                                physical_override.custom_overview = None
                                physical_override.custom_poster = None
                                physical_override.custom_backdrop = None
                                physical_override.custom_logo = None
                                physical_override.custom_language = None
                                physical_override.user_rating = None
                                physical_override.user_comment = None
                                physical_override.is_favorite = False
                                physical_override.is_watched = False
                            else:
                                self.db.delete(physical_override)
                            override = existing_meta
                        else:
                            physical_override.metadata_match_id = metadata_match_id
                            if physical_override.resume_position:
                                new_physical = UserOverride(
                                    user_id=self.user_id,
                                    media_item_id=media_item_id,
                                    resume_position=physical_override.resume_position
                                )
                                self.db.add(new_physical)
                                physical_override.resume_position = 0
                            physical_override.media_item_id = None
                            override = physical_override
                        self.db.flush()
                except IntegrityError:
                    override = query_meta()
                    if override and physical_override in self.db:
                        if not physical_override.resume_position:
                            self.db.delete(physical_override)

        if not override:
            try:
                with self.db.begin_nested():
                    override = UserOverride(
                        user_id=self.user_id,
                        metadata_match_id=metadata_match_id
                    )
                    self.db.add(override)
                    self.db.flush()
            except IntegrityError:
                override = query_meta()
        return override

    def _get_or_create_physical_override(self, item_id: str) -> Optional[UserOverride]:
        media_item_id, _ = self.resolver.resolve_ids(item_id)
        if not media_item_id:
            return None

        def query_physical():
            return self.db.query(UserOverride).filter(
                UserOverride.user_id == self.user_id,
                UserOverride.media_item_id == media_item_id,
                UserOverride.metadata_match_id == None
            ).first()

        override = query_physical()
        if not override:
            from sqlalchemy.exc import IntegrityError
            try:
                with self.db.begin_nested():
                    override = UserOverride(
                        user_id=self.user_id,
                        media_item_id=media_item_id
                    )
                    self.db.add(override)
                    self.db.flush()
            except IntegrityError:
                override = query_physical()
        return override

    def _get_or_create_override(self, item_id: str, media_type: Optional[str] = None) -> Optional[UserOverride]:
        if isinstance(item_id, str) and item_id.startswith("collection_"):
            collection_tmdb_id = item_id.split("_")[1]
            collection_id = self.library_port.get_or_create_collection_id(collection_tmdb_id, "tmdb")
            
            def query_coll():
                return self.db.query(UserOverride).filter(
                    UserOverride.user_id == self.user_id,
                    UserOverride.collection_id == collection_id
                ).first()

            override = query_coll()
            if not override:
                from sqlalchemy.exc import IntegrityError
                try:
                    with self.db.begin_nested():
                        override = UserOverride(
                            user_id=self.user_id,
                            collection_id=collection_id
                        )
                        self.db.add(override)
                        self.db.flush()
                except IntegrityError:
                    override = query_coll()
            return override

        return self._get_or_create_metadata_override(item_id, media_type) or self._get_or_create_physical_override(item_id)

    def get_or_create_media_item_override(self, media_item_id: int) -> UserOverride:
        """Helper to fetch or create a UserOverride specifically by media_item_id (physical file)."""
        def query_override():
            return self.db.query(UserOverride).filter(
                UserOverride.user_id == self.user_id,
                UserOverride.media_item_id == media_item_id
            ).first()

        override = query_override()
        if not override:
            from sqlalchemy.exc import IntegrityError
            try:
                with self.db.begin_nested():
                    override = UserOverride(user_id=self.user_id, media_item_id=media_item_id)
                    self.db.add(override)
                    self.db.flush()
            except IntegrityError:
                override = query_override()
        return override

    def update_item_overrides(self, request: ItemOverridesUpdate) -> Dict[str, Any]:
        return self.title_lock_service.update_item_overrides(request)

    def update_item_status(self, item_id: int, status: str) -> Dict[str, Any]:
        return self.resolver.update_item_status(item_id, status)

    def update_item_image(self, item_id: str, image_type: str, path: str, media_type: Optional[str] = None) -> Dict[str, Any]:
        return self.image_override_service.update_item_image(item_id, image_type, path, media_type=media_type)

    def handle_image_upload(self, item_id: str, image_type: str, filename: str, file_stream, media_type: Optional[str] = None) -> Dict[str, Any]:
        return self.image_override_service.handle_image_upload(item_id, image_type, filename, file_stream, media_type=media_type)

    def bulk_update(self, request: BulkOverridesUpdate) -> Dict[str, Any]:
        return self.title_lock_service.bulk_update(request)

    def bulk_tags(self, request: BulkTagsUpdate) -> Dict[str, Any]:
        return self.tag_override_service.bulk_tags(request)

    def bulk_watched(self, request: BulkWatchedUpdate) -> Dict[str, Any]:
        return self.title_lock_service.bulk_watched(request)

    def track_item(self, item_id: str, is_tracked: bool) -> Dict[str, Any]:
        return self.title_lock_service.track_item(item_id, is_tracked)
