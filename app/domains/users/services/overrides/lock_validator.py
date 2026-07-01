import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domains.users.models import Tag
from app.domains.metadata.models import MetadataMatch

logger = logging.getLogger(__name__)

class LockValidator:
    def resolve_item_is_adult(self, db: Session, media_item_id: Optional[int], metadata_match_id: Optional[int]) -> bool:
        """Determines if a target item is adult-only based on match metadata."""
        is_adult_item = False
        if metadata_match_id:
            match_db = db.query(MetadataMatch).filter(MetadataMatch.id == metadata_match_id).first()
            if match_db:
                is_adult_item = bool(match_db.is_adult)
        elif media_item_id:
            match_db = db.query(MetadataMatch).filter(
                MetadataMatch.media_item_id == media_item_id,
                MetadataMatch.is_active == True
            ).first()
            if match_db:
                is_adult_item = bool(match_db.is_adult)
        return is_adult_item

    def resolve_tags(self, db: Session, tags_input: List[Any], is_adult_item: bool) -> List[Tag]:
        """Resolves tags input (dictionary, IDs, or text strings) into Tag database objects."""
        tags_list = []
        for t in tags_input:
            tag_obj = None
            if isinstance(t, dict):
                tag_id = t.get("id")
                tag_name = t.get("name")
                if tag_id:
                    tag_obj = db.query(Tag).filter(Tag.id == tag_id).first()
                elif tag_name:
                    tag_obj = db.query(Tag).filter(func.lower(Tag.name) == func.lower(tag_name), Tag.is_adult == is_adult_item).first()
            elif isinstance(t, int):
                tag_obj = db.query(Tag).filter(Tag.id == t).first()
            elif isinstance(t, str):
                tag_obj = db.query(Tag).filter(func.lower(Tag.name) == func.lower(t), Tag.is_adult == is_adult_item).first()
                if not tag_obj:
                    tag_obj = Tag(name=t, is_adult=is_adult_item)
                    db.add(tag_obj)
                    db.flush()
            if tag_obj and tag_obj not in tags_list:
                tags_list.append(tag_obj)
        return tags_list

    def parse_watched_date(self, watched_at: Optional[Any]) -> datetime:
        """Parses watched date safely, defaulting to current time if invalid."""
        parsed_date = datetime.now(timezone.utc)
        if watched_at:
            try:
                parsed_date = datetime.fromisoformat(str(watched_at).replace("Z", "+00:00"))
            except ValueError as e:
                logger.debug(f"Swallowed exception parsing watched date: {e}", exc_info=True)
        return parsed_date
