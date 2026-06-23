from typing import Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.ports.media_resolver import MediaResolverPort

class DbMediaResolver(MediaResolverPort):
    def __init__(self, db: Session):
        self.db = db

    def resolve_ids(self, item_id: str) -> Tuple[Optional[int], Optional[int]]:
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
            media_item_id = match.media_item_id
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
            media_item_id = match.media_item_id
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
                    return None, None

        return media_item_id, metadata_match_id


    def update_item_status(self, item_id: int, status: str) -> Dict[str, Any]:
        item = self.db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if not item:
            from app.shared_kernel.exceptions import NotFoundException
            raise NotFoundException("Item not found")

        try:
            new_status = ItemStatus(status.lower())
        except ValueError:
            from app.shared_kernel.exceptions import BadRequestException
            raise BadRequestException(f"Invalid status: {status}")

        if new_status == ItemStatus.IGNORED and item.status != ItemStatus.IGNORED:
            item.ignored_previous_status = item.status
            item.ignored_at = datetime.now(timezone.utc)
        elif new_status != ItemStatus.IGNORED:
            item.ignored_previous_status = None
            item.ignored_at = None

        item.status = new_status
        self.db.commit()
        return {"status": "success", "item_id": item_id, "new_status": item.status.value}
