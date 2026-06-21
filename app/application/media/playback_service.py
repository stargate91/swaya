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

from app.core.enums import Provider, MediaType, ItemStatus
from app.domains.media.models.filesystem import MediaItem
from app.domains.media.models.metadata import MetadataMatch, MetadataLocalization
from app.domains.history.models import PlaybackLog
from app.domains.settings.models import UserSetting
from app.core.images import ImageProcessingService
from app.core.language import LanguageService

from app.core.constants import PLAYBACK_CHECK_TIMEOUT, DEFAULT_FALLBACK_LANGUAGE

logger = logging.getLogger(__name__)

class PlaybackService:
    def __init__(self, db: Session):
        self.db = db
        self.img_service = ImageProcessingService()

    def _resolve_img(self, path: Optional[str], subfolder: str) -> Optional[str]:
        if not path:
            return None
        return self.img_service.resolve_image_url(path, subfolder)

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
        db = self.db
        logs = sorted(
            [log for log in (item.playback_logs or []) if log.watched_at],
            key=lambda x: x.watched_at,
            reverse=True,
        )
        
        # In Swaya, watch_count, is_watched, resume_position etc are stored on UserOverride model or directly on MediaItem if applicable.
        # Wait! Let's check e:\projects\python\Swaya\app\domains\users\models.py for UserOverride.
        # UserOverride has user_rating, user_comment, is_favorite, is_watched, last_watched_at, watch_count, resume_position, is_tracked.
        # Let's find/create UserOverride for user_id=1, media_item_id=item.id.
        from app.domains.users.models import UserOverride
        override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item.id).first()
        if not override:
            override = UserOverride(user_id=1, media_item_id=item.id)
            db.add(override)
            
        override.watch_count = len(logs)
        override.last_watched_at = logs[0].watched_at if logs else None
        override.is_watched = bool(logs)
        if logs:
            override.resume_position = 0

    def _watch_history_response(self, item) -> dict:
        db = self.db
        from app.domains.users.models import UserOverride
        override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item.id).first()
        
        return {
            "status": "success",
            "watch_count": override.watch_count if override else 0,
            "is_watched": override.is_watched if override else False,
            "resume_position": override.resume_position if override else 0,
            "last_watched_at": override.last_watched_at.isoformat() if (override and override.last_watched_at) else None,
            "playback_logs": self._serialize_playback_logs(item),
        }

    def find_media_player(self):
        import shutil
        db = self.db

        vlc_path_setting = db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == "vlc_path").first()
        mpc_path_setting = db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == "mpc_path").first()

        vlc_path = vlc_path_setting.value if vlc_path_setting else None
        mpc_path = mpc_path_setting.value if mpc_path_setting else None

        def save_setting(key, val):
            try:
                setting = db.query(UserSetting).filter(UserSetting.user_id == 1, UserSetting.key == key).first()
                if setting:
                    setting.value = val
                else:
                    db.add(UserSetting(user_id=1, key=key, value=val))
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to save player setting {key}: {e}")

        # Detect VLC
        vlc_valid = False
        if vlc_path and os.path.exists(vlc_path):
            vlc_valid = True
        else:
            which_vlc = shutil.which("vlc")
            if which_vlc:
                vlc_path = which_vlc
                vlc_valid = True
            elif platform.system() == "Windows":
                vlc_paths = [
                    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
                ]
                for p in vlc_paths:
                    if os.path.exists(p):
                        vlc_path = p
                        vlc_valid = True
                        break
            if vlc_valid and vlc_path:
                save_setting("vlc_path", vlc_path)

        # Detect MPC-HC
        mpc_valid = False
        if mpc_path and os.path.exists(mpc_path):
            mpc_valid = True
        else:
            which_mpc = shutil.which("mpc-hc") or shutil.which("mpc-hc64")
            if which_mpc:
                mpc_path = which_mpc
                mpc_valid = True
            elif platform.system() == "Windows":
                mpc_paths = [
                    r"C:\Program Files\MPC-HC\mpc-hc64.exe",
                    r"C:\Program Files (x86)\MPC-HC\mpc-hc.exe"
                ]
                for p in mpc_paths:
                    if os.path.exists(p):
                        mpc_path = p
                        mpc_valid = True
                        break
            if mpc_valid and mpc_path:
                save_setting("mpc_path", mpc_path)

        if vlc_valid and vlc_path:
            return vlc_path, "vlc"
        if mpc_valid and mpc_path:
            return mpc_path, "mpc"
        return None, None

    def _launch_media_file(self, file_path: str, start_seconds: int = 0) -> dict:
        normalized_path = os.path.normpath(file_path)
        player_path, player_type = self.find_media_player()

        if player_path and player_type:
            proc = None
            port = 8080 if player_type == "vlc" else 13579

            if player_type == "vlc":
                args = [player_path, normalized_path]
                if start_seconds > 10:
                    args.append(f"--start-time={start_seconds}")
                args.extend(["--no-one-instance", "--extraintf=http", "--http-password=renda", f"--http-port={port}", "--http-host=127.0.0.1"])
                proc = subprocess.Popen(args)
            elif player_type == "mpc":
                args = [player_path, normalized_path]
                if start_seconds > 10:
                    h = start_seconds // 3600
                    m = (start_seconds % 3600) // 60
                    s = start_seconds % 60
                    args.extend(["/startpos", f"{h:02d}:{m:02d}:{s:02d}"])
                proc = subprocess.Popen(args)

            if proc:
                return {
                    "status": "success",
                    "player_type": player_type,
                    "process": proc,
                    "port": port,
                    "message": f"Launched {player_type.upper()} for {normalized_path}",
                }

        logger.info(f"VLC or MPC-HC not found. Falling back to default OS player for: {normalized_path}")
        if platform.system() == "Windows":
            os.startfile(normalized_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", normalized_path])
        else:
            subprocess.Popen(["xdg-open", normalized_path])

        return {
            "status": "success",
            "player_type": "default",
            "process": None,
            "port": None,
            "message": f"Launched default player for {normalized_path}",
        }

    def monitor_playback(self, item_id: int, player_type: str, proc: subprocess.Popen, port: int):
        logger.info(f"Started playback monitoring thread for item_id={item_id}, player={player_type}, port={port}")
        last_saved_time = 0
        total_length = 0
        current_time = 0
        time.sleep(3)
        
        try:
            while proc.poll() is None:
                time.sleep(2)
                try:
                    if player_type == "vlc":
                        r = requests.get(
                            f"http://127.0.0.1:{port}/requests/status.json", 
                            auth=("", "renda"), 
                            timeout=PLAYBACK_CHECK_TIMEOUT
                        )
                        if r.status_code == 200:
                            data = r.json()
                            current_time = int(data.get("time", 0))
                            total_length = int(data.get("length", 0))
                    elif player_type == "mpc":
                        r = requests.get(f"http://127.0.0.1:{port}/variables.html", timeout=PLAYBACK_CHECK_TIMEOUT)
                        if r.status_code == 200:
                            pos_match = re.search(r'id="position">(\d+)</p>', r.text)
                            dur_match = re.search(r'id="duration">(\d+)</p>', r.text)
                            if pos_match:
                                current_time = int(pos_match.group(1)) // 1000
                            if dur_match:
                                total_length = int(dur_match.group(1)) // 1000
                    
                    if current_time > 0 and abs(current_time - last_saved_time) >= 10:
                        last_saved_time = current_time
                        from app.core.database import SessionLocal
                        from app.domains.users.models import UserOverride
                        db_session = SessionLocal()
                        try:
                            item = db_session.query(MediaItem).filter(MediaItem.id == item_id).first()
                            if item:
                                if total_length > 0:
                                    item.duration = total_length
                                override = db_session.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item_id).first()
                                if not override:
                                    override = UserOverride(user_id=1, media_item_id=item_id)
                                    db_session.add(override)
                                override.resume_position = current_time
                                if total_length > 0 and current_time / total_length > 0.90:
                                    override.is_watched = True
                                    override.resume_position = 0
                                db_session.commit()
                        except Exception as ex:
                            db_session.rollback()
                            logger.error(f"Failed to update position: {ex}")
                        finally:
                            db_session.close()
                except Exception as e:
                    logger.debug(f"Polling failed: {e}")
        except Exception as e:
            logger.error(f"Error in monitoring: {e}")
        finally:
            if current_time > 0 and current_time != last_saved_time:
                from app.core.database import SessionLocal
                from app.domains.users.models import UserOverride
                db_session = SessionLocal()
                try:
                    item = db_session.query(MediaItem).filter(MediaItem.id == item_id).first()
                    if item:
                        if total_length > 0:
                            item.duration = total_length
                        override = db_session.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item_id).first()
                        if not override:
                            override = UserOverride(user_id=1, media_item_id=item_id)
                            db_session.add(override)
                        override.resume_position = current_time
                        if total_length > 0 and current_time / total_length > 0.90:
                            override.is_watched = True
                            override.resume_position = 0
                        db_session.commit()
                except Exception as ex:
                    db_session.rollback()
                    logger.error(f"Failed final position save: {ex}")
                finally:
                    db_session.close()

    def play_media_item(self, item_id: int):
        db = self.db
        from app.domains.users.models import UserOverride
        item = db.query(MediaItem).filter(MediaItem.id == item_id).first()
        if not item:
            return JSONResponse(status_code=404, content={"error": "Media item not found"})

        file_path = item.current_path
        if not file_path or not os.path.exists(file_path):
            return JSONResponse(status_code=404, content={"error": f"Media file not found at: {file_path}"})

        # general stats updates
        override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item_id).first()
        if not override:
            override = UserOverride(user_id=1, media_item_id=item_id)
            db.add(override)

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
        launch_result = self._launch_media_file(file_path, start_seconds=start_seconds)
        proc = launch_result.get("process")
        player_type = launch_result.get("player_type")
        port = launch_result.get("port")

        if proc and player_type in {"vlc", "mpc"}:
            t = threading.Thread(
                target=self.monitor_playback,
                args=(item.id, player_type, proc, port),
                daemon=True
            )
            t.start()
            return {"status": "success", "message": f"Launched {player_type.upper()} with precision tracking."}

        return {"status": "success", "message": f"Launched default player for {file_path}"}

    def preview_media_file(self, file_path: str, start_seconds: int = 0):
        if not file_path or not os.path.exists(file_path):
            return JSONResponse(status_code=404, content={"error": f"Media file not found at: {file_path}"})

        launch_result = self._launch_media_file(file_path, start_seconds=start_seconds)
        player_type = launch_result.get("player_type") or "default"
        return {"status": "success", "message": f"Launched {player_type.upper()} preview for {file_path}"}

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

    def reset_item_progress(self, item_id: int):
        db = self.db
        from app.domains.users.models import UserOverride
        override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item_id).first()
        if not override:
            return JSONResponse(status_code=404, content={"error": "Item not found"})

        override.resume_position = 0
        override.is_watched = False
        db.commit()
        return {"status": "success", "resume_position": 0, "is_watched": False}

    def get_watched_history(self, page: int = 1, limit: int = 20, include_adult: bool = False):
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
            from app.domains.users.models import UserOverride
            override = db.query(UserOverride).filter(UserOverride.user_id == 1, UserOverride.media_item_id == item.id).first()

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

        return {
            "items": results,
            "page": page,
            "has_more": has_more
        }

    def reveal_in_explorer(self, path: str):
        if not path or not os.path.exists(path):
            return {"status": "error", "message": f"Path does not exist: {path}"}
        
        path = os.path.abspath(path)
        try:
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{os.path.normpath(path)}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                folder = os.path.dirname(path)
                subprocess.Popen(["xdg-open", folder])
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Reveal failed: {e}")
            return {"status": "error", "message": str(e)}

    def open_path(self, path: str):
        if not path or not os.path.exists(path):
            return {"status": "error", "message": f"Path does not exist: {path}"}

        path = os.path.abspath(path)
        try:
            if platform.system() == "Windows":
                os.startfile(os.path.normpath(path))
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Open path failed: {e}")
            return {"status": "error", "message": str(e)}
