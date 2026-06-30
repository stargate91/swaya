import logging
import os
import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domains.people.models import Person
from app.shared_kernel.user_context import get_current_user_id
from app.shared_kernel.ports.library_port import LibraryPort
from app.shared_kernel.ports.image_service_port import ImageServicePort

logger = logging.getLogger(__name__)

def fnv1a_hash(s: str) -> str:
    hash_val = 2166136261
    for char in s.encode('utf-8'):
        hash_val ^= char
        hash_val = (hash_val * 16777619) & 0xffffffff
    return f"{hash_val:08x}"

class PerformerAssetManager:
    def __init__(self, db: Session, library_port: LibraryPort, image_service: ImageServicePort):
        self.db = db
        self.library_port = library_port
        self.image_service = image_service

    def _resolve_img(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        return self.image_service.resolve_image_url(path, subfolder, size)

    def update_person_backdrop(self, person_id: int, backdrop_path: str) -> Dict[str, Any]:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1
        
        if backdrop_path and (backdrop_path.startswith("/") or backdrop_path.startswith(("http://", "https://"))):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(backdrop_path)
            is_local = False
            if "127.0.0.1" in parsed.netloc or "localhost" in parsed.netloc:
                is_local = True
            elif backdrop_path.startswith("/media/") or backdrop_path.startswith("media/"):
                is_local = True

            if is_local:
                query_params = parse_qs(parsed.query)
                if "url" in query_params:
                    backdrop_path = query_params["url"][0]
                else:
                    backdrop_path = os.path.basename(parsed.path)

        if backdrop_path and (backdrop_path.startswith("/") or backdrop_path.startswith(("http://", "https://"))):
            try:
                from app.infrastructure.tasks.tasks_image_download_adapter import TasksImageDownloadAdapter
                downloader = TasksImageDownloadAdapter()
                url = downloader.get_download_url(backdrop_path, "backdrops")
                if url:
                    import re
                    from urllib.parse import urlparse
                    basename = os.path.basename(urlparse(backdrop_path).path)
                    name, ext = os.path.splitext(basename)
                    ext = ext.lower() or ".jpg"
                    url_hash = fnv1a_hash(url)
                    prefix = f"user_override_{user_id}_person_backdrop_{person_id}"
                    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
                    filename = f"{safe_prefix}_{name}_{url_hash}{ext}"
                    
                    import threading
                    def bg_download():
                        try:
                            downloader.download_now(url, "backdrops", filename)
                            from app.shared_kernel.database import SessionLocal
                            from app.domains.users.models import UserOverride
                            db_bg = SessionLocal()
                            try:
                                override = db_bg.query(UserOverride).filter(UserOverride.person_id == person_id).first()
                                if override:
                                    override.custom_backdrop = filename
                                    db_bg.commit()
                            finally:
                                db_bg.close()
                        except Exception as e:
                            logger.error(f"Failed to download person backdrop in bg: {e}")
                    threading.Thread(target=bg_download, daemon=True).start()
            except Exception as e:
                logger.error(f"Failed to download person backdrop override image: {e}")

        self.library_port.update_person_user_override(
            user_id=user_id,
            person_id=person_id,
            custom_backdrop=backdrop_path,
            update_backdrop=True
        )
        db.commit()

        # Mark person as active on user interaction
        person.is_active = True
        db.commit()

        return {
            "status": "success",
            "backdrop_path": self._resolve_img(backdrop_path, "backdrops", size="original"),
            "has_local_backdrop": bool(backdrop_path)
        }

    def handle_person_backdrop_upload(self, person_id: int, filename: str, file_stream) -> Dict[str, Any]:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1

        img_service = self.image_service
        img_service.ensure_folders()

        ext = os.path.splitext(filename)[1] or ".jpg"
        new_filename = f"upload_{uuid.uuid4().hex}{ext}"
        original_path = img_service.get_original_path("backdrops", new_filename)
        thumbnail_path = img_service.get_thumbnail_path("backdrops", new_filename)

        saved_path = img_service.write_upload(original_path, file_stream)
        if not saved_path:
            raise HTTPException(status_code=400, detail="Failed to save uploaded image")

        img_service.generate_thumbnail(original_path, thumbnail_path, "backdrops")

        self.library_port.update_person_user_override(
            user_id=user_id,
            person_id=person_id,
            custom_backdrop=new_filename,
            update_backdrop=True
        )
        person.is_active = True
        db.commit()

        resolved_url = img_service.resolve_image_url(new_filename, "backdrops", size="original")
        return {"status": "success", "backdrop_path": resolved_url, "has_local_backdrop": True}

    def update_person_profile(self, person_id: int, profile_path: str) -> Dict[str, Any]:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1
        
        if profile_path and (profile_path.startswith("/") or profile_path.startswith(("http://", "https://"))):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(profile_path)
            is_local = False
            if "127.0.0.1" in parsed.netloc or "localhost" in parsed.netloc:
                is_local = True
            elif profile_path.startswith("/media/") or profile_path.startswith("media/"):
                is_local = True

            if is_local:
                query_params = parse_qs(parsed.query)
                if "url" in query_params:
                    profile_path = query_params["url"][0]
                else:
                    profile_path = os.path.basename(parsed.path)

        if profile_path and (profile_path.startswith("/") or profile_path.startswith(("http://", "https://"))):
            try:
                from app.infrastructure.tasks.tasks_image_download_adapter import TasksImageDownloadAdapter
                downloader = TasksImageDownloadAdapter()
                url = downloader.get_download_url(profile_path, "people")
                if url:
                    import re
                    from urllib.parse import urlparse
                    basename = os.path.basename(urlparse(profile_path).path)
                    name, ext = os.path.splitext(basename)
                    ext = ext.lower() or ".jpg"
                    url_hash = fnv1a_hash(url)
                    prefix = f"user_override_{user_id}_person_{person_id}"
                    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
                    filename = f"{safe_prefix}_{name}_{url_hash}{ext}"
                    
                    import threading
                    def bg_download():
                        try:
                            downloader.download_now(url, "people", filename)
                            from app.shared_kernel.database import SessionLocal
                            from app.domains.users.models import UserOverride
                            db_bg = SessionLocal()
                            try:
                                override = db_bg.query(UserOverride).filter(UserOverride.person_id == person_id).first()
                                if override:
                                    override.custom_poster = filename
                                    db_bg.commit()
                            finally:
                                db_bg.close()
                        except Exception as e:
                            logger.error(f"Failed to download person profile in bg: {e}")
                    threading.Thread(target=bg_download, daemon=True).start()
            except Exception as e:
                logger.error(f"Failed to download person profile override image: {e}")

        self.library_port.update_person_user_override(
            user_id=user_id,
            person_id=person_id,
            custom_poster=profile_path,
            update_poster=True
        )
        person.is_active = True
        db.commit()

        return {
            "status": "success",
            "profile_path": self._resolve_img(profile_path, "people"),
            "has_local_profile": bool(profile_path)
        }

    def handle_person_profile_upload(self, person_id: int, filename: str, file_stream) -> Dict[str, Any]:
        db = self.db
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")

        user_id = get_current_user_id() or 1

        img_service = self.image_service
        img_service.ensure_folders()

        ext = os.path.splitext(filename)[1] or ".jpg"
        new_filename = f"upload_{uuid.uuid4().hex}{ext}"
        original_path = img_service.get_original_path("people", new_filename)
        thumbnail_path = img_service.get_thumbnail_path("people", new_filename)

        saved_path = img_service.write_upload(original_path, file_stream)
        if not saved_path:
            raise HTTPException(status_code=400, detail="Failed to save uploaded image")

        img_service.generate_thumbnail(original_path, thumbnail_path, "people")

        self.library_port.update_person_user_override(
            user_id=user_id,
            person_id=person_id,
            custom_poster=new_filename,
            update_poster=True
        )
        person.is_active = True
        db.commit()

        resolved_url = img_service.resolve_image_url(new_filename, "people")
        return {"status": "success", "profile_path": resolved_url, "has_local_profile": True}
