import logging
from typing import Dict, Any
from sqlalchemy import func

from app.domains.users.models import UserOverride, Tag
from app.application.users.schemas import BulkTagsUpdate

logger = logging.getLogger(__name__)

class TagOverrideService:
    def __init__(self, parent_service):
        self.service = parent_service

    @property
    def db(self):
        return self.service.db

    def bulk_tags(self, request: BulkTagsUpdate) -> Dict[str, Any]:
        item_ids = request.item_ids or []
        tag_ids = request.tag_ids or []
        tags_input = request.tags or []
        action = request.action or "add"

        if not item_ids:
            return {"status": "success", "count": 0}

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
            override = self.service._get_or_create_override(str(item_id))
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
