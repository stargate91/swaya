import os
import logging
import platform
import subprocess
import threading
import time
import requests
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from fastapi.responses import JSONResponse, FileResponse

from app.shared_kernel.enums import Provider, MediaType, ItemStatus
from app.domains.library.models import MediaItem
from app.domains.metadata.models import MetadataMatch, MetadataLocalization
from app.domains.history.models import PlaybackLog
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.language import LanguageService

from app.shared_kernel.constants import PLAYBACK_CHECK_TIMEOUT, DEFAULT_FALLBACK_LANGUAGE
from app.application.media.schemas import (
    PlaybackStatusResponse,
    WatchHistoryResponse,
    WatchedHistoryResponse,
)

from app.shared_kernel.ports.settings_port import SettingsPort

logger = logging.getLogger(__name__)

class PlaybackService:
    def __init__(self, db: Session, settings_port: Optional[SettingsPort] = None, overrides_service: Optional[Any] = None):
        self.db = db
        from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
        self.settings = settings_port or DbSettingsAdapter(db)
        if overrides_service:
            self.overrides = overrides_service
        else:
            from app.domains.users.services.overrides_service import OverridesService
            from app.infrastructure.media.db_media_resolver import DbMediaResolver
            self.overrides = OverridesService(db, DbMediaResolver(db))

    def _resolve_img(self, path: Optional[str], subfolder: str) -> Optional[str]:
        return image_processing_service.resolve_image_url(path, subfolder)


    def _parse_watched_at(self, value) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value
        try:
            normalized = str(value).strip().replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        except Exception as exc:
            raise ValueError("Invalid watched_at datetime format") from exc

    def _serialize_playback_logs(self, item) -> list[dict]:
        logs = sorted(item.playback_logs or [], key=lambda x: x.watched_at, reverse=True)
        return [
            {
                "id": log.id,
                "watched_at": log.watched_at.isoformat(),
            }
            for log in logs
            if getattr(log, "watched_at", None)
        ]

    def _recalculate_watch_state(self, item) -> None:
        logs = sorted(
            [log for log in (item.playback_logs or []) if log.watched_at],
            key=lambda x: x.watched_at,
            reverse=True,
        )
        
        override = self.overrides.get_or_create_media_item_override(item.id)
            
        override.watch_count = len(logs)
        override.last_watched_at = logs[0].watched_at if logs else None
        override.is_watched = bool(logs)
        if logs:
            override.resume_position = 0

    def _watch_history_response(self, item) -> WatchHistoryResponse:
        override = self.overrides.get_or_create_media_item_override(item.id)
        
        return WatchHistoryResponse(
            status="success",
            watch_count=override.watch_count if override else 0,
            is_watched=override.is_watched if override else False,
            resume_position=override.resume_position if override else 0,
            last_watched_at=override.last_watched_at.isoformat() if (override and override.last_watched_at) else None,
            playback_logs=self._serialize_playback_logs(item),
        )

    def play_media_item(self, item_id: Any):
        from app.infrastructure.playback.player_detector import launch_media_file
        from app.infrastructure.playback.playback_monitor import monitor_playback
        db = self.db
        
        try:
            item_id_int = int(item_id)
        except (ValueError, TypeError):
            # Try to resolve prefixed string or external_id
            item_str = str(item_id)
            match_db = None
            
            # Check for tv/tmdb episode ID: provider_tvshowid_season_episode
            # Example: tmdb_12345_1_1
            parts = item_str.split("_")
            if len(parts) >= 4 and parts[0] in {"tmdb", "tv"}:
                try:
                    tv_show_id = parts[1]
                    season_num = int(parts[2])
                    ep_num = int(parts[3])
                    
                    episodes = db.query(MetadataMatch).filter(
                        MetadataMatch.external_id == tv_show_id,
                        MetadataMatch.media_type == MediaType.EPISODE,
                        MetadataMatch.season_number == season_num
                    ).all()
                    
                    for ep in episodes:
                        ep_val = ep.episode_number
                        if ep_val == ep_num:
                            match_db = ep
                            break
                        elif isinstance(ep_val, list) and ep_num in ep_val:
                            match_db = ep
                            break
                        elif isinstance(ep_val, str):
                            try:
                                import json
                                loaded = json.loads(ep_val)
                                if loaded == ep_num or (isinstance(loaded, list) and ep_num in loaded):
                                    match_db = ep
                                    break
                            except:
                                if ep_val == str(ep_num):
                                    match_db = ep
                                    break
                except ValueError:
                    pass
            elif len(parts) == 3:
                try:
                    tv_show_id = parts[0]
                    season_num = int(parts[1])
                    ep_num = int(parts[2])
                    
                    episodes = db.query(MetadataMatch).filter(
                        MetadataMatch.external_id == tv_show_id,
                        MetadataMatch.media_type == MediaType.EPISODE,
                        MetadataMatch.season_number == season_num
                    ).all()
                    
                    for ep in episodes:
                        ep_val = ep.episode_number
                        if ep_val == ep_num:
                            match_db = ep
                            break
                        elif isinstance(ep_val, list) and ep_num in ep_val:
                            match_db = ep
                            break
                        elif isinstance(ep_val, str):
                            try:
                                import json
                                loaded = json.loads(ep_val)
                                if loaded == ep_num or (isinstance(loaded, list) and ep_num in loaded):
                                    match_db = ep
                                    break
                            except:
                                if ep_val == str(ep_num):
                                    match_db = ep
                                    break
                except ValueError:
                    pass

            if not match_db and "_" in item_str:
                parts = item_str.split("_", 1)
                uuid_or_id = parts[1]
                match_db = db.query(MetadataMatch).filter(
                    (MetadataMatch.external_id == uuid_or_id) | (MetadataMatch.id == uuid_or_id)
                ).first()
            
            if not match_db:
                match_db = db.query(MetadataMatch).filter(
                    (MetadataMatch.external_id == item_str) | (MetadataMatch.id == item_str)
                ).first()
                
            if match_db and match_db.media_item_id:
                item_id_int = match_db.media_item_id
            else:
                return JSONResponse(status_code=404, content={"error": f"Media item not found for ID: {item_id}"})

        item = db.query(MediaItem).filter(MediaItem.id == item_id_int).first()
        if not item:
            return JSONResponse(status_code=404, content={"error": "Media item not found"})

        file_path = item.current_path
        if not file_path or not os.path.exists(file_path):
            return JSONResponse(status_code=404, content={"error": f"Media file not found at: {file_path}"})

        # general stats updates
        override = self.overrides.get_or_create_media_item_override(item_id_int)

        override.last_watched_at = datetime.now(timezone.utc)
        
        # Check if the item has an unfinished session and update/create playback log
        existing_log = None
        if not override.is_watched:
            existing_log = db.query(PlaybackLog).filter(
                PlaybackLog.media_item_id == item.id
            ).order_by(PlaybackLog.watched_at.desc()).first()

        if existing_log:
            existing_log.watched_at = datetime.now(timezone.utc)
        else:
            log_entry = PlaybackLog(media_item_id=item.id, watched_at=datetime.now(timezone.utc))
            db.add(log_entry)
            override.watch_count = (override.watch_count or 0) + 1

        override.is_watched = False
        db.commit()

        start_seconds = override.resume_position or 0
        launch_result = launch_media_file(file_path, db, self.settings, start_seconds=start_seconds)
        proc = launch_result.get("process")
        player_type = launch_result.get("player_type")
        port = launch_result.get("port")

        if proc and player_type in {"vlc", "mpc"}:
            t = threading.Thread(
                target=monitor_playback,
                args=(item.id, player_type, proc, port, self.overrides.user_id),
                daemon=True
            )
            t.start()
            return PlaybackStatusResponse(
                status="success",
                message=f"Launched {player_type.upper()} with precision tracking.",
                player_type=player_type,
                port=port,
                resume_position=override.resume_position,
                is_watched=override.is_watched,
            )

        return PlaybackStatusResponse(
            status="success",
            message=f"Launched default player for {file_path}",
            player_type="default",
            resume_position=override.resume_position,
            is_watched=override.is_watched,
        )

    def preview_media_file(self, file_path: str, start_seconds: int = 0) -> PlaybackStatusResponse:
        from app.infrastructure.playback.player_detector import launch_media_file
        if not file_path or not os.path.exists(file_path):
            return JSONResponse(status_code=404, content={"error": f"Media file not found at: {file_path}"})

        launch_result = launch_media_file(file_path, self.db, self.settings, start_seconds=start_seconds)
        player_type = launch_result.get("player_type") or "default"
        port = launch_result.get("port")
        return PlaybackStatusResponse(
            status="success",
            message=f"Launched {player_type.upper()} preview for {file_path}",
            player_type=player_type,
            port=port,
        )


    def add_watch_history_entry(self, item_id: int, watched_at_raw: Any = None):
        db = self.db
        item = db.query(MediaItem).options(joinedload(MediaItem.playback_logs)).filter(MediaItem.id == item_id).first()
        if not item:
            return JSONResponse(status_code=404, content={"error": "Item not found"})

        watched_at = self._parse_watched_at(watched_at_raw)
        db.add(PlaybackLog(media_item_id=item.id, watched_at=watched_at))
        db.flush()
        db.refresh(item)
        self._recalculate_watch_state(item)
        db.commit()
        db.refresh(item)
        return self._watch_history_response(item)

    def update_watch_history_entry(self, item_id: int, log_id: int, watched_at_raw: Any = None):
        db = self.db
        item = db.query(MediaItem).options(joinedload(MediaItem.playback_logs)).filter(MediaItem.id == item_id).first()
        if not item:
            return JSONResponse(status_code=404, content={"error": "Item not found"})

        log = db.query(PlaybackLog).filter(
            PlaybackLog.id == log_id,
            PlaybackLog.media_item_id == item_id,
        ).first()
        if not log:
            return JSONResponse(status_code=404, content={"error": "Watch history entry not found"})

        log.watched_at = self._parse_watched_at(watched_at_raw)
        db.flush()
        db.refresh(item)
        self._recalculate_watch_state(item)
        db.commit()
        db.refresh(item)
        return self._watch_history_response(item)

    def delete_watch_history_entry(self, item_id: int, log_id: int):
        db = self.db
        item = db.query(MediaItem).options(joinedload(MediaItem.playback_logs)).filter(MediaItem.id == item_id).first()
        if not item:
            return JSONResponse(status_code=404, content={"error": "Item not found"})

        log = db.query(PlaybackLog).filter(
            PlaybackLog.id == log_id,
            PlaybackLog.media_item_id == item_id,
        ).first()
        if not log:
            return JSONResponse(status_code=404, content={"error": "Watch history entry not found"})

        db.delete(log)
        db.flush()
        db.refresh(item)
        self._recalculate_watch_state(item)
        db.commit()
        db.refresh(item)
        return self._watch_history_response(item)

    def reset_item_progress(self, item_id: int) -> PlaybackStatusResponse:
        override = self.overrides.get_or_create_media_item_override(item_id)
        if not override:
            return JSONResponse(status_code=404, content={"error": "Item not found"})

        override.resume_position = 0
        override.is_watched = False
        self.db.commit()
        return PlaybackStatusResponse(
            status="success",
            resume_position=0,
            is_watched=False,
        )

    def get_watched_history(self, page: int = 1, limit: int = 20, include_adult: bool = False) -> WatchedHistoryResponse:
        db = self.db
        offset = (page - 1) * limit
        
        query = db.query(PlaybackLog).join(MediaItem)
        if not include_adult:
            active_adult_match = db.query(MetadataMatch.id).filter(
                MetadataMatch.media_item_id == MediaItem.id,
                MetadataMatch.is_active == True,
                MetadataMatch.is_adult == True,
            ).exists()
            query = query.filter(~active_adult_match)

        logs = query.options(
            joinedload(PlaybackLog.media_item).options(
                joinedload(MediaItem.matches).joinedload(MetadataMatch.localizations)
            )
        ).order_by(PlaybackLog.watched_at.desc()).offset(offset).limit(limit + 1).all()

        has_more = len(logs) > limit
        if has_more:
            logs = logs[:limit]

        results = []
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for log in logs:
            item = log.media_item
            if not item:
                continue

            active_match = next((match for match in item.matches if match.is_active), None)
            loc = LanguageService.get_best_localization(active_match.localizations, ui_lang) if active_match else None
            override = self.overrides.get_or_create_media_item_override(item.id)

            title = loc.title if loc else item.filename
            
            results.append({
                "id": log.id,
                "media_item_id": item.id,
                "watched_at": log.watched_at.isoformat(),
                "title": title,
                "type": item.item_type.value if hasattr(item.item_type, "value") else str(item.item_type),
                "season_number": active_match.season_number if active_match else None,
                "episode_number": active_match.episode_number if active_match else None,
                "poster_path": self._resolve_img(loc.poster_path if loc else None, "posters"),
                "resume_position": override.resume_position if override else 0,
                "duration": item.duration or 0,
                "is_watched": override.is_watched if override else False,
            })

        return WatchedHistoryResponse(
            items=results,
            page=page,
            has_more=has_more
        )

    def reveal_in_explorer(self, path: str) -> PlaybackStatusResponse:
        if not path or not os.path.exists(path):
            return PlaybackStatusResponse(status="error", message=f"Path does not exist: {path}")
        
        path = os.path.abspath(path)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                folder = os.path.dirname(path)
                subprocess.Popen(["xdg-open", folder])
            return PlaybackStatusResponse(status="success")
        except Exception as e:
            logger.error(f"Reveal failed: {e}")
            return PlaybackStatusResponse(status="error", message=str(e))

    def open_path(self, path: str) -> PlaybackStatusResponse:
        if not path or not os.path.exists(path):
            return PlaybackStatusResponse(status="error", message=f"Path does not exist: {path}")

        path = os.path.abspath(path)
        try:
            if platform.system() == "Windows":
                os.startfile(os.path.normpath(path))
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return PlaybackStatusResponse(status="success")
        except Exception as e:
            logger.error(f"Open path failed: {e}")
            return PlaybackStatusResponse(status="error", message=str(e))
