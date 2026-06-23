import logging
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.shared_kernel.enums import MediaType, ItemStatus
from app.domains.library.models import MediaItem, Library, ExtraFile
from app.domains.metadata.models import MetadataMatch
from app.shared_kernel.ports.scrapers import ScraperGatewayPort
from app.shared_kernel.ports.settings_port import SettingsPort
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.application.organizer.schemas import OrganizerGroupsResponse, ActionResponse

logger = logging.getLogger(__name__)

class OrganizerService:
    def __init__(self, db: Session, scrapers: ScraperGatewayPort, settings_port: Optional[SettingsPort] = None):
        self.db = db
        from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
        self.settings = settings_port or DbSettingsAdapter(db)
        self.img_service = image_processing_service

    def _preferred_metadata_language(self) -> str:
        lang = self.settings.get_setting("primary_metadata_language")
        return lang if lang else DEFAULT_FALLBACK_LANGUAGE

    def _resolve_image_with_fallback(self, local_path: Optional[str], remote_path: Optional[str], subfolder: str) -> Optional[str]:
        resolved = self.img_service.resolve_image_url(local_path, subfolder)
        if resolved:
            return resolved
        return self.img_service.resolve_image_url(remote_path, subfolder)

    def _infer_organizer_type(self, item: MediaItem) -> str:
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

        import re
        filename = item.filename.lower()
        if re.search(r"s\d+e\d+", filename) or re.search(r"\b\d+x\d+\b", filename) or re.search(r"\b(ep|episode)\s*\d+\b", filename):
            return MediaType.EPISODE.value
        return MediaType.MOVIE.value

    @staticmethod
    def _matches_scan_mode_filter(item_scan_mode: str, scan_mode: Optional[str]) -> bool:
        normalized_filter = str(scan_mode or "").strip().lower()
        normalized_item = str(item_scan_mode or "").strip().lower()

        if not normalized_filter:
            return True
        if normalized_filter == "scenes":
            return normalized_item == "scenes"
        if normalized_filter == "movies_tv":
            return normalized_item in {"", "movies_tv", "porndb_movie"}
        return normalized_item == normalized_filter

    @classmethod
    def _matches_session_mode_filter(cls, item: MediaItem, session_mode: Optional[str]) -> bool:
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

    def get_organizer_groups(self, scan_mode: Optional[str] = None, session_mode: Optional[str] = None) -> OrganizerGroupsResponse:
        all_items = self.db.query(MediaItem).options(
            joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
            joinedload(MediaItem.extras),
            joinedload(MediaItem.overrides)
        ).filter(
            ~MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED, ItemStatus.IGNORED])
        ).all()

        items = [
            item for item in all_items
            if self._matches_scan_mode_filter((item.parsed_info or {}).get('scan_mode') or '', scan_mode)
            and self._matches_session_mode_filter(
                item,
                session_mode,
            )
        ]

        from app.infrastructure.settings.formatter_config_adapter import build_formatter_from_db
        formatter = build_formatter_from_db(self.db)

        groups = {"manual": [], "movies": [], "tv": [], "extras": [], "collisions": []}
        parent_planned_paths = {}
        parent_types = {}
        parent_statuses = {}
        parent_is_adults = {}
        pref_lang = self._preferred_metadata_language()

        previews = []
        preview_map = {}
        for item in items:
            active_match = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
            if active_match and not active_match.is_active:
                active_match = None
            overrides = item.overrides
            target_lang = overrides.custom_language if (overrides and overrides.custom_language) else (formatter.config.default_target_language or pref_lang)
            loc = None
            if active_match:
                loc = LanguageService.get_best_localization(active_match.localizations, target_lang)
            try:
                preview = formatter.format_item(item, active_match, loc)
                previews.append(preview)
                preview_map[item.id] = preview
            except Exception:
                pass

        if previews:
            formatter.resolve_collisions(previews)

        for item in items:
            overrides = item.overrides
            target_lang = overrides.custom_language if (overrides and overrides.custom_language) else (formatter.config.default_target_language or pref_lang)
            preview = preview_map.get(item.id)
            if preview:
                planned_path = str(preview.target_path).replace("\\", "/")
                action = getattr(preview, "action", "rename")
            else:
                planned_path = item.planned_path
                action = None

            parent_planned_paths[item.id] = planned_path
            matches_dto = []
            for m in item.matches:
                loc = LanguageService.get_best_localization(m.localizations, pref_lang)
                matches_dto.append({
                    "id": m.id,
                    "tmdb_id": int(m.external_id) if m.external_id.isdigit() else None,
                    "type": m.media_type.value,
                    "title": loc.title if loc else "",
                    "year": m.release_date.year if m.release_date else None,
                    "poster_path": loc.poster_path if loc else None,
                    "vote_average": m.rating_tmdb,
                    "is_active": m.is_active,
                    "confidence": m.confidence_score,
                    "is_adult": m.is_adult,
                    "provider": m.provider.value if m.provider else None
                })

            itype = self._infer_organizer_type(item)
            images_list = []
            if item.matches:
                active_m = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
                if active_m:
                    if active_m.media_type == MediaType.EPISODE:
                        season_m = None
                        if active_m.parent_id:
                            season_m = self.db.query(MetadataMatch).filter(MetadataMatch.id == active_m.parent_id).first()

                        tv_m = None
                        if season_m and season_m.parent_id:
                            tv_m = self.db.query(MetadataMatch).filter(MetadataMatch.id == season_m.parent_id).first()
                        elif active_m.parent_id:
                            parent_m = self.db.query(MetadataMatch).filter(MetadataMatch.id == active_m.parent_id).first()
                            if parent_m and parent_m.media_type == MediaType.TV:
                                tv_m = parent_m

                        if season_m:
                            loc = LanguageService.get_best_localization(season_m.localizations, target_lang)
                            if loc:
                                resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                                if resolved:
                                    images_list.append({"path": resolved})

                        if tv_m:
                            loc = LanguageService.get_best_localization(tv_m.localizations, target_lang)
                            if loc:
                                resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                                if resolved:
                                    images_list.append({"path": resolved})

                        if not images_list:
                            resolved = self._resolve_image_with_fallback(active_m.local_still_path, active_m.still_path, "stills")
                            if resolved:
                                images_list.append({"path": resolved})
                    elif active_m.media_type == MediaType.SCENE:
                        resolved = self._resolve_image_with_fallback(active_m.local_backdrop_path, active_m.backdrop_path, "scene_stills")
                        if resolved:
                            images_list.append({"path": resolved})
                        else:
                            loc = LanguageService.get_best_localization(active_m.localizations, target_lang)
                            if loc:
                                resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                                if resolved:
                                    images_list.append({"path": resolved})
                    else:
                        loc = LanguageService.get_best_localization(active_m.localizations, target_lang)
                        if loc:
                            resolved = self._resolve_image_with_fallback(loc.local_poster_path, loc.poster_path, "posters")
                            if resolved:
                                images_list.append({"path": resolved})

            parent_types[item.id] = itype
            parent_statuses[item.id] = item.status.value
            item_scan_mode = str((item.parsed_info or {}).get("scan_mode") or "").lower()
            parent_scan_modes = getattr(self, "_parent_scan_modes", None)
            if parent_scan_modes is None:
                parent_scan_modes = {}
                self._parent_scan_modes = parent_scan_modes
            parent_scan_modes[item.id] = item_scan_mode
            
            if item_scan_mode in {"scenes", "porndb_movie"}:
                item_is_adult = True
            else:
                active_match = next((m for m in item.matches if m.is_active), None) or next((m for m in item.matches), None)
                item_is_adult = active_match.is_adult if active_match else False
            parent_is_adults[item.id] = item_is_adult

            parsed = item.parsed_info or {}
            fn_data = parsed.get("fn") or {}
            it_data = parsed.get("it") or {}
            fd_data = parsed.get("fd") or {}
            season_val = parsed.get("season") or fn_data.get("season") or it_data.get("season") or fd_data.get("season")
            episode_val = parsed.get("episode") or fn_data.get("episode") or it_data.get("episode") or fd_data.get("episode")

            overrides = item.overrides
            custom_edition_val = overrides.custom_edition.value if (overrides and overrides.custom_edition) else (item.edition.value if item.edition else "none")
            custom_audio_type_val = overrides.custom_audio_type.value if (overrides and overrides.custom_audio_type) else (item.audio_type.value if item.audio_type else "none")
            custom_source_val = overrides.custom_source.value if (overrides and overrides.custom_source) else (item.source.value if item.source else "none")

            item_dto = {
                "id": item.id,
                "filename": item.filename,
                "status": item.status.value,
                "type": itype,
                "title": item.filename,
                "planned_path": planned_path,
                "extension": item.extension,
                "size_mb": round((item.size or 0) / (1024 * 1024), 2),
                "images": images_list,
                "matches": matches_dto,
                "current_path": item.current_path,
                "action": action,
                "target_language": target_lang,
                "scan_mode": item_scan_mode,
                "season": str(season_val) if season_val is not None else None,
                "episode": str(episode_val) if episode_val is not None else None,
                "custom_edition": custom_edition_val,
                "custom_audio_type": custom_audio_type_val,
                "custom_source": custom_source_val
            }

            if item.status in [ItemStatus.NEW, ItemStatus.UNCERTAIN, ItemStatus.NO_MATCH, ItemStatus.MULTIPLE, ItemStatus.ERROR]:
                groups["manual"].append(item_dto)
            else:
                is_movie = any(m.media_type == MediaType.MOVIE for m in item.matches)
                if is_movie:
                    groups["movies"].append(item_dto)
                else:
                    groups["tv"].append(item_dto)

        extras = self.db.query(ExtraFile).join(
            MediaItem, ExtraFile.media_item_id == MediaItem.id
        ).filter(
            ~MediaItem.status.in_([ItemStatus.IGNORED])
        ).all()

        parent_scan_modes = getattr(self, "_parent_scan_modes", {})
        extra_parent_ids = {ex.media_item_id for ex in extras}
        missing_parent_ids = extra_parent_ids - set(parent_planned_paths.keys())
        if missing_parent_ids:
            missing_parents = self.db.query(MediaItem).options(
                joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations),
                joinedload(MediaItem.overrides)
            ).filter(MediaItem.id.in_(missing_parent_ids)).all()
            for parent in missing_parents:
                parent_planned_paths[parent.id] = parent.planned_path or parent.current_path
                parent_types[parent.id] = self._infer_organizer_type(parent)
                parent_statuses[parent.id] = parent.status.value
                p_scan_mode = str((parent.parsed_info or {}).get("scan_mode") or "").lower()
                parent_scan_modes[parent.id] = p_scan_mode
                if p_scan_mode in {"scenes", "porndb_movie"}:
                    p_is_adult = True
                else:
                    active_match = next((m for m in parent.matches if m.is_active), None) or next((m for m in parent.matches), None)
                    p_is_adult = active_match.is_adult if active_match else False
                parent_is_adults[parent.id] = p_is_adult

        for ex in extras:
            parent_p_path = parent_planned_paths.get(ex.media_item_id) or ""
            groups["extras"].append({
                "id": ex.id,
                "parent_id": ex.media_item_id,
                "parent_type": parent_types.get(ex.media_item_id, "unknown"),
                "parent_status": parent_statuses.get(ex.media_item_id),
                "parent_name": Path(parent_p_path).stem if parent_p_path else ex.media_item.filename,
                "filename": ex.filename,
                "extension": ex.extension,
                "category": ex.category.value,
                "subtype": ex.subtype.value if ex.subtype else "other",
                "language": ex.language,
                "path": ex.current_path,
                "planned_path": str(Path(parent_p_path).parent / ex.filename).replace("\\", "/"),
                "action": "rename",
                "parent_scan_mode": parent_scan_modes.get(ex.media_item_id, ""),
                "parent_is_adult": parent_is_adults.get(ex.media_item_id, False)
            })

        return OrganizerGroupsResponse(**groups)

    def get_organizer_item_count(self, scan_mode: Optional[str] = None, session_mode: Optional[str] = None) -> int:
        items = self.db.query(MediaItem).options(
            joinedload(MediaItem.matches)
        ).filter(
            ~MediaItem.status.in_([ItemStatus.RENAMED, ItemStatus.ORGANIZED, ItemStatus.IGNORED])
        ).all()
        return sum(
            1
            for item in items
            if self._matches_scan_mode_filter((item.parsed_info or {}).get("scan_mode") or "", scan_mode)
            and self._matches_session_mode_filter(item, session_mode)
        )

    def delete_organizer_items(self, item_ids: List[int], extra_ids: List[int], mode: str) -> ActionResponse:
        if mode == "ignore":
            items = self.db.query(MediaItem).filter(MediaItem.id.in_(item_ids)).all()
            for item in items:
                item.status = ItemStatus.IGNORED
            self.db.commit()
            return ActionResponse(status="success", ignored_items=len(item_ids))

        if item_ids:
            self.db.query(MediaItem).filter(MediaItem.id.in_(item_ids)).delete(synchronize_session=False)
        if extra_ids:
            self.db.query(ExtraFile).filter(ExtraFile.id.in_(extra_ids)).delete(synchronize_session=False)
        self.db.commit()
        return ActionResponse(status="success", deleted_items=len(item_ids), deleted_extras=len(extra_ids), mode=mode)
