import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.domains.users.models import Tag, user_override_tags
from app.domains.people.models import Person

logger = logging.getLogger(__name__)

class TagsService:
    def __init__(self, db: Session):
        self.db = db

    def _serialize_tag(self, t: Tag) -> Dict[str, Any]:
        custom_images = []
        if t.custom_image_poster_1:
            custom_images.append({"path": t.custom_image_poster_1, "position_x": 50, "position_y": 50})
        if t.custom_image_poster_2:
            custom_images.append({"path": t.custom_image_poster_2, "position_x": 50, "position_y": 50})
        if t.custom_image_backdrop:
            custom_images.append({"path": t.custom_image_backdrop, "position_x": 50, "position_y": 50})
            
        return {
            "id": t.id,
            "name": t.name,
            "color": t.color or "#3b82f6",
            "target_type": "media",
            "is_adult": t.is_adult,
            "custom_images": custom_images
        }

    def _parse_custom_images(self, custom_images: List[Any]) -> List[str]:
        paths = []
        for entry in custom_images:
            if isinstance(entry, dict):
                path = entry.get("path", "")
            else:
                path = str(entry)
            if path:
                paths.append(path)
        return paths

    def get_all_tags(self, target_type: Optional[str] = None, is_adult: bool = False) -> List[Dict[str, Any]]:
        query = self.db.query(Tag).filter(Tag.is_adult == is_adult)
        tags = query.all()
        return [self._serialize_tag(t) for t in tags]

    def create_tag(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = payload.get("name", "").strip()
        color = payload.get("color", "#3b82f6")
        is_adult = bool(payload.get("is_adult", False))
        custom_images = payload.get("custom_images", [])

        if not name:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("Name required")

        existing = self.db.query(Tag).filter(
            func.lower(Tag.name) == func.lower(name),
            Tag.is_adult == is_adult
        ).first()

        if existing:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException("Tag already exists")

        paths = self._parse_custom_images(custom_images)
        poster_1 = paths[0] if len(paths) > 0 else None
        poster_2 = paths[1] if len(paths) > 1 else None
        backdrop = paths[2] if len(paths) > 2 else None

        tag = Tag(
            name=name,
            color=color,
            is_adult=is_adult,
            custom_image_poster_1=poster_1,
            custom_image_poster_2=poster_2,
            custom_image_backdrop=backdrop
        )
        self.db.add(tag)
        self.db.commit()
        return self._serialize_tag(tag)

    def update_tag(self, tag_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        tag = self.db.query(Tag).filter(Tag.id == tag_id).first()
        if not tag:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Not found")

        if "name" in payload:
            name = payload["name"].strip()
            if name:
                existing = self.db.query(Tag).filter(
                    func.lower(Tag.name) == func.lower(name),
                    Tag.is_adult == tag.is_adult,
                    Tag.id != tag_id
                ).first()
                if existing:
                    from app.shared_kernel.exceptions import BadRequestException
                    raise BadRequestException("Name already taken")
                tag.name = name

        if "color" in payload:
            tag.color = payload["color"]

        if "custom_images" in payload:
            paths = self._parse_custom_images(payload["custom_images"])
            tag.custom_image_poster_1 = paths[0] if len(paths) > 0 else None
            tag.custom_image_poster_2 = paths[1] if len(paths) > 1 else None
            tag.custom_image_backdrop = paths[2] if len(paths) > 2 else None

        self.db.commit()
        return self._serialize_tag(tag)

    def delete_tag(self, tag_id: int) -> Dict[str, Any]:
        tag = self.db.query(Tag).filter(Tag.id == tag_id).first()
        if not tag:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Not found")

        # Delete association links
        self.db.execute(user_override_tags.delete().where(user_override_tags.c.tag_id == tag_id))
        self.db.delete(tag)
        self.db.commit()
        return {"status": "success"}
