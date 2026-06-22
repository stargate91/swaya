import os
import re
from pathlib import Path
from urllib.parse import urlparse
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.shared_kernel.enums import Provider, MediaType, RoleType
from app.shared_kernel.constants import DEFAULT_FALLBACK_LANGUAGE
from app.domains.metadata.models import MetadataMatch, MetadataLocalization, Studio, MediaCollection
from app.domains.people.models import Person, MediaPersonLink
from app.domains.people.services import PersonService

logger = logging.getLogger(__name__)


import threading

persistence_lock = threading.Lock()

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

    try:
        import requests

        resp = requests.head(url, timeout=3, allow_redirects=True)
        ext = from_content_type(resp.headers.get('Content-Type', ''))
        if ext:
            return ext
    except Exception:
        pass

    try:
        import requests

        resp = requests.get(url, timeout=5, allow_redirects=True, stream=True)
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


class ScraperPersister:
    """
    Handles database persistence for scraper metadata.
    Decoupled from scraper classes to maintain clean domain boundaries.
    """

    def __init__(self, db: Session):
        self.db = db

    def persist_normalized_scene(
        self,
        provider: Provider,
        scene_id: str,
        norm: Dict[str, Any],
        media_type: MediaType = MediaType.SCENE,
    ) -> MetadataMatch:
        """Takes a normalized scene structure and persists it to the database."""
        with persistence_lock:
            # Find or create match
            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == provider,
                MetadataMatch.external_id == scene_id,
                MetadataMatch.media_type == media_type
            ).first()

            if not match:
                match = MetadataMatch(
                    provider=provider,
                    external_id=scene_id,
                    media_type=media_type
                )
                try:
                    with self.db.begin_nested():
                        self.db.add(match)
                        self.db.flush()
                except Exception:
                    match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == provider,
                        MetadataMatch.external_id == scene_id,
                        MetadataMatch.media_type == media_type
                    ).first()

            # 1. Map basic match fields
            for k, v in norm["match"].items():
                setattr(match, k, v)

            # 2. Map Studio details
            for studio_info in norm["studios"]:
                s_name = studio_info["name"]
                studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                if not studio:
                    studio = Studio(name=s_name, logo_path=studio_info["logo_path"])
                    try:
                        with self.db.begin_nested():
                            self.db.add(studio)
                            self.db.flush()
                    except Exception:
                        studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                elif studio_info.get("logo_path") and (
                    not studio.logo_path 
                    or (studio.logo_path.startswith("logos/") and studio.logo_path.lower().endswith((".jpg", ".jpeg")))
                ):
                    studio.logo_path = studio_info["logo_path"]
                
                # Map parent studio
                parent_info = studio_info["parent"]
                if parent_info:
                    p_name = parent_info["name"]
                    parent_studio = self.db.query(Studio).filter(Studio.name == p_name).first()
                    if not parent_studio:
                        parent_studio = Studio(name=p_name, logo_path=parent_info["logo_path"])
                        try:
                            with self.db.begin_nested():
                                self.db.add(parent_studio)
                                self.db.flush()
                        except Exception:
                            parent_studio = self.db.query(Studio).filter(Studio.name == p_name).first()
                    elif parent_info.get("logo_path") and (
                        not parent_studio.logo_path 
                        or (parent_studio.logo_path.startswith("logos/") and parent_studio.logo_path.lower().endswith((".jpg", ".jpeg")))
                    ):
                        parent_studio.logo_path = parent_info["logo_path"]
                    studio.parent_studio = parent_studio
                    self._queue_studio_logo(parent_studio)

                self._queue_studio_logo(studio)

                if studio not in match.studios:
                    match.studios.append(studio)

            loc = None
            for l in match.localizations:
                if l.locale == DEFAULT_FALLBACK_LANGUAGE:
                    loc = l
                    break
            if not loc:
                loc = self.db.query(MetadataLocalization).filter(
                    MetadataLocalization.match_id == match.id if match.id else False,
                    MetadataLocalization.locale == DEFAULT_FALLBACK_LANGUAGE
                ).first()
            if not loc:
                loc = MetadataLocalization(locale=DEFAULT_FALLBACK_LANGUAGE)
                for k, v in norm["localization"].items():
                    if k != "genres":
                        setattr(loc, k, v)
                match.localizations.append(loc)
                try:
                    with self.db.begin_nested():
                        self.db.flush()
                except Exception:
                    loc = self.db.query(MetadataLocalization).filter(
                        MetadataLocalization.match_id == match.id if match.id else False,
                        MetadataLocalization.locale == DEFAULT_FALLBACK_LANGUAGE
                    ).first()
            else:
                for k, v in norm["localization"].items():
                    if k != "genres":
                        setattr(loc, k, v)

            # 4. Map Performers/Cast utilizing PersonService
            person_service = PersonService(self.db)
            for idx, perf in enumerate(norm["performers"]):
                prov_enum = None
                if perf.get("provider"):
                    try:
                        prov_enum = Provider(perf["provider"])
                    except Exception:
                        pass
                person = person_service.update_or_create_person(
                    name=perf["name"],
                    profile_path=perf["profile_path"],
                    gender=perf["gender"],
                    is_adult=perf["is_adult"],
                    performer_details=perf["performer_details"],
                    provider=prov_enum,
                    external_id=perf.get("external_id")
                )

                # Queue profile image download
                self._queue_person_profile(person)

                # Link person to match
                link = self.db.query(MediaPersonLink).filter(
                    MediaPersonLink.match_id == match.id if match.id else False,
                    MediaPersonLink.person_id == person.id if person.id else False,
                    MediaPersonLink.role == RoleType.ACTOR
                ).first()

                if not link:
                    link = MediaPersonLink(
                        role=RoleType.ACTOR,
                        order=idx
                    )
                    link.person = person
                    match.people.append(link)

            self.db.flush()
            self._queue_adult_assets(match)
            return match

    def persist_normalized_movie(self, movie_id: str, norm: Dict[str, Any], language: str) -> MetadataMatch:
        """Takes a normalized movie structure and persists it to the database."""
        with persistence_lock:
            match = self.db.query(MetadataMatch).filter(
                MetadataMatch.provider == Provider.TMDB,
                MetadataMatch.external_id == movie_id,
                MetadataMatch.media_type == MediaType.MOVIE
            ).first()

            if not match:
                match = MetadataMatch(
                    provider=Provider.TMDB,
                    external_id=movie_id,
                    media_type=MediaType.MOVIE
                )
                try:
                    with self.db.begin_nested():
                        self.db.add(match)
                        self.db.flush()
                except Exception:
                    match = self.db.query(MetadataMatch).filter(
                        MetadataMatch.provider == Provider.TMDB,
                        MetadataMatch.external_id == movie_id,
                        MetadataMatch.media_type == MediaType.MOVIE
                    ).first()

            # 1. Map basic match fields
            for k, v in norm["match"].items():
                setattr(match, k, v)

            # 2. Map Studio details
            for studio_info in norm["studios"]:
                s_name = studio_info["name"]
                studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                if not studio:
                    studio = Studio(name=s_name, logo_path=studio_info["logo_path"])
                    try:
                        with self.db.begin_nested():
                            self.db.add(studio)
                            self.db.flush()
                    except Exception:
                        studio = self.db.query(Studio).filter(Studio.name == s_name).first()
                elif studio_info.get("logo_path") and (
                    not studio.logo_path 
                    or (studio.logo_path.startswith("logos/") and studio.logo_path.lower().endswith((".jpg", ".jpeg")))
                ):
                    studio.logo_path = studio_info["logo_path"]

                if studio not in match.studios:
                    match.studios.append(studio)
                
                self._queue_studio_logo(studio)

            # 3. Map Collection details
            coll_info = norm["collection"]
            if coll_info:
                coll_id = coll_info["external_id"]
                collection = self.db.query(MediaCollection).filter(
                    MediaCollection.provider == Provider.TMDB,
                    MediaCollection.external_id == coll_id
                ).first()
                if not collection:
                    collection = MediaCollection(
                        provider=Provider.TMDB,
                        external_id=coll_id,
                        backdrop_path=coll_info["backdrop_path"]
                    )
                    try:
                        with self.db.begin_nested():
                            self.db.add(collection)
                            self.db.flush()
                    except Exception:
                        collection = self.db.query(MediaCollection).filter(
                            MediaCollection.provider == Provider.TMDB,
                            MediaCollection.external_id == coll_id
                        ).first()
                match.collection = collection

            # 4. Map Localization
            loc = None
            for l in match.localizations:
                if l.locale == language:
                    loc = l
                    break
            if not loc:
                loc = self.db.query(MetadataLocalization).filter(
                    MetadataLocalization.match_id == match.id if match.id else False,
                    MetadataLocalization.locale == language
                ).first()
            if not loc:
                loc = MetadataLocalization(locale=language)
                for k, v in norm["localization"].items():
                    setattr(loc, k, v)
                match.localizations.append(loc)
                try:
                    with self.db.begin_nested():
                        self.db.flush()
                except Exception:
                    loc = self.db.query(MetadataLocalization).filter(
                        MetadataLocalization.match_id == match.id if match.id else False,
                        MetadataLocalization.locale == language
                    ).first()
            else:
                for k, v in norm["localization"].items():
                    setattr(loc, k, v)

            # 5. Map Cast/Crew utilizing PersonService
            person_service = PersonService(self.db)
            for idx, cast_member in enumerate(norm["performers"][:15]):
                person = person_service.update_or_create_person(
                    name=cast_member["name"],
                    profile_path=cast_member["profile_path"],
                    gender=cast_member["gender"],
                    is_adult=cast_member["is_adult"],
                    tmdb_id=cast_member["tmdb_id"]
                )
                
                # Queue profile image download
                self._queue_person_profile(person)

                # Check Link
                link = self.db.query(MediaPersonLink).filter(
                    MediaPersonLink.match_id == match.id if match.id else False,
                    MediaPersonLink.person_id == person.id if person.id else False,
                    MediaPersonLink.role == RoleType.ACTOR
                ).first()
                if not link:
                    link = MediaPersonLink(
                        role=RoleType.ACTOR,
                        character_name=cast_member["character"],
                        order=idx
                    )
                    link.person = person
                    match.people.append(link)

            self.db.flush()
            self._queue_adult_assets(match)
            return match

    def _queue_adult_assets(self, match: MetadataMatch) -> None:
        """Queues poster/backdrop downloads for adult matches."""
        try:
            from app.domains.tasks import task_manager
        except Exception:
            return

        image_service = task_manager.download_worker.image_service

        def queue_image(path: Optional[str], subfolder: str, prefix: str) -> Optional[str]:
            if not path:
                return None

            url = image_service.get_download_url(path, subfolder)
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
            task_manager.download_worker.enqueue_download(url, subfolder, filename)
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

    def _queue_studio_logo(self, studio: Studio) -> None:
        """Queues studio logo downloads."""
        if not studio or not studio.logo_path:
            return
        if studio.logo_path.startswith("logos/"):
            return

        try:
            from app.domains.tasks import task_manager
            image_service = task_manager.download_worker.image_service
        except Exception:
            return

        url = image_service.get_download_url(studio.logo_path, "logos")
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
        task_manager.download_worker.enqueue_download(url, "logos", filename)

    def _queue_person_profile(self, person: Person) -> None:
        """Queues person profile image downloads."""
        if not person or not person.profile_path:
            return
        if person.local_profile_path and person.local_profile_path.startswith("people/"):
            return

        try:
            from app.domains.tasks import task_manager
            image_service = task_manager.download_worker.image_service
        except Exception:
            return

        url = image_service.get_download_url(person.profile_path, "people")
        if not url:
            return

        basename = os.path.basename(urlparse(person.profile_path).path)
        if not basename:
            return

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
            elif "jpeg" in ct or "jpg" in ct:
                ext = ".jpg"
            else:
                ext = os.path.splitext(basename)[1].lower() or ".jpg"
        except Exception:
            ext = os.path.splitext(basename)[1].lower() or ".jpg"
        basename = f"{basename}{ext}"

        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", person.name).strip("_")
        ext_id = "unknown"
        prov_val = "perf"
        if person.external_ids:
            for k, v in person.external_ids.items():
                prov_val = k
                ext_id = v
                break
        filename = f"{prov_val}_{ext_id}_{safe_name}_{basename}"
        person.local_profile_path = f"people/{filename}"
        task_manager.download_worker.enqueue_download(url, "people", filename)
