import re
import os
from pathlib import Path
from urllib.parse import urlparse
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.domains.metadata.models import MetadataMatch, Studio
from app.shared_kernel.ports.metadata_repository_port import MetadataRepositoryPort

logger = logging.getLogger(__name__)

def _detect_remote_image_extension(url: str, fallback_name: str = "") -> str:
    fallback_ext = Path(urlparse(fallback_name).path).suffix.lower()
    if fallback_ext in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'}:
        return '.jpg' if fallback_ext == '.jpeg' else fallback_ext

    def from_content_type(content_type: str) -> Optional[str]:
        value = (content_type or '').lower()
        if 'image/svg+xml' in value or 'svg' in value:
            return '.svg'
        if 'image/png' in value or 'png' in value:
            return '.png'
        if 'image/webp' in value or 'webp' in value:
            return '.webp'
        if 'image/gif' in value or 'gif' in value:
            return '.gif'
        if 'image/jpeg' in value or 'image/jpg' in value or 'jpeg' in value or 'jpg' in value:
            return '.jpg'
        return None

    def from_bytes(data: bytes) -> Optional[str]:
        sample = (data or b'').lstrip()
        if sample.startswith(b'\x89PNG\r\n\x1a\n'):
            return '.png'
        if sample.startswith(b'GIF87a') or sample.startswith(b'GIF89a'):
            return '.gif'
        if sample.startswith(b'\xff\xd8\xff'):
            return '.jpg'
        if sample.startswith(b'RIFF') and b'WEBP' in sample[:16]:
            return '.webp'
        lowered = sample[:4096].lower()
        if lowered.startswith(b'<?xml') or lowered.startswith(b'<svg') or b'<svg' in lowered:
            return '.svg'
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        import requests
        resp = requests.head(url, headers=headers, timeout=3, allow_redirects=True)
        ext = from_content_type(resp.headers.get('Content-Type', ''))
        if ext:
            return ext
    except Exception:
        pass

    try:
        import requests
        resp = requests.get(url, headers=headers, timeout=5, allow_redirects=True, stream=True)
        ext = from_content_type(resp.headers.get('Content-Type', ''))
        if ext:
            resp.close()
            return ext

        for chunk in resp.iter_content(chunk_size=4096):
            if chunk:
                ext = from_bytes(chunk)
                resp.close()
                if ext:
                    return ext
                break
        resp.close()
    except Exception:
        pass

    return '.jpg'

class StudioPersister:
    def __init__(self, parent_persister):
        self.persister = parent_persister

    @property
    def db(self) -> Session:
        return self.persister.db

    @property
    def metadata_repo(self) -> MetadataRepositoryPort:
        return self.persister.metadata_repo

    @property
    def image_downloader(self):
        return self.persister.image_downloader

    def _local_image_exists(self, path: Optional[str], subfolder: str) -> bool:
        return bool(path and path.startswith(f"{subfolder}/"))

    def queue_studio_logo(self, studio: Studio) -> None:
        """Queues studio logo downloads."""
        if not studio or not studio.logo_path:
            return
        if studio.logo_path.startswith("logos/") and self._local_image_exists(studio.logo_path, "logos"):
            return

        url = self.image_downloader.get_download_url(studio.logo_path, "logos")
        if not url:
            return

        basename = os.path.basename(urlparse(studio.logo_path).path)
        if not basename:
            return

        ext = _detect_remote_image_extension(url, studio.logo_path)
        basename_root = Path(basename).stem or basename
        basename = f"{basename_root}{ext}"

        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", studio.name).strip("_")
        filename = f"studio_{safe_name}_{basename}"
        studio.logo_path = f"logos/{filename}"
        self.image_downloader.enqueue_download(url, "logos", filename)

    def persist_studios(self, studios_info: List[Dict[str, Any]], match: MetadataMatch):
        for studio_info in studios_info:
            s_name = studio_info["name"]
            studio = self.metadata_repo.get_studio_by_name(s_name)
            if not studio:
                try:
                    with self.db.begin_nested():
                        studio = self.metadata_repo.create_studio(name=s_name, logo_path=studio_info["logo_path"])
                        self.metadata_repo.flush()
                except Exception:
                    studio = self.metadata_repo.get_studio_by_name(s_name)
            elif studio_info.get("logo_path") and (
                not studio.logo_path 
                or not self._local_image_exists(studio.logo_path, "logos")
                or (studio.logo_path.startswith("logos/") and studio.logo_path.lower().endswith((".jpg", ".jpeg")))
            ):
                studio.logo_path = studio_info["logo_path"]
            
            # Map parent studio
            parent_info = studio_info.get("parent")
            if parent_info:
                p_name = parent_info["name"]
                parent_studio = self.metadata_repo.get_studio_by_name(p_name)
                if not parent_studio:
                    try:
                        with self.db.begin_nested():
                            parent_studio = self.metadata_repo.create_studio(name=p_name, logo_path=parent_info["logo_path"])
                            self.metadata_repo.flush()
                    except Exception:
                        parent_studio = self.metadata_repo.get_studio_by_name(p_name)
                elif parent_info.get("logo_path") and (
                    not parent_studio.logo_path 
                    or not self._local_image_exists(parent_studio.logo_path, "logos")
                    or (parent_studio.logo_path.startswith("logos/") and parent_studio.logo_path.lower().endswith((".jpg", ".jpeg")))
                ):
                    parent_studio.logo_path = parent_info["logo_path"]
                studio.parent_studio = parent_studio
                self.queue_studio_logo(parent_studio)

            self.queue_studio_logo(studio)

            if studio not in match.studios:
                match.studios.append(studio)
