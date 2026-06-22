import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import BinaryIO, Iterable, Optional
from PIL import Image
import requests
from io import BytesIO

from app.domains.media_assets.services import image_selectors
from app.shared_kernel.constants import (
    TMDB_IMAGE_BASE,
    TMDB_DOWNLOAD_SIZES,
    MEDIA_IMAGE_SUBFOLDERS,
    MEDIA_IMAGE_LIMITS,
    MIN_CACHED_IMAGE_BYTES,
)

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """
    Handles file operations, formatting, verification, and downscaling
    for downloaded media assets (covers, posters, backdrops, logos).
    """

    def __init__(self, image_root: Optional[str | Path] = None):
        """
        Resolves the image storage root.
        Defaults to the portable local 'data/media/images' directory in the application root.
        """
        if image_root:
            self.image_root = Path(image_root)
        else:
            self.image_root = Path(__file__).resolve().parents[4] / "data" / "media" / "images"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def ensure_folders(self) -> None:
        """Ensures all subdirectories exist for original assets and thumbnails."""
        for subfolder in MEDIA_IMAGE_SUBFOLDERS:
            (self.image_root / "original" / subfolder).mkdir(parents=True, exist_ok=True)
            (self.image_root / "thumbnails" / subfolder).mkdir(parents=True, exist_ok=True)

    def get_original_path(self, subfolder: str, filename: str) -> Path:
        """Returns target path for original resolution image."""
        return self.image_root / "original" / subfolder / filename.lstrip("/")

    def get_thumbnail_path(self, subfolder: str, filename: str) -> Path:
        """Returns target path for the thumbnail image (keeping original extension)."""
        return self.image_root / "thumbnails" / subfolder / filename.lstrip("/")

    def exists(self, path: str | Path) -> bool:
        """Checks if a file exists and is not corrupted/empty."""
        p = Path(path)
        return p.exists() and p.stat().st_size > MIN_CACHED_IMAGE_BYTES

    def write_chunks(self, target_path: str | Path, chunks: Iterable[bytes]) -> Optional[str]:
        """Writes network chunk stream to a file safely via a temp file."""
        target = Path(target_path)
        temp_path = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(temp_path, "wb") as f:
                for chunk in chunks:
                    if chunk:
                        f.write(chunk)
            return self._finalize_file(temp_path, target)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def write_upload(self, target_path: str | Path, source: BinaryIO) -> Optional[str]:
        """Writes uploaded image stream to a file safely via a temp file."""
        target = Path(target_path)
        temp_path = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(temp_path, "wb") as f:
                shutil.copyfileobj(source, f)
            return self._finalize_file(temp_path, target)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def generate_thumbnail(self, original_path: str | Path, thumbnail_path: str | Path, subfolder: str) -> bool:
        """
        Loads an original image, resizes it keeping aspect ratio according to
        configured subfolder limits, and saves it in its original format.
        If the image is already within bounds, skips processing and copies it directly.
        """
        orig = Path(original_path)
        thumb = Path(thumbnail_path)
        
        if not self.exists(orig):
            logger.warning(f"Cannot generate thumbnail: original file {orig} does not exist.")
            return False

        # Exclude SVGs from processing
        if orig.suffix.lower() == ".svg":
            thumb.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(orig, thumb)
            return True

        limits = MEDIA_IMAGE_LIMITS.get(subfolder)
        if not limits:
            # No limits configured for this category (e.g. logos) -> skip thumbnail, use original
            return True

        thumb_temp = thumb.with_name(f"{thumb.name}.{uuid.uuid4().hex}.tmp")
        thumb.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 1. Quick size check to avoid decoding/processing if already small
            with Image.open(orig) as img:
                width, height = img.size
                
                max_width = limits.get("max_width")
                max_height = limits.get("max_height")
                
                already_in_bounds = True
                if max_width and width > max_width:
                    already_in_bounds = False
                if max_height and height > max_height:
                    already_in_bounds = False

            if already_in_bounds:
                # Already in bounds, no thumbnail needed
                return True

            # 2. Resize if bounds exceeded
            with Image.open(orig) as img:
                orig_format = img.format or ("PNG" if orig.suffix.lower() == ".png" else "JPEG")
                width, height = img.size
                
                if max_width and width > max_width:
                    ratio = max_width / float(width)
                    new_height = int(float(height) * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                elif max_height and height > max_height:
                    ratio = max_height / float(height)
                    new_width = int(float(width) * ratio)
                    img = img.resize((new_width, max_height), Image.Resampling.LANCZOS)
                
                # Convert modes if saving as JPEG (must not be RGBA)
                if orig_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")

                # Save using original format with default settings
                img.save(thumb_temp, orig_format)
            
            if thumb.exists():
                thumb.unlink()
            thumb_temp.replace(thumb)
            return True
        except Exception as e:
            logger.error(f"Failed to generate thumbnail for {orig} in {subfolder}: {e}")
            if thumb_temp.exists():
                thumb_temp.unlink()
            return False

    def _finalize_file(self, temp_path: Path, target_path: Path) -> Optional[str]:
        """Verifies integrity and moves file to target path."""
        if not temp_path.exists() or temp_path.stat().st_size < MIN_CACHED_IMAGE_BYTES:
            return None

        # Check for SVG
        is_svg = False
        try:
            with open(temp_path, "rb") as f:
                header = f.read(4096).strip().lower()
                if header.startswith(b"<svg") or header.startswith(b"<?xml") or b"<svg" in header:
                    is_svg = True
        except Exception:
            pass

        # Verify image integrity via PIL (unless SVG) and cap at 4K for scene_stills/backdrops
        if not is_svg:
            try:
                need_save = False
                with Image.open(temp_path) as img:
                    img.verify()
                
                # Open again to process/resize if needed
                with Image.open(temp_path) as img:
                    img_format = img.format or "JPEG"
                    if "scene_stills" in target_path.parts or "backdrops" in target_path.parts:
                        width, height = img.size
                        if width > 3840 or height > 3840:
                            if width >= height:
                                new_width = 3840
                                new_height = int(height * (3840.0 / float(width)))
                            else:
                                new_height = 3840
                                new_width = int(width * (3840.0 / float(height)))
                            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            need_save = True

                    if need_save:
                        if img_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                            img = img.convert("RGB")
                        img.save(temp_path, img_format)
            except Exception as e:
                logger.error(f"Image verification/processing failed: {e}")
                return None

        if target_path.exists():
            target_path.unlink()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.replace(target_path)
        return str(target_path)

    def resolve_image_url(self, path: Optional[str], subfolder: str, size: str = "w500") -> Optional[str]:
        """
        Resolves the image path/URL for the frontend.
        1. If it's a remote URL (HTTP/HTTPS), returns it directly.
        2. If the local thumbnail exists, returns its relative path for frontend serving.
        3. If it is a relative TMDB path (starts with /), falls back to the TMDB CDN.
        """
        if not path:
            return None

        # 1. Remote URL fallback
        if path.startswith(("http://", "https://")):
            return path

        # 2. Local check
        filename = os.path.basename(path)
        thumb_path = self.get_thumbnail_path(subfolder, filename)
        if self.exists(thumb_path):
            return f"/media/images/thumbnails/{subfolder}/{filename}"
        orig_path = self.get_original_path(subfolder, filename)
        if self.exists(orig_path):
            return f"/media/images/original/{subfolder}/{filename}"

        # 3. TMDB CDN fallback
        if path.startswith("/") and not path.startswith("/media/"):
            return f"{TMDB_IMAGE_BASE}{size}{path}"

        return None

    def pick_logo_path(self, raw_data: dict, preferred_language: Optional[str] = None) -> Optional[str]:
        """
        Analyzes and selects the best logo from TMDB metadata images.
        Ensures the logo has sufficient luminance to be readable on dark overlays.
        """
        return image_selectors.pick_logo_path(
            raw_data=raw_data,
            image_root=self.image_root,
            session=self.session,
            preferred_language=preferred_language
        )

    def pick_backdrop_path(
        self,
        raw_data: dict,
        preferred_language: Optional[str] = None,
        min_width: int = 1920,
        allow_low_res: bool = True
    ) -> Optional[str]:
        """
        Analyzes and selects the best backdrop from TMDB metadata images.
        Filters out over-bright (white) backdrops to maintain readability of overlaid text.
        """
        return image_selectors.pick_backdrop_path(
            raw_data=raw_data,
            image_root=self.image_root,
            session=self.session,
            preferred_language=preferred_language,
            min_width=min_width,
            allow_low_res=allow_low_res
        )

    def get_download_url(self, path: Optional[str], subfolder: str) -> Optional[str]:
        """
        Builds the download URL for an asset.
        - If it's a remote URL, returns it directly (rewriting TMDB URLs to the configured download size).
        - If it's a relative TMDB path (starts with /), prepends the base URL and the configured download size.
        """
        if not path:
            return None
        if path.startswith(("http://", "https://")):
            if "image.tmdb.org/t/p/" in path:
                parts = path.split("/t/p/")
                if len(parts) == 2:
                    subparts = parts[1].split("/", 1)
                    if len(subparts) == 2:
                        size = TMDB_DOWNLOAD_SIZES.get(subfolder, "original")
                        return f"{parts[0]}/t/p/{size}/{subparts[1]}"
            return path
        if path.startswith("/"):
            size = TMDB_DOWNLOAD_SIZES.get(subfolder, "original")
            return f"{TMDB_IMAGE_BASE}{size}{path}"
        return None

    def get_db_relative_paths(self, filename: str, subfolder: str) -> tuple[str, str]:
        """
        Returns relative paths for storing in the database.
        Format:
          Original: media/images/original/{subfolder}/{filename}
          Thumbnail: media/images/thumbnails/{subfolder}/{filename}
        """
        clean_filename = os.path.basename(filename)
        orig_rel = f"media/images/original/{subfolder}/{clean_filename}"
        thumb_rel = f"media/images/thumbnails/{subfolder}/{clean_filename}"
        return orig_rel, thumb_rel


image_processing_service = ImageProcessingService()

