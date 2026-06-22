import os
import shutil
import platform
import logging
import json
import requests
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import or_


from app.domains.settings.models import UserSetting, SystemSetting
from app.domains.library.models import MediaItem
from app.shared_kernel.enums import ItemStatus, MediaType
from app.shared_kernel.constants import STASHDB_DEFAULT_ENDPOINT, FANSDB_DEFAULT_ENDPOINT, PORNDB_DEFAULT_ENDPOINT
from app.domains.media_assets.services.images import image_processing_service

logger = logging.getLogger(__name__)

class SettingsService:
    def __init__(self, db: Session, user_id: Optional[int] = None):
        self.db = db
        if user_id is None:
            from app.shared_kernel.user_context import get_current_user_id
            user_id = get_current_user_id()
        self.user_id = user_id


    def get_settings(self) -> Dict[str, Any]:

        # Auto-detect VLC path
        vlc_setting = self.db.query(UserSetting).filter(UserSetting.user_id == self.user_id, UserSetting.key == "vlc_path").first()
        if not vlc_setting or not vlc_setting.value:
            vlc_path = ""
            which_vlc = shutil.which("vlc")
            if which_vlc:
                vlc_path = which_vlc
            elif platform.system() == "Windows":
                for p in [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]:
                    if os.path.exists(p):
                        vlc_path = p
                        break
            if not vlc_setting:
                vlc_setting = UserSetting(user_id=self.user_id, key="vlc_path", value=vlc_path)
                self.db.add(vlc_setting)
            else:
                vlc_setting.value = vlc_path
            self.db.commit()

        # Auto-detect MPC path
        mpc_setting = self.db.query(UserSetting).filter(UserSetting.user_id == self.user_id, UserSetting.key == "mpc_path").first()
        if not mpc_setting or not mpc_setting.value:
            mpc_path = ""
            which_mpc = shutil.which("mpc-hc") or shutil.which("mpc-hc64")
            if which_mpc:
                mpc_path = which_mpc
            elif platform.system() == "Windows":
                for p in [r"C:\Program Files\MPC-HC\mpc-hc64.exe", r"C:\Program Files (x86)\MPC-HC\mpc-hc.exe"]:
                    if os.path.exists(p):
                        mpc_path = p
                        break
            if not mpc_setting:
                mpc_setting = UserSetting(user_id=self.user_id, key="mpc_path", value=mpc_path)
                self.db.add(mpc_setting)
            else:
                mpc_setting.value = mpc_path
            self.db.commit()

        settings = self.db.query(UserSetting).filter(UserSetting.user_id == self.user_id).all()
        return {s.key: s.value for s in settings}

    def update_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:

        for key, value in settings.items():
            setting = self.db.query(UserSetting).filter(UserSetting.user_id == self.user_id, UserSetting.key == key).first()
            if setting:
                setting.value = value
            else:
                setting = UserSetting(user_id=self.user_id, key=key, value=value)
                self.db.add(setting)
        self.db.commit()
        return {"status": "success"}

    def upload_avatar(self, filename: str, file_stream) -> Dict[str, str]:
        extension = Path(filename or "").suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            raise ValueError("Unsupported image format")

        image_service = image_processing_service
        avatar_filename = f"user_{self.user_id}_{uuid.uuid4().hex}{extension}"
        original_path = image_service.get_original_path("avatars", avatar_filename)
        thumbnail_path = image_service.get_thumbnail_path("avatars", avatar_filename)

        if not image_service.write_upload(original_path, file_stream):
            raise ValueError("Invalid image file")
        if not image_service.generate_thumbnail(original_path, thumbnail_path, "avatars"):
            original_path.unlink(missing_ok=True)
            raise ValueError("Failed to process avatar")

        avatar_path = image_service.resolve_image_url(avatar_filename, "avatars")
        setting = self.db.query(UserSetting).filter(
            UserSetting.user_id == self.user_id,
            UserSetting.key == "avatar_path",
        ).first()
        if setting:
            setting.value = avatar_path
        else:
            self.db.add(UserSetting(user_id=self.user_id, key="avatar_path", value=avatar_path))
        self.db.commit()
        return {"avatar_path": avatar_path}
    def validate_folders(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        scan_dir = (payload.get("default_scan_dir") or "").strip()
        library_dir = (payload.get("folder_library_path") or "").strip()
        move_to_library = bool(payload.get("folder_move_to_library"))

        errors = {}
        if scan_dir and not os.path.exists(scan_dir):
            errors["scanFolder"] = "scanDirNotExist"

        if move_to_library:
            if not library_dir:
                errors["targetFolder"] = "libraryDirRequired"
            elif not os.path.exists(library_dir):
                errors["targetFolder"] = "libraryDirNotExist"
            elif scan_dir and os.path.abspath(scan_dir) == os.path.abspath(library_dir):
                errors["targetFolder"] = "foldersCannotBeSame"

        if errors:
            return {"valid": False, "errors": errors}
        return {"valid": True, "message": "foldersVerified"}

    def get_changelog(self) -> Dict[str, Any]:
        changelog_path = Path("CHANGELOG.md")
        if changelog_path.exists():
            return {"status": "success", "content": changelog_path.read_text(encoding="utf-8")}
        return {"status": "error", "message": "CHANGELOG.md not found.", "content": ""}

    def get_ignored_items(self, search: str = "", offset: int = 0, limit: int = 40) -> Dict[str, Any]:
        query = self.db.query(MediaItem).filter(MediaItem.status == ItemStatus.IGNORED)
        if search:
            pattern = f"%{search}%"
            query = query.filter(MediaItem.filename.ilike(pattern))
            
        total = query.count()
        items = query.order_by(MediaItem.ignored_at.desc()).offset(offset).limit(limit).all()
        
        serialized = [{
            "id": item.id,
            "filename": item.filename,
            "current_path": item.current_path,
            "item_type": item.matches[0].media_type.value if item.matches else None,
            "status": item.status.value,
            "ignored_at": item.ignored_at.isoformat() if item.ignored_at else None,
        } for item in items]
        
        return {
            "items": serialized,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(items) < total,
        }

    def restore_ignored_items(self, item_ids: List[int]) -> Dict[str, Any]:
        items = self.db.query(MediaItem).filter(MediaItem.id.in_(item_ids), MediaItem.status == ItemStatus.IGNORED).all()
        for item in items:
            item.status = item.ignored_previous_status or ItemStatus.NEW
            item.ignored_previous_status = None
            item.ignored_at = None
        self.db.commit()
        return {"status": "success", "restored": len(items)}

    def validate_api_keys(self, payload: dict) -> Dict[str, Any]:
        tmdb_api_key = (payload.get("tmdb_api_key") or "").strip()
        tmdb_bearer_token = (payload.get("tmdb_bearer_token") or "").strip()
        omdb_api_key = (payload.get("omdb_api_key") or "").strip()
        stashdb_api_key = (payload.get("stashdb_api_key") or "").strip()
        fansdb_api_key = (payload.get("fansdb_api_key") or "").strip()
        porndb_api_key = (payload.get("porndb_api_key") or "").strip()
        stashdb_endpoint = (payload.get("stashdb_endpoint") or STASHDB_DEFAULT_ENDPOINT).strip()
        fansdb_endpoint = (payload.get("fansdb_endpoint") or FANSDB_DEFAULT_ENDPOINT).strip()
        porndb_endpoint = (payload.get("porndb_endpoint") or PORNDB_DEFAULT_ENDPOINT).strip()

        result = {
            "tmdb": {"valid": False, "message": None},
            "omdb": {"valid": False, "message": None},
            "stashdb": {"valid": False, "message": None},
            "fansdb": {"valid": False, "message": None},
            "porndb": {"valid": False, "message": None},
        }

        def validate_graphql_provider(provider_key: str, endpoint: str, api_key: str, use_bearer: bool = False) -> Dict[str, Any]:
            if not api_key:
                return {"valid": False, "message": None}

            headers = {"Content-Type": "application/json"}
            if use_bearer:
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers["ApiKey"] = api_key

            payload = {
                "query": """
                query ValidateAdultProvider($term: String!) {
                  searchScene(term: $term) {
                    id
                  }
                }
                """,
                "variables": {"term": "validation_probe"},
            }

            try:
                response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
                if response.status_code in (401, 403):
                    return {
                        "valid": False,
                        "code": "adultApiKeyInvalid",
                        "provider": provider_key,
                    }

                response.raise_for_status()
                response_data = response.json()
                if response_data.get("errors"):
                    return {
                        "valid": False,
                        "code": "adultValidationFailedEndpointApiKey",
                        "provider": provider_key,
                    }
                return {"valid": True}
            except requests.Timeout:
                return {
                    "valid": False,
                    "code": "adultValidationTimedOut",
                    "provider": provider_key,
                }
            except requests.RequestException:
                return {
                    "valid": False,
                    "code": "adultValidationFailedEndpoint",
                    "provider": provider_key,
                }

        if tmdb_api_key or tmdb_bearer_token:
            if not tmdb_api_key or not tmdb_bearer_token:
                result["tmdb"]["message"] = "Both TMDB API Key (v3) and Read Access Token (v4) are required."
            else:
                try:
                    key_response = requests.get(
                        "https://api.themoviedb.org/3/configuration",
                        params={"api_key": tmdb_api_key},
                        timeout=15,
                    )
                    if key_response.status_code == 401:
                        result["tmdb"]["message"] = "The TMDB API Key (v3) is invalid."
                    else:
                        key_response.raise_for_status()
                        token_response = requests.get(
                            "https://api.themoviedb.org/3/authentication",
                            headers={"Authorization": f"Bearer {tmdb_bearer_token}"},
                            timeout=15,
                        )
                        if token_response.status_code == 401:
                            result["tmdb"]["message"] = "The TMDB Read Access Token (v4) is invalid."
                        else:
                            token_response.raise_for_status()
                            result["tmdb"] = {"valid": True, "message": "TMDB credentials verified."}
                except requests.Timeout:
                    result["tmdb"]["message"] = "TMDB validation timed out. Check your connection and try again."
                except requests.RequestException:
                    result["tmdb"]["message"] = "TMDB validation failed. Check your connection and try again."

        if omdb_api_key:
            try:
                omdb_response = requests.get(
                    "https://www.omdbapi.com/",
                    params={"apikey": omdb_api_key, "i": "tt0111161"},
                    timeout=15,
                )
                omdb_response.raise_for_status()
                omdb_data = omdb_response.json()
                if omdb_data.get("Response") == "True":
                    result["omdb"] = {"valid": True, "message": "OMDb API key verified."}
                else:
                    error_message = omdb_data.get("Error") or "OMDb validation failed."
                    result["omdb"]["message"] = error_message
            except requests.Timeout:
                result["omdb"]["message"] = "OMDb validation timed out. Check your connection and try again."
            except requests.RequestException:
                result["omdb"]["message"] = "OMDb validation failed. Check your connection and try again."

        result["stashdb"] = validate_graphql_provider("stashdb", stashdb_endpoint, stashdb_api_key)
        result["fansdb"] = validate_graphql_provider("fansdb", fansdb_endpoint, fansdb_api_key)
        result["porndb"] = validate_graphql_provider("porndb", porndb_endpoint, porndb_api_key, use_bearer=True)

        return result
