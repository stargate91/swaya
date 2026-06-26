import os
import uuid
import logging
from typing import Dict, Any, Optional

from app.domains.users.models import UserOverride
from app.domains.media_assets.services.images import image_processing_service
from app.shared_kernel.exceptions import NotFoundException, BadRequestException

logger = logging.getLogger(__name__)

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
            try:
                if self.image_downloader:
                    url = self.image_downloader.get_download_url(path, subfolder)
                    if url:
                        import re
                        from urllib.parse import urlparse
                        basename = os.path.basename(urlparse(path).path)
                        ext = os.path.splitext(basename)[1].lower() or ".jpg"
                        prefix = f"user_override_{override.user_id}_{item_id}"
                        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
                        filename = f"{safe_prefix}_{basename}{ext}"
                        self.image_downloader.download_now(url, subfolder, filename)
                        path = f"{subfolder}/{filename}"
                else:
                    logger.warning("No image_downloader available for user override image download")
            except Exception as e:
                logger.error(f"Failed to queue image download for user override: {e}")

        if image_type == "poster":
            override.custom_poster = path
        elif image_type == "backdrop":
            override.custom_backdrop = path
        elif image_type == "logo":
            override.custom_logo = path

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
