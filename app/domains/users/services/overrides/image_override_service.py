import os
import uuid
import logging
from typing import Dict, Any, Optional

from app.domains.users.models import UserOverride
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.exceptions import NotFoundException, BadRequestException

logger = logging.getLogger(__name__)

def fnv1a_hash(s: str) -> str:
    hash_val = 2166136261
    for char in s.encode('utf-8'):
        hash_val ^= char
        hash_val = (hash_val * 16777619) & 0xffffffff
    return f"{hash_val:08x}"

class ImageOverrideService:
    def __init__(self, parent_service):
        self.service = parent_service

    @property
    def db(self):
        return self.service.db

    @property
    def image_downloader(self):
        return self.service.image_downloader

    def update_item_image(self, item_id: str, image_type: str, path: str, media_type: Optional[str] = None) -> Dict[str, Any]:
        override = self.service._get_or_create_override(item_id, media_type=media_type)
        if not override:
            raise NotFoundException("Target item not found")

        if image_type not in ("poster", "backdrop", "logo"):
            raise BadRequestException(f"Invalid image type: {image_type}")

        subfolder = "posters"
        if image_type == "backdrop":
            subfolder = "backdrops"
        elif image_type == "logo":
            subfolder = "logos"

        if path and (path.startswith("/") or path.startswith(("http://", "https://"))):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(path)
            is_local = False
            if "127.0.0.1" in parsed.netloc or "localhost" in parsed.netloc:
                is_local = True
            elif path.startswith("/media/") or path.startswith("media/"):
                is_local = True

            if is_local:
                query_params = parse_qs(parsed.query)
                if "url" in query_params:
                    path = query_params["url"][0]
                else:
                    import re
                    match = re.search(r"/(?:original|thumbnails)/([^/]+/[^/]+)$", parsed.path)
                    if match:
                        path = match.group(1)
                    else:
                        path = os.path.basename(parsed.path)

        if path and (path.startswith("/") or path.startswith(("http://", "https://"))):
            try:
                if self.image_downloader:
                    url = self.image_downloader.get_download_url(path, subfolder)
                    if url:
                        import re
                        from urllib.parse import urlparse
                        basename = os.path.basename(urlparse(path).path)
                        name, ext = os.path.splitext(basename)
                        ext = ext.lower() or ".jpg"
                        url_hash = fnv1a_hash(url)
                        prefix = f"user_override_{override.user_id}_{item_id}"
                        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
                        filename = f"{safe_prefix}_{name}_{url_hash}{ext}"
                        
                        import threading
                        override_id = override.id
                        def bg_download():
                            try:
                                downloaded_filename = self.image_downloader.download_now(url, subfolder, filename)
                                if downloaded_filename:
                                    from app.shared_kernel.database import SessionLocal
                                    from app.domains.users.models import UserOverride
                                    db_bg = SessionLocal()
                                    try:
                                        override_bg = db_bg.query(UserOverride).filter(UserOverride.id == override_id).first()
                                        if override_bg:
                                            local_path = f"{subfolder}/{downloaded_filename}"
                                            if image_type == "poster":
                                                override_bg.custom_poster = local_path
                                            elif image_type == "backdrop":
                                                override_bg.custom_backdrop = local_path
                                            elif image_type == "logo":
                                                override_bg.custom_logo = local_path
                                            db_bg.commit()
                                    finally:
                                        db_bg.close()
                            except Exception as e:
                                logger.error(f"Failed to download generic override image in bg: {e}")
                        threading.Thread(target=bg_download, daemon=True).start()
                else:
                    logger.warning("No image_downloader available for user override image download")
            except Exception as e:
                logger.error(f"Failed to queue image download for user override: {e}")

        if image_type == "poster":
            override.custom_poster = path if path else None
        elif image_type == "backdrop":
            override.custom_backdrop = path if path else None
        elif image_type == "logo":
            override.custom_logo = path if path else None

        logger.info(f"[IMAGE_OVERRIDE] Saved override for item {item_id}: image_type={image_type}, path={path}, custom_logo={override.custom_logo}")
        self.db.commit()
        return {"status": "success", "image_type": image_type, "path": path}

    def handle_image_upload(self, item_id: str, image_type: str, filename: str, file_stream, media_type: Optional[str] = None) -> Dict[str, Any]:
        override = self.service._get_or_create_override(item_id, media_type=media_type)
        if not override:
            raise NotFoundException("Target item not found")

        subfolder = "posters"
        if image_type == "backdrop":
            subfolder = "backdrops"
        elif image_type == "logo":
            subfolder = "logos"

        img_service = image_processing_service
        img_service.ensure_folders()

        ext = os.path.splitext(filename)[1] or ".jpg"
        new_filename = f"upload_{uuid.uuid4().hex}{ext}"
        original_path = img_service.get_original_path(subfolder, new_filename)
        thumbnail_path = img_service.get_thumbnail_path(subfolder, new_filename)

        saved_path = img_service.write_upload(original_path, file_stream)
        if not saved_path:
            raise BadRequestException("Failed to save uploaded image")

        img_service.generate_thumbnail(original_path, thumbnail_path, subfolder)

        relative_path_for_db = new_filename
        if image_type == "poster":
            override.custom_poster = relative_path_for_db
        elif image_type == "backdrop":
            override.custom_backdrop = relative_path_for_db
        elif image_type == "logo":
            override.custom_logo = relative_path_for_db

        self.db.commit()
        
        resolved_url = img_service.resolve_image_url(relative_path_for_db, subfolder)
        return {"status": "success", "path": relative_path_for_db, "url": resolved_url}
