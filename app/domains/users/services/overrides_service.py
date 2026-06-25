import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.domains.users.models import UserOverride, Tag
from app.domains.media_assets.services.images import image_processing_service
from app.domains.users.schemas import (
    ItemOverridesUpdate,
    BulkOverridesUpdate,
    BulkTagsUpdate,
    BulkWatchedUpdate,
)
from app.shared_kernel.ports.media_resolver import MediaResolverPort
from app.shared_kernel.exceptions import NotFoundException, BadRequestException

logger = logging.getLogger(__name__)

class OverridesService:
    def __init__(self, db: Session, resolver: MediaResolverPort, user_id: Optional[int] = None):
        self.db = db
        self.resolver = resolver
        if user_id is None:
            from app.shared_kernel.user_context import get_current_user_id
            user_id = get_current_user_id()
        self.user_id = user_id

    def _enrich_language_if_needed(self, item, language: str):
        if not language or language == "none":
            return
        
        active_match = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
        if not active_match or not active_match.provider:
            return
            
        from app.shared_kernel.enums import Provider
        if active_match.provider != Provider.TMDB:
            return
            
        try:
            from app.infrastructure.scrapers.enrichment.mainstream_enricher import MainstreamEnricher
            enricher = MainstreamEnricher(self.db)
            enricher.enrich_matched_item(item, language=language)
        except Exception as e:
            logger.error(f"Error enriching language {language} for item {item.id}: {e}")

    def _shift_tv_episode_match_if_needed(self, item, parsed, new_season, new_episode, custom_language, reset_match: bool = False):
        if reset_match:
            return
        from app.shared_kernel.enums import MediaType
        active_match = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
        if active_match and active_match.media_type in (MediaType.SEASON, MediaType.EPISODE, MediaType.TV):
            tv_match = None
            current = active_match
            while current:
                if current.media_type == MediaType.TV:
                    tv_match = current
                    break
                current = current.parent
                if not current and active_match.parent_id is not None:
                    current = self.db.query(MetadataMatch).filter(MetadataMatch.id == active_match.parent_id).first()
            
            if tv_match:
                try:
                    ns_num = int(new_season) if new_season is not None and str(new_season).isdigit() else (int(parsed.get("season")) if str(parsed.get("season")).isdigit() else 1)
                    ne_num = int(new_episode) if new_episode is not None and str(new_episode).isdigit() else (int(parsed.get("episode")) if str(parsed.get("episode")).isdigit() else 1)
                    
                    season_match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == tv_match.provider,
                        MetadataMatch.parent_id == tv_match.id,
                        MetadataMatch.media_type == MediaType.SEASON,
                        MetadataMatch.season_number == ns_num
                    ).first()
                    if not season_match:
                        season_match = MetadataMatch(
                            provider=tv_match.provider,
                            external_id=f"{tv_match.external_id}-s{ns_num}",
                            media_type=MediaType.SEASON,
                            season_number=ns_num,
                            parent_id=tv_match.id,
                            confidence_score=1.0,
                            is_adult=tv_match.is_adult
                        )
                        self.db.add(season_match)
                        self.db.flush()
                        
                    episode_match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == tv_match.provider,
                        MetadataMatch.parent_id == season_match.id,
                        MetadataMatch.media_type == MediaType.EPISODE,
                        MetadataMatch.episode_number == ne_num
                    ).first()
                    if not episode_match:
                        episode_match = MetadataMatch(
                            provider=tv_match.provider,
                            external_id=tv_match.external_id,
                            media_type=MediaType.EPISODE,
                            season_number=ns_num,
                            episode_number=ne_num,
                            parent_id=season_match.id,
                            confidence_score=1.0,
                            media_item_id=item.id,
                            is_active=True,
                            is_adult=tv_match.is_adult
                        )
                        self.db.add(episode_match)
                        self.db.flush()
                    else:
                        episode_match.media_item_id = item.id
                        episode_match.is_active = True
                        episode_match.is_adult = tv_match.is_adult
                        
                    for m in item.matches:
                        if m.id != episode_match.id:
                            m.is_active = False
                            m.media_item_id = None
                            
                    # Enrich the new match
                    from app.infrastructure.scrapers.enrichment.mainstream_enricher import MainstreamEnricher
                    enricher = MainstreamEnricher(self.db)
                    enricher.enrich_matched_item(item, language=custom_language or "en")
                except Exception as e:
                    logger.error(f"Error shifting TV episode match: {e}")

    def _get_or_create_metadata_override(self, item_id: str, media_type: Optional[str] = None) -> Optional[UserOverride]:
        media_item_id, metadata_match_id = self.resolver.resolve_ids(item_id, media_type)

        if not media_item_id and not metadata_match_id:
            return None

        # Try to resolve metadata_match_id from active match if only media_item_id is present
        if media_item_id and not metadata_match_id:
            from app.domains.metadata.models import MetadataMatch
            active_match = self.db.query(MetadataMatch).filter(
                MetadataMatch.media_item_id == media_item_id,
                MetadataMatch.is_active == True
            ).first()
            if active_match:
                metadata_match_id = active_match.id

        if not metadata_match_id:
            return None

        override = self.db.query(UserOverride).filter(
            UserOverride.user_id == self.user_id,
            UserOverride.metadata_match_id == metadata_match_id
        ).first()
        
        # Migration: Split old overrides associated with physical media_item_id
        if not override and media_item_id:
            override = self.db.query(UserOverride).filter(
                UserOverride.user_id == self.user_id,
                UserOverride.media_item_id == media_item_id,
                UserOverride.metadata_match_id == None
            ).first()
            if override:
                override.metadata_match_id = metadata_match_id
                if override.resume_position:
                    physical_override = UserOverride(
                        user_id=self.user_id,
                        media_item_id=media_item_id,
                        resume_position=override.resume_position
                    )
                    self.db.add(physical_override)
                    # Clear from metadata override
                    override.resume_position = 0
                override.media_item_id = None

        if not override:
            override = UserOverride(
                user_id=self.user_id,
                metadata_match_id=metadata_match_id
            )
            self.db.add(override)
        return override

    def _get_or_create_physical_override(self, item_id: str) -> Optional[UserOverride]:
        media_item_id, _ = self.resolver.resolve_ids(item_id)
        if not media_item_id:
            return None

        override = self.db.query(UserOverride).filter(
            UserOverride.user_id == self.user_id,
            UserOverride.media_item_id == media_item_id,
            UserOverride.metadata_match_id == None
        ).first()
        if not override:
            override = UserOverride(
                user_id=self.user_id,
                media_item_id=media_item_id
            )
            self.db.add(override)
        return override

    def _get_or_create_override(self, item_id: str, media_type: Optional[str] = None) -> Optional[UserOverride]:
        if isinstance(item_id, str) and item_id.startswith("collection_"):
            from app.domains.metadata.models import MediaCollection
            from app.shared_kernel.enums import Provider
            collection_tmdb_id = item_id.split("_")[1]
            collection = self.db.query(MediaCollection).filter(
                MediaCollection.provider == Provider.TMDB,
                MediaCollection.external_id == collection_tmdb_id
            ).first()
            if not collection:
                collection = MediaCollection(
                    provider=Provider.TMDB,
                    external_id=collection_tmdb_id
                )
                self.db.add(collection)
                self.db.flush()
            
            override = self.db.query(UserOverride).filter(
                UserOverride.user_id == self.user_id,
                UserOverride.collection_id == collection.id
            ).first()
            if not override:
                override = UserOverride(
                    user_id=self.user_id,
                    collection_id=collection.id
                )
                self.db.add(override)
                self.db.flush()
            return override

        return self._get_or_create_metadata_override(item_id, media_type) or self._get_or_create_physical_override(item_id)

    def get_or_create_media_item_override(self, media_item_id: int) -> UserOverride:
        """Helper to fetch or create a UserOverride specifically by media_item_id (physical file)."""
        override = self.db.query(UserOverride).filter(
            UserOverride.user_id == self.user_id,
            UserOverride.media_item_id == media_item_id
        ).first()
        if not override:
            override = UserOverride(user_id=self.user_id, media_item_id=media_item_id)
            self.db.add(override)
        return override

    def update_item_overrides(self, request: ItemOverridesUpdate) -> Dict[str, Any]:
        logger.info(f"update_item_overrides payload: {request.model_dump()}")
        item_id = request.item_id
        is_extra = request.type == 'extra'

        if is_extra:
            from app.domains.library.models import ExtraFile, MediaItem
            extra = self.db.query(ExtraFile).filter(ExtraFile.id == int(item_id)).first()
            if not extra:
                raise NotFoundException("Target extra item not found")

            # Support conversion to movie/episode/scene
            if request.main_type in ("movie", "episode", "scene"):
                parent_media = extra.media_item
                if parent_media:
                    from app.shared_kernel.enums import ItemStatus
                    new_item = MediaItem(
                        library_id=parent_media.library_id,
                        relative_path=extra.relative_path,
                        filename=extra.filename,
                        extension=extra.extension,
                        status=ItemStatus.NEW,
                        parsed_info={"season": request.season, "episode": request.episode} if request.main_type == "episode" else {}
                    )
                    self.db.add(new_item)
                    self.db.delete(extra)
                    self.db.commit()
                    return {"status": "success", "item_id": item_id}

            if request.parent_id is not None:
                extra.media_item_id = int(request.parent_id)
            if request.subtype is not None:
                from app.shared_kernel.enums import ExtraSubtype
                try:
                    extra.subtype = ExtraSubtype(request.subtype.lower())
                except ValueError:
                    pass
            if request.language is not None:
                extra.language = request.language

            self.db.commit()
            return {"status": "success", "item_id": item_id}

        from app.domains.library.models import MediaItem, ExtraFile
        media_item_id, metadata_match_id = self.resolver.resolve_ids(item_id, media_type=request.media_type)
        item = None
        if media_item_id:
            item = self.db.query(MediaItem).filter(MediaItem.id == media_item_id).first()

        # Convert to extra if main_type is bonus
        if item and request.main_type == "bonus" and request.parent_id is not None:
            from app.shared_kernel.enums import ExtraCategory, ExtraSubtype
            parent_item = self.db.query(MediaItem).filter(MediaItem.id == int(request.parent_id)).first()
            if parent_item:
                for extra in list(item.extras):
                    extra.media_item = parent_item
                item.extras.clear()
                self.db.flush()
            new_extra = ExtraFile(
                media_item_id=int(request.parent_id),
                relative_path=item.relative_path,
                filename=item.filename,
                extension=item.extension,
                category=ExtraCategory.VIDEO,
                subtype=None
            )
            self.db.add(new_extra)
            self.db.delete(item)
            self.db.commit()
            return {"status": "success", "item_id": item_id}

        # Handle conversion between movie and episode
        if item and request.main_type in ("movie", "episode"):
            parsed = dict(item.parsed_info) if item.parsed_info else {}
            old_type = parsed.get("type")
            if not old_type:
                active_m = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
                if active_m:
                    old_type = active_m.media_type.value
                else:
                    fn_data = parsed.get("fn") or {}
                    it_data = parsed.get("it") or {}
                    fd_data = parsed.get("fd") or {}
                    old_type = fn_data.get("type") or it_data.get("type") or fd_data.get("type") or "movie"

            if str(old_type).lower() != request.main_type.lower():
                from app.shared_kernel.enums import ItemStatus
                item.status = ItemStatus.NEW
                parsed["type"] = request.main_type
                for match in item.matches:
                    match.is_active = False
                    match.media_item_id = None
                
                if request.main_type == "movie":
                    parsed.pop("season", None)
                    parsed.pop("episode", None)
                    for k in ["fn", "it", "fd"]:
                        if k in parsed and isinstance(parsed[k], dict):
                            parsed[k].pop("season", None)
                            parsed[k].pop("episode", None)
                            parsed[k]["type"] = "movie"
                elif request.main_type == "episode":
                    for k in ["fn", "it", "fd"]:
                        if k in parsed and isinstance(parsed[k], dict):
                            parsed[k]["type"] = "episode"
            
            item.parsed_info = parsed

        metadata_override = self._get_or_create_metadata_override(str(item_id), media_type=request.media_type)
        physical_override = self._get_or_create_physical_override(str(item_id))

        m_override = metadata_override or physical_override
        p_override = physical_override or metadata_override

        if not m_override:
            raise NotFoundException("Target item not found")

        # Custom text and details
        if request.custom_title is not None:
            m_override.custom_title = request.custom_title
        if request.custom_overview is not None:
            m_override.custom_overview = request.custom_overview
        
        # Language override
        language_updated = False
        if request.custom_language is not None:
            m_override.custom_language = request.custom_language
            language_updated = True
        elif request.language is not None:
            m_override.custom_language = request.language
            language_updated = True

        if item and language_updated and m_override.custom_language:
            self._enrich_language_if_needed(item, m_override.custom_language)

        # Edition, Audio Type, Source overrides
        if item:
            from app.shared_kernel.enums import MovieEdition, MediaAudioType, MediaSource
            if request.custom_edition is not None:
                val = request.custom_edition
                item.custom_edition = MovieEdition.NONE if (val == "none" or not val) else MovieEdition(val.lower())
            if request.custom_audio_type is not None:
                val = request.custom_audio_type
                item.custom_audio_type = MediaAudioType.NONE if (val == "none" or not val) else MediaAudioType(val.lower())
            if request.custom_source is not None:
                val = request.custom_source
                item.custom_source = MediaSource.NONE if (val == "none" or not val) else MediaSource(val.lower())

        # Rating, comments, favorite
        if "user_rating" in request.model_fields_set:
            m_override.user_rating = request.user_rating
            m_override.user_rating_at = datetime.now(timezone.utc) if request.user_rating is not None else None

        if "user_comment" in request.model_fields_set:
            m_override.user_comment = request.user_comment
            m_override.user_comment_at = datetime.now(timezone.utc) if request.user_comment is not None else None

        if request.is_favorite is not None:
            m_override.is_favorite = bool(request.is_favorite)
            m_override.is_favorite_at = datetime.now(timezone.utc) if m_override.is_favorite else None

        if request.is_watched is not None:
            m_override.is_watched = bool(request.is_watched)
            if m_override.is_watched:
                m_override.watch_count = max(m_override.watch_count or 0, 1)
                m_override.last_watched_at = datetime.now(timezone.utc)

        if request.resume_position is not None:
            p_override.resume_position = int(request.resume_position or 0)

        # Season & Episode updates in parsed_info
        if item and (request.season is not None or request.episode is not None):
            parsed = dict(item.parsed_info) if item.parsed_info else {}
            if request.season is not None:
                parsed["season"] = request.season
                for k in ["fn", "it", "fd"]:
                    if k in parsed and isinstance(parsed[k], dict):
                        parsed[k]["season"] = request.season
            if request.episode is not None:
                parsed["episode"] = request.episode
                for k in ["fn", "it", "fd"]:
                    if k in parsed and isinstance(parsed[k], dict):
                        parsed[k]["episode"] = request.episode
            item.parsed_info = parsed
            self._shift_tv_episode_match_if_needed(item, parsed, request.season, request.episode, m_override.custom_language, bool(request.reset_match))

        # Reset Match
        if item and request.reset_match:
            from app.shared_kernel.enums import ItemStatus
            item.status = ItemStatus.NEW
            for match in item.matches:
                match.is_active = False
                match.media_item_id = None

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
            m_override.tags = tags_list

        self.db.commit()
        return {
            "status": "success",
            "item_id": item_id,
            "user_rating": m_override.user_rating if m_override else None,
            "user_comment": m_override.user_comment if m_override else None,
            "is_watched": m_override.is_watched if m_override else False,
            "is_favorite": m_override.is_favorite if m_override else False,
            "tags": [t.name for t in m_override.tags] if m_override and m_override.tags else [],
        }

    def update_item_status(self, item_id: int, status: str) -> Dict[str, Any]:
        return self.resolver.update_item_status(item_id, status)

    def update_item_image(self, item_id: str, image_type: str, path: str, media_type: Optional[str] = None) -> Dict[str, Any]:
        override = self._get_or_create_override(item_id, media_type=media_type)
        if not override:
            raise NotFoundException("Target item not found")

        if image_type not in ("poster", "backdrop", "logo"):
            raise BadRequestException(f"Invalid image type: {image_type}")

        subfolder = "posters"
        if image_type == "backdrop":
            subfolder = "backdrops"
        elif image_type == "logo":
            subfolder = "logos"

        if path and (path.startswith("/") or path.startswith(("http://", "https://"))):
            try:
                from app.domains.tasks import task_manager
                image_service = task_manager.download_worker.image_service
                url = image_service.get_download_url(path, subfolder)
                if url:
                    import re
                    from urllib.parse import urlparse
                    basename = os.path.basename(urlparse(path).path)
                    ext = os.path.splitext(basename)[1].lower() or ".jpg"
                    prefix = f"user_override_{override.user_id}_{item_id}"
                    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
                    filename = f"{safe_prefix}_{basename}{ext}"
                    task_manager.download_worker.enqueue_download(url, subfolder, filename)
                    path = f"{subfolder}/{filename}"
            except Exception as e:
                logger.error(f"Failed to queue image download for user override: {e}")

        if image_type == "poster":
            override.custom_poster = path
        elif image_type == "backdrop":
            override.custom_backdrop = path
        elif image_type == "logo":
            override.custom_logo = path

        self.db.commit()
        return {"status": "success", "image_type": image_type, "path": path}

    def handle_image_upload(self, item_id: str, image_type: str, filename: str, file_stream, media_type: Optional[str] = None) -> Dict[str, Any]:
        override = self._get_or_create_override(item_id, media_type=media_type)
        if not override:
            raise NotFoundException("Target item not found")

        subfolder = "posters"
        if image_type == "backdrop":
            subfolder = "backdrops"
        elif image_type == "logo":
            subfolder = "logos"

        img_service = image_processing_service
        img_service.ensure_folders()

        ext = os.path.splitext(filename)[1] or ".jpg"
        new_filename = f"upload_{uuid.uuid4().hex}{ext}"
        original_path = img_service.get_original_path(subfolder, new_filename)
        thumbnail_path = img_service.get_thumbnail_path(subfolder, new_filename)

        # Write uploaded image file stream
        saved_path = img_service.write_upload(original_path, file_stream)
        if not saved_path:
            raise BadRequestException("Failed to save uploaded image")

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
        logger.info(f"bulk_update payload: {request.model_dump()}")
        item_ids = request.item_ids or []
        is_extra = request.type == 'extra'

        count = 0
        # 1. Apply common updates
        for item_id in item_ids:
            if is_extra:
                from app.domains.library.models import ExtraFile, MediaItem
                extra = self.db.query(ExtraFile).filter(ExtraFile.id == int(item_id)).first()
                if extra:
                    if request.parent_id is not None:
                        extra.media_item_id = int(request.parent_id)
                    if request.subtype is not None:
                        from app.shared_kernel.enums import ExtraSubtype
                        try:
                            extra.subtype = ExtraSubtype(request.subtype.lower())
                        except ValueError:
                            pass
                    if request.language is not None:
                        extra.language = request.language

                    if request.main_type in ("movie", "episode", "scene"):
                        parent_media = extra.media_item
                        if parent_media:
                            from app.shared_kernel.enums import ItemStatus
                            new_item = MediaItem(
                                library_id=parent_media.library_id,
                                relative_path=extra.relative_path,
                                filename=extra.filename,
                                extension=extra.extension,
                                status=ItemStatus.NEW,
                                parsed_info={"season": request.season, "episode": request.episode} if request.main_type == "episode" else {}
                            )
                            self.db.add(new_item)
                            self.db.delete(extra)
                    count += 1
            else:
                from app.domains.library.models import MediaItem, ExtraFile
                item = self.db.query(MediaItem).filter(MediaItem.id == int(item_id)).first()
                if item:
                    if request.main_type == "bonus" and request.parent_id is not None:
                        from app.shared_kernel.enums import ExtraCategory, ExtraSubtype
                        parent_item = self.db.query(MediaItem).filter(MediaItem.id == int(request.parent_id)).first()
                        if parent_item:
                            for extra in list(item.extras):
                                extra.media_item = parent_item
                            item.extras.clear()
                            self.db.flush()
                        new_extra = ExtraFile(
                            media_item_id=int(request.parent_id),
                            relative_path=item.relative_path,
                            filename=item.filename,
                            extension=item.extension,
                            category=ExtraCategory.VIDEO,
                            subtype=ExtraSubtype.OTHER
                        )
                        self.db.add(new_extra)
                        self.db.delete(item)
                    else:
                        metadata_override = self._get_or_create_metadata_override(str(item_id))
                        physical_override = self._get_or_create_physical_override(str(item_id))
                        m_override = metadata_override or physical_override
                        if m_override:
                            from app.shared_kernel.enums import MovieEdition, MediaAudioType, MediaSource
                            if request.custom_edition is not None:
                                val = request.custom_edition
                                item.custom_edition = MovieEdition.NONE if (val == "none" or not val) else MovieEdition(val.lower())
                            if request.custom_audio_type is not None:
                                val = request.custom_audio_type
                                item.custom_audio_type = MediaAudioType.NONE if (val == "none" or not val) else MediaAudioType(val.lower())
                            if request.custom_source is not None:
                                val = request.custom_source
                                item.custom_source = MediaSource.NONE if (val == "none" or not val) else MediaSource(val.lower())
                            
                            language_val = request.custom_language if request.custom_language is not None else request.language
                            if language_val is not None:
                                m_override.custom_language = language_val
                                self._enrich_language_if_needed(item, language_val)

                            if request.season is not None or request.episode is not None:
                                parsed = dict(item.parsed_info) if item.parsed_info else {}
                                if request.season is not None:
                                    parsed["season"] = request.season
                                    for k in ["fn", "it", "fd"]:
                                        if k in parsed and isinstance(parsed[k], dict):
                                            parsed[k]["season"] = request.season
                                if request.episode is not None:
                                    parsed["episode"] = request.episode
                                    for k in ["fn", "it", "fd"]:
                                        if k in parsed and isinstance(parsed[k], dict):
                                            parsed[k]["episode"] = request.episode
                                item.parsed_info = parsed
                                self._shift_tv_episode_match_if_needed(item, parsed, request.season, request.episode, m_override.custom_language, bool(request.reset_match))

                            if request.reset_match:
                                for match in item.matches:
                                    match.is_active = False
                    count += 1

        # 2. Apply individual item updates (e.g. auto numbering)
        if request.item_updates:
            for it_up in request.item_updates:
                u_id = it_up.get("id")
                u_updates = it_up.get("updates") or {}
                if not u_id:
                    continue
                if is_extra:
                    from app.domains.library.models import ExtraFile
                    extra = self.db.query(ExtraFile).filter(ExtraFile.id == int(u_id)).first()
                    if extra:
                        if "parent_id" in u_updates:
                            extra.media_item_id = int(u_updates["parent_id"])
                        if "subtype" in u_updates:
                            from app.shared_kernel.enums import ExtraSubtype
                            try:
                                extra.subtype = ExtraSubtype(u_updates["subtype"].lower())
                            except ValueError:
                                pass
                        if "language" in u_updates:
                            extra.language = u_updates["language"]
                else:
                    from app.domains.library.models import MediaItem
                    item = self.db.query(MediaItem).filter(MediaItem.id == int(u_id)).first()
                    if item:
                        metadata_override = self._get_or_create_metadata_override(str(u_id))
                        physical_override = self._get_or_create_physical_override(str(u_id))
                        m_override = metadata_override or physical_override
                        if m_override:
                            from app.shared_kernel.enums import MovieEdition, MediaAudioType, MediaSource
                            if "custom_edition" in u_updates:
                                val = u_updates["custom_edition"]
                                item.custom_edition = MovieEdition.NONE if (val == "none" or not val) else MovieEdition(val.lower())
                            if "custom_audio_type" in u_updates:
                                val = u_updates["custom_audio_type"]
                                item.custom_audio_type = MediaAudioType.NONE if (val == "none" or not val) else MediaAudioType(val.lower())
                            if "custom_source" in u_updates:
                                val = u_updates["custom_source"]
                                item.custom_source = MediaSource.NONE if (val == "none" or not val) else MediaSource(val.lower())
                            
                            language_val = u_updates.get("custom_language") if "custom_language" in u_updates else u_updates.get("language")
                            if language_val is not None:
                                m_override.custom_language = language_val
                                self._enrich_language_if_needed(item, language_val)

                            if "season" in u_updates or "episode" in u_updates:
                                parsed = dict(item.parsed_info) if item.parsed_info else {}
                                if "season" in u_updates:
                                    parsed["season"] = u_updates["season"]
                                    for k in ["fn", "it", "fd"]:
                                        if k in parsed and isinstance(parsed[k], dict):
                                            parsed[k]["season"] = u_updates["season"]
                                if "episode" in u_updates:
                                    parsed["episode"] = u_updates["episode"]
                                    for k in ["fn", "it", "fd"]:
                                        if k in parsed and isinstance(parsed[k], dict):
                                            parsed[k]["episode"] = u_updates["episode"]
                                item.parsed_info = parsed
                                self._shift_tv_episode_match_if_needed(item, parsed, u_updates.get("season"), u_updates.get("episode"), m_override.custom_language, bool(u_updates.get("reset_match") or request.reset_match))

                            if u_updates.get("reset_match"):
                                for match in item.matches:
                                    match.is_active = False

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
                    override.watch_count = max(override.watch_count or 0, 1)
                    override.last_watched_at = parsed_date
                else:
                    override.watch_count = 0
                    override.last_watched_at = None
                count += 1

        self.db.commit()
        return {"status": "success", "count": count}

    def track_item(self, item_id: str, is_tracked: bool) -> Dict[str, Any]:
        override = self._get_or_create_override(item_id)
        if not override:
            raise NotFoundException("Target item not found")

        override.is_tracked = is_tracked
        self.db.commit()
        return {"status": "success", "item_id": item_id, "is_tracked": is_tracked}
