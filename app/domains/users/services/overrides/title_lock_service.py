import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy import func

from app.domains.users.models import UserOverride, Tag
from app.application.users.schemas import (
    ItemOverridesUpdate,
    BulkOverridesUpdate,
    BulkWatchedUpdate,
)
from app.shared_kernel.exceptions import NotFoundException

logger = logging.getLogger(__name__)

class TitleLockService:
    def __init__(self, parent_service):
        self.service = parent_service

    @property
    def db(self):
        return self.service.db

    @property
    def resolver(self):
        return self.service.resolver

    @property
    def library_port(self):
        return self.service.library_port

    def update_item_overrides(self, request: ItemOverridesUpdate) -> Dict[str, Any]:
        item_id = request.item_id
        is_extra = request.type == 'extra'

        # Delegate all structural library mutations
        if is_extra or request.main_type in ("bonus", "movie", "episode", "scene"):
            payload = {
                "type": request.type,
                "main_type": request.main_type,
                "parent_id": request.parent_id,
                "subtype": request.subtype,
                "language": request.language,
                "season": request.season,
                "episode": request.episode,
                "custom_language": request.custom_language,
                "custom_edition": request.custom_edition,
                "custom_audio_type": request.custom_audio_type,
                "custom_source": request.custom_source,
                "reset_match": request.reset_match,
                "media_type": request.media_type,
            }
            result = self.library_port.update_library_item_type_or_hierarchy(str(item_id), payload)
            if result.get("converted") and result.get("new_item_id"):
                item_id = result["new_item_id"]
            elif is_extra or result.get("converted"):
                return {"status": "success", "item_id": item_id}

        media_item_id, metadata_match_id = self.resolver.resolve_ids(item_id, media_type=request.media_type)

        metadata_override = self.service._get_or_create_metadata_override(str(item_id), media_type=request.media_type)
        physical_override = self.service._get_or_create_physical_override(str(item_id))

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

        if media_item_id and language_updated and m_override.custom_language:
            self.service._enrich_language_if_needed(media_item_id, m_override.custom_language)

        # Rating, comments, favorite
        has_active_interaction = False
        if "user_rating" in request.model_fields_set:
            m_override.user_rating = request.user_rating
            m_override.user_rating_at = datetime.now(timezone.utc) if request.user_rating is not None else None
            if request.user_rating is not None:
                has_active_interaction = True

        if "user_comment" in request.model_fields_set:
            m_override.user_comment = request.user_comment
            m_override.user_comment_at = datetime.now(timezone.utc) if request.user_comment is not None else None
            if request.user_comment:
                has_active_interaction = True

        if request.is_favorite is not None:
            m_override.is_favorite = bool(request.is_favorite)
            m_override.is_favorite_at = datetime.now(timezone.utc) if m_override.is_favorite else None
            if m_override.is_favorite:
                has_active_interaction = True

        if request.is_watched is not None:
            m_override.is_watched = bool(request.is_watched)
            if m_override.is_watched:
                m_override.watch_count = max(m_override.watch_count or 0, 1)
                m_override.last_watched_at = datetime.now(timezone.utc)
                has_active_interaction = True

        if has_active_interaction:
            m_override.is_tracked = True

        if request.resume_position is not None:
            p_override.resume_position = int(request.resume_position or 0)

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

    def bulk_update(self, request: BulkOverridesUpdate) -> Dict[str, Any]:
        item_ids = request.item_ids or []
        is_extra = request.type == 'extra'

        # Apply common updates to library structure via LibraryPort
        library_payload = {
            "parent_id": request.parent_id,
            "subtype": request.subtype,
            "language": request.language,
            "main_type": request.main_type,
            "season": request.season,
            "episode": request.episode,
            "reset_match": request.reset_match,
            "custom_edition": request.custom_edition,
            "custom_audio_type": request.custom_audio_type,
            "custom_source": request.custom_source,
            "custom_language": request.custom_language if request.custom_language is not None else request.language,
        }
        
        self.library_port.bulk_update_library_items(item_ids, is_extra, library_payload)

        # Update user overrides if not extra
        count = 0
        if not is_extra:
            is_converting_to_bonus = request.main_type == "bonus" and request.parent_id is not None
            if not is_converting_to_bonus:
                for item_id in item_ids:
                    m_override = self.service._get_or_create_metadata_override(str(item_id)) or self.service._get_or_create_physical_override(str(item_id))
                    if m_override:
                        language_val = request.custom_language if request.custom_language is not None else request.language
                        if language_val is not None:
                            m_override.custom_language = language_val
                            self.service._enrich_language_if_needed(int(item_id), language_val)
                    count += 1
            else:
                count = len(item_ids)
        else:
            count = len(item_ids)

        # Apply individual item updates
        if request.item_updates:
            for it_up in request.item_updates:
                u_id = it_up.get("id")
                u_updates = it_up.get("updates") or {}
                if not u_id:
                    continue
                
                if is_extra:
                    payload = {
                        "type": "extra",
                        "parent_id": u_updates.get("parent_id"),
                        "subtype": u_updates.get("subtype"),
                        "language": u_updates.get("language"),
                    }
                    self.library_port.update_library_item_type_or_hierarchy(str(u_id), payload)
                else:
                    is_converting_to_bonus = u_updates.get("main_type") == "bonus" and u_updates.get("parent_id") is not None
                    
                    payload = {
                        "type": "media_item",
                        "main_type": u_updates.get("main_type"),
                        "parent_id": u_updates.get("parent_id"),
                        "custom_edition": u_updates.get("custom_edition"),
                        "custom_audio_type": u_updates.get("custom_audio_type"),
                        "custom_source": u_updates.get("custom_source"),
                        "season": u_updates.get("season"),
                        "episode": u_updates.get("episode"),
                        "reset_match": u_updates.get("reset_match") or request.reset_match,
                        "custom_language": u_updates.get("custom_language") or u_updates.get("language"),
                    }
                    self.library_port.update_library_item_type_or_hierarchy(str(u_id), payload)
                    
                    if not is_converting_to_bonus:
                        m_override = self.service._get_or_create_metadata_override(str(u_id)) or self.service._get_or_create_physical_override(str(u_id))
                        if m_override:
                            language_val = u_updates.get("custom_language") if "custom_language" in u_updates else u_updates.get("language")
                            if language_val is not None:
                                m_override.custom_language = language_val
                                self.service._enrich_language_if_needed(int(u_id), language_val)

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
            override = self.service._get_or_create_override(str(item_id))
            if override:
                override.is_watched = is_watched
                if is_watched:
                    override.watch_count = max(override.watch_count or 0, 1)
                    override.last_watched_at = parsed_date
                    override.is_tracked = True
                else:
                    override.watch_count = 0
                    override.last_watched_at = None
                count += 1

        self.db.commit()
        return {"status": "success", "count": count}

    def track_item(self, item_id: str, is_tracked: bool) -> Dict[str, Any]:
        override = self.service._get_or_create_override(item_id)
        if not override:
            raise NotFoundException("Target item not found")

        override.is_tracked = is_tracked
        
        if is_tracked:
            media_type = None
            if override.metadata_match:
                m_type = override.metadata_match.media_type
                media_type = m_type.value if hasattr(m_type, "value") else str(m_type)
            
            from app.infrastructure.scrapers.support.gateway import scraper_gateway
            if media_type == 'scene':
                from app.domains.library.services.detail.scene_detail_service import SceneDetailService
                try:
                    SceneDetailService(self.db, scraper_gateway).get_scene_detail(item_id)
                except Exception as e:
                    logger.error(f"Auto-enrich failed for scene {item_id}: {e}")
            elif media_type == 'tv':
                from app.domains.library.services.detail.tv_detail_service import TvDetailService
                try:
                    TvDetailService(self.db, scraper_gateway).get_library_tv_detail(item_id)
                except Exception as e:
                    logger.error(f"Auto-enrich failed for tv {item_id}: {e}")
            elif media_type == 'movie':
                from app.domains.library.services.detail.movie_detail_service import MovieDetailService
                try:
                    MovieDetailService(self.db, scraper_gateway).get_library_item_detail(item_id)
                except Exception as e:
                    logger.error(f"Auto-enrich failed for movie {item_id}: {e}")

        self.db.commit()
        return {"status": "success", "item_id": item_id, "is_tracked": is_tracked}
