import re
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload

from app.shared_kernel.enums import MediaType, ItemStatus
from app.domains.library.models import MediaItem, ExtraFile
from app.domains.metadata.models import MetadataMatch
from app.domains.people.models import MediaPersonLink

class OrganizerDomainService:
    @staticmethod
    def infer_organizer_type(item: MediaItem) -> str:
        scan_mode = str((item.parsed_info or {}).get("scan_mode") or "").lower()
        if scan_mode == "scenes":
            return MediaType.SCENE.value

        if item.parsed_info and item.parsed_info.get("type"):
            return str(item.parsed_info.get("type")).lower()

        active_match = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
        if active_match:
            return active_match.media_type.value

        gtype = None
        if item.parsed_info:
            fn_data = item.parsed_info.get("fn") or {}
            it_data = item.parsed_info.get("it") or {}
            fd_data = item.parsed_info.get("fd") or {}
            gtype = fn_data.get("type") or it_data.get("type") or fd_data.get("type")

        if gtype:
            return str(gtype).lower()

        filename = item.filename.lower()
        if re.search(r"s\d+e\d+", filename) or re.search(r"\b\d+x\d+\b", filename) or re.search(r"\b(ep|episode)\s*\d+\b", filename):
            return MediaType.EPISODE.value
        return MediaType.MOVIE.value

    @staticmethod
    def matches_scan_mode_filter(item_scan_mode: str, scan_mode: Optional[str]) -> bool:
        normalized_filter = str(scan_mode or "").strip().lower()
        normalized_item = str(item_scan_mode or "").strip().lower()

        if not normalized_filter:
            return True
        if normalized_filter == "scenes":
            return normalized_item == "scenes"
        if normalized_filter == "movies_tv":
            return normalized_item in {"", "movies_tv", "porndb_movie"}
        return normalized_item == normalized_filter

    @staticmethod
    def matches_session_mode_filter(item: MediaItem, session_mode: Optional[str]) -> bool:
        normalized_session = str(session_mode or "sfw").strip().lower()
        item_scan_mode = (item.parsed_info or {}).get("scan_mode") or ""
        normalized_item = str(item_scan_mode).strip().lower()
        
        if normalized_item in {"scenes", "porndb_movie"}:
            is_adult = True
        else:
            active_match = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
            if active_match:
                is_adult = active_match.is_adult
            else:
                is_adult = False
            
        return is_adult if normalized_session == "nsfw" else not is_adult

    @classmethod
    def get_unorganized_media_items(cls, db: Session, scan_mode: Optional[str] = None, session_mode: Optional[str] = None) -> List[MediaItem]:
        all_items = db.query(MediaItem).options(
            joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
            joinedload(MediaItem.matches).joinedload(MetadataMatch.overrides),
            joinedload(MediaItem.matches).joinedload(MetadataMatch.people_links).joinedload(MediaPersonLink.person),
            joinedload(MediaItem.extras),
            joinedload(MediaItem.overrides)
        ).filter(
            ~MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED, ItemStatus.IGNORED])
        ).all()

        return [
            item for item in all_items
            if cls.matches_scan_mode_filter((item.parsed_info or {}).get('scan_mode') or '', scan_mode)
            and cls.matches_session_mode_filter(item, session_mode)
        ]

    @classmethod
    def get_unorganized_extra_files(cls, db: Session, scan_mode: Optional[str] = None, session_mode: Optional[str] = None) -> List[ExtraFile]:
        extras = db.query(ExtraFile).join(
            MediaItem, ExtraFile.media_item_id == MediaItem.id
        ).options(
            joinedload(ExtraFile.media_item).joinedload(MediaItem.matches)
        ).filter(
            ~MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED, ItemStatus.IGNORED])
        ).all()

        return [
            ex for ex in extras
            if cls.matches_scan_mode_filter((ex.media_item.parsed_info or {}).get("scan_mode") or "", scan_mode)
            and cls.matches_session_mode_filter(ex.media_item, session_mode)
        ]

    @staticmethod
    def get_missing_parents(db: Session, missing_parent_ids: set) -> List[MediaItem]:
        return db.query(MediaItem).options(
            joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
            joinedload(MediaItem.overrides)
        ).filter(MediaItem.id.in_(missing_parent_ids)).all()

    @staticmethod
    def delete_or_ignore_items(db: Session, item_ids: List[int], extra_ids: List[int], mode: str) -> Dict[str, Any]:
        if mode == "ignore":
            items = db.query(MediaItem).filter(MediaItem.id.in_(item_ids)).all()
            for item in items:
                item.status = ItemStatus.IGNORED
            db.commit()
            return {"ignored_items": len(item_ids)}

        if item_ids:
            db.query(MediaItem).filter(MediaItem.id.in_(item_ids)).delete(synchronize_session=False)
        if extra_ids:
            db.query(ExtraFile).filter(ExtraFile.id.in_(extra_ids)).delete(synchronize_session=False)
        db.commit()
        return {"deleted_items": len(item_ids), "deleted_extras": len(extra_ids)}
