import re
import os
import logging
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.domains.metadata.models import MetadataMatch, MetadataLocalization, MediaCollection
from app.shared_kernel.enums import Provider, MediaType
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.shared_kernel.language import LanguageService
from app.shared_kernel.ports.metadata_repository_port import MetadataRepositoryPort

logger = logging.getLogger(__name__)

class MatchPersister:
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

    def queue_adult_assets(self, match: MetadataMatch) -> None:
        """Queues poster/backdrop downloads for adult matches."""
        def queue_image(path: Optional[str], subfolder: str, prefix: str) -> Optional[str]:
            if not path:
                return None

            url = self.image_downloader.get_download_url(path, subfolder)
            if not url:
                return None

            basename = os.path.basename(urlparse(path).path)
            if not basename:
                return None

            ext = os.path.splitext(basename)[1].lower()
            if ext not in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'}:
                try:
                    import requests
                    resp = requests.head(url, timeout=3, allow_redirects=True)
                    ct = resp.headers.get("Content-Type", "").lower()
                    if "png" in ct:
                        ext = ".png"
                    elif "webp" in ct:
                        ext = ".webp"
                    elif "gif" in ct:
                        ext = ".gif"
                    elif "svg" in ct:
                        ext = ".svg"
                    else:
                        ext = ".jpg"
                except Exception:
                    ext = ".jpg"
                basename = f"{basename}{ext}"

            safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("_")
            filename = f"{safe_prefix}_{basename}"
            self.image_downloader.enqueue_download(url, subfolder, filename)
            return f"{subfolder}/{filename}"

        asset_prefix = f"{match.provider.value}_{match.external_id}"
        backdrop_subfolder = "scene_stills" if match.media_type == MediaType.SCENE else "backdrops"
        match.local_backdrop_path = queue_image(match.backdrop_path, backdrop_subfolder, asset_prefix)

        loc = next((l for l in match.localizations if l.locale == DEFAULT_FALLBACK_LANGUAGE), None)
        if loc:
            if match.media_type == MediaType.SCENE and loc.poster_path and loc.poster_path == match.backdrop_path:
                loc.local_poster_path = match.local_backdrop_path
            else:
                loc.local_poster_path = queue_image(loc.poster_path, "posters", asset_prefix)

    def persist_collection(self, coll_info: Dict[str, Any], match: MetadataMatch, language: str):
        coll_id = coll_info["external_id"]
        collection = self.metadata_repo.get_collection(Provider.TMDB, coll_id)
        if not collection:
            try:
                with self.db.begin_nested():
                    collection = self.metadata_repo.create_collection(
                        provider=Provider.TMDB,
                        external_id=coll_id,
                        backdrop_path=coll_info["backdrop_path"]
                    )
                    self.metadata_repo.flush()
            except Exception:
                collection = self.metadata_repo.get_collection(Provider.TMDB, coll_id)
        match.collection = collection
        
        if collection:
            lang_code = LanguageService.clean_locale(language)
            loc = None
            if collection.id is not None:
                loc = self.metadata_repo.get_collection_localization(collection.id, lang_code)
            if not loc:
                loc = self.metadata_repo.create_collection_localization(
                    collection_id=collection.id,
                    locale=lang_code
                )
            loc.title = coll_info.get("name") or loc.title
            loc.poster_path = coll_info.get("poster_path") or loc.poster_path
            
            if loc.poster_path and not loc.local_poster_path:
                try:
                    url = self.image_downloader.get_download_url(loc.poster_path, "posters")
                    if url:
                        import re
                        from urllib.parse import urlparse
                        basename = os.path.basename(urlparse(loc.poster_path).path)
                        ext = os.path.splitext(basename)[1].lower() or ".jpg"
                        asset_prefix = f"tmdb_{collection.external_id}"
                        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", asset_prefix).strip("_")
                        filename = f"{safe_prefix}_{basename}{ext}"
                        self.image_downloader.enqueue_download(url, "posters", filename)
                        loc.local_poster_path = f"posters/{filename}"
                except Exception as e:
                    logger.error(f"Failed to queue image download for collection in persistence: {e}")

            if collection.backdrop_path and not collection.local_backdrop_path:
                try:
                    url = self.image_downloader.get_download_url(collection.backdrop_path, "backdrops")
                    if url:
                        import re
                        from urllib.parse import urlparse
                        basename = os.path.basename(urlparse(collection.backdrop_path).path)
                        ext = os.path.splitext(basename)[1].lower() or ".jpg"
                        asset_prefix = f"tmdb_{collection.external_id}"
                        safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", asset_prefix).strip("_")
                        filename = f"{safe_prefix}_{basename}{ext}"
                        self.image_downloader.enqueue_download(url, "backdrops", filename)
                        collection.local_backdrop_path = f"backdrops/{filename}"
                except Exception as e:
                    logger.error(f"Failed to queue backdrop download for collection in persistence: {e}")
