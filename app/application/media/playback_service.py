import os
import logging
import platform
import subprocess
import threading
from datetime import datetime
from typing import Optional, Any, List, Dict
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from app.shared_kernel.enums import Provider, MediaType
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.language import LanguageService
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.exceptions import NotFoundException
from app.application.media.schemas import (
    PlaybackStatusResponse,
    WatchHistoryResponse,
    WatchedHistoryResponse,
)
from app.domains.media.services.playback_service import PlaybackService as DomainPlaybackService

logger = logging.getLogger(__name__)


class PlaybackService:
    def __init__(
        self,
        db: Session,
        settings_port: Optional[Any] = None,
        overrides_service: Optional[Any] = None,
        playback_repo: Optional[Any] = None,
        library_port: Optional[Any] = None
    ):
        self.db = db
        from app.infrastructure.settings.db_settings_adapter import DbSettingsAdapter
        self.settings = settings_port or DbSettingsAdapter(db)
        self.domain_service = DomainPlaybackService(
            db=db,
            overrides_service=overrides_service,
            playback_repo=playback_repo,
            library_port=library_port,
        )

    def _resolve_img(self, path: Optional[str], subfolder: str) -> Optional[str]:
        return image_processing_service.resolve_image_url(path, subfolder)

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

    def _watch_history_response(self, item) -> WatchHistoryResponse:
        override = self.domain_service.overrides.get_or_create_media_item_override(item.id)
        
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

        try:
            item, override, start_seconds = self.domain_service.track_playback_start(item_id)
        except NotFoundException as e:
            return JSONResponse(status_code=404, content={"error": str(e)})

        file_path = item.current_path
        launch_result = launch_media_file(file_path, self.settings, start_seconds=start_seconds)
        proc = launch_result.get("process")
        player_type = launch_result.get("player_type")
        port = launch_result.get("port")

        if proc and player_type in {"vlc", "mpc"}:
            t = threading.Thread(
                target=monitor_playback,
                args=(item.id, player_type, proc, port, self.domain_service.overrides.user_id),
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

        launch_result = launch_media_file(file_path, self.settings, start_seconds=start_seconds)
        player_type = launch_result.get("player_type") or "default"
        port = launch_result.get("port")
        return PlaybackStatusResponse(
            status="success",
            message=f"Launched {player_type.upper()} preview for {file_path}",
            player_type=player_type,
            port=port,
        )

    def add_watch_history_entry(self, item_id: int, watched_at_raw: Any = None):
        try:
            item = self.domain_service.add_watch_history_entry(item_id, watched_at_raw)
            return self._watch_history_response(item)
        except NotFoundException as e:
            return JSONResponse(status_code=404, content={"error": str(e)})

    def update_watch_history_entry(self, item_id: int, log_id: int, watched_at_raw: Any = None):
        try:
            item = self.domain_service.update_watch_history_entry(item_id, log_id, watched_at_raw)
            return self._watch_history_response(item)
        except NotFoundException as e:
            return JSONResponse(status_code=404, content={"error": str(e)})

    def delete_watch_history_entry(self, item_id: int, log_id: int):
        try:
            item = self.domain_service.delete_watch_history_entry(item_id, log_id)
            return self._watch_history_response(item)
        except NotFoundException as e:
            return JSONResponse(status_code=404, content={"error": str(e)})

    def reset_item_progress(self, item_id: int) -> PlaybackStatusResponse:
        try:
            resume_pos, is_watched = self.domain_service.reset_item_progress(item_id)
            return PlaybackStatusResponse(
                status="success",
                resume_position=resume_pos,
                is_watched=is_watched,
            )
        except NotFoundException as e:
            return JSONResponse(status_code=404, content={"error": str(e)})

    def get_watched_history(self, page: int = 1, limit: int = 20, include_adult: bool = False) -> WatchedHistoryResponse:
        logs, has_more = self.domain_service.get_watched_history_logs(page, limit, include_adult)

        results = []
        ui_lang = DEFAULT_FALLBACK_LANGUAGE
        for log in logs:
            item = log.media_item
            if not item:
                continue

            active_match = next((match for match in item.matches if match.is_active), None)
            loc = LanguageService.get_best_localization(active_match.localizations, ui_lang) if active_match else None
            override = self.domain_service.overrides.get_or_create_media_item_override(item.id)

            title = loc.title if loc else item.filename
            
            from app.infrastructure.playback.playback_monitor import active_sessions
            is_active = item.id in active_sessions
            
            results.append({
                "id": log.id,
                "media_item_id": item.id,
                "watched_at": log.watched_at.isoformat(),
                "title": title,
                "type": active_match.media_type.value if (active_match and hasattr(active_match.media_type, "value")) else (str(active_match.media_type) if active_match else "movie"),
                "season_number": active_match.season_number if active_match else None,
                "episode_number": active_match.episode_number if active_match else None,
                "poster_path": self._resolve_img(loc.poster_path if loc else None, "posters"),
                "backdrop_path": self._resolve_img(active_match.backdrop_path if active_match else None, "backdrops"),
                "resume_position": override.resume_position if override else 0,
                "duration": int(item.duration) if item.duration else 0,
                "is_watched": override.is_watched if override else False,
                "is_active": is_active,
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
